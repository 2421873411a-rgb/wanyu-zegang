"""门禁场景 6/7/8：管理员导入真实性、最后管理员保护、超大上传 413。

v17.9.10 新增门禁：
- meta 缺失必须整体拒绝（fail-closed，不允许 optional validation）
- job_id 格式非法必须拒绝（旧实现"解析不了就放过"的 fail-open 回归锁）
- canonical 键 all_majors + canonical meta 约定（total=raw）必须可导入
- 快照语义：stale 下线 → 公共查询不可见；重新出现自动恢复 active；
  字段 exact overwrite（源清空 → DB 清空）
"""
import json

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.job import Job
from app.models.user import User

from tests.conftest import get_test_session_factory, _auth, _login, _make_admin, _register

pytestmark = pytest.mark.asyncio


def _row(cycle: str, i: int, **extra) -> dict:
    rid = f"job-{cycle}-{i:020x}"
    row = {
        "job_id": rid,
        "row_id": rid,
        "code": f"1{i:05d}",
        "city": "合肥",
        "exam": "省考",
        "unit": f"测试单位{i}",
        "zw": "测试职位",
        "zy": "法学",
        "num": 2,
        "bm": 10,
        "xl": "本科及以上",
    }
    row.update(extra)
    return row


def _payload(n: int = 3, cycle: str = "2026", key: str = "allMajors") -> dict:
    """静态派生约定：total=active=n、raw_total=n、excluded=0、recruits=active sum(num)。"""
    rows = [_row(cycle, i) for i in range(n)]
    meta = {"total": n, "raw_total": n, "excluded": 0, "recruits": n * 2}
    return {key: {"meta": meta, "rows": rows}, "cycle": cycle}


async def _admin_headers(client: AsyncClient) -> dict:
    await _make_admin()
    data = await _login(client, "admin@example.com", "abc1234567")
    return _auth(data["access_token"])


async def _import(client: AsyncClient, headers: dict, payload, cycle: str = "2026"):
    body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
    return await client.post(f"/api/v1/admin/import/{cycle}", headers=headers,
                             files={"file": ("jobs.json", body, "application/json")})


async def _job_count(cycle: str = "2026") -> int:
    async with get_test_session_factory()() as session:
        return (await session.execute(
            select(func.count(Job.id)).where(Job.cycle == cycle)
        )).scalar()


async def test_non_admin_cannot_access_admin(client: AsyncClient):
    data = await _register(client)
    r = await client.get("/api/v1/admin/dashboard", headers=_auth(data["access_token"]))
    assert r.status_code == 403
    r2 = await client.get("/api/v1/admin/users")
    assert r2.status_code in (401, 403)


async def test_import_writes_rows_and_reconciles(client: AsyncClient):
    """门禁6：导入必须真实写库——响应含对账统计 + mirror state + 快照替换。"""
    headers = await _admin_headers(client)
    r = await _import(client, headers, _payload(3))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_total"] == 3
    assert body["imported"] == 3
    assert body["updated"] == 0
    assert body["deactivated"] == 0
    assert len(body["source_sha256"]) == 64
    assert len(body["job_id_set_sha256"]) == 64

    assert await _job_count() == 3


async def test_import_rejects_bad_structure_and_cycle(client: AsyncClient):
    """门禁6b：结构不符/非法周期必须失败（绝不假成功）。"""
    headers = await _admin_headers(client)
    r1 = await _import(client, headers, b'{"hello": 1}')
    assert r1.status_code == 400
    r2 = await _import(client, headers, _payload(1), cycle="1999")
    assert r2.status_code == 400
    r3 = await _import(client, headers, b"not json")
    assert r3.status_code == 400
    # 确认没有数据被写入（事务干净）
    assert await _job_count() == 0


async def test_import_oversize_returns_413(client: AsyncClient, monkeypatch):
    """门禁8：超大 JSON upload 返回 413。"""
    from app.config import settings
    monkeypatch.setattr(settings, "ADMIN_IMPORT_MAX_BYTES", 1024)
    headers = await _admin_headers(client)
    r = await _import(client, headers, _payload(2000))
    assert r.status_code == 413, r.text


async def test_last_admin_cannot_be_demoted_or_disabled(client: AsyncClient):
    """门禁7：最后管理员不能被降权/禁用。"""
    headers = await _admin_headers(client)
    async with get_test_session_factory()() as session:
        admin_id = (await session.execute(select(User).where(User.email == "admin@example.com"))).scalar_one().id

    r1 = await client.put(f"/api/v1/admin/users/{admin_id}?is_admin=false", headers=headers)
    assert r1.status_code == 400
    r2 = await client.put(f"/api/v1/admin/users/{admin_id}?is_active=false", headers=headers)
    assert r2.status_code == 400

    # 有了第二名管理员后，降权第一名才放行
    r3 = await client.put(f"/api/v1/admin/users/{admin_id}?is_admin=true", headers=headers)
    assert r3.status_code == 200
    await _make_admin(email="admin2@example.com", username="admin2")
    r4 = await client.put(f"/api/v1/admin/users/{admin_id}?is_admin=false", headers=headers)
    assert r4.status_code == 200


async def test_register_cannot_reach_admin_endpoints_even_with_admin_email(client: AsyncClient):
    """门禁1（纵深）：ADMIN_EMAIL 注册的用户对管理后台无任何权限。"""
    from app.config import settings
    settings.ADMIN_EMAIL = "sneaky@kaogong.art"
    data = await _register(client, email="sneaky@kaogong.art", username="sneaky")
    for path in ("/api/v1/admin/dashboard", "/api/v1/admin/users"):
        r = await client.get(path, headers=_auth(data["access_token"]))
        assert r.status_code == 403


async def test_truncated_snapshot_rejected(client: AsyncClient):
    """门禁：截断快照必须被 meta 守恒拦住（raw_total 与行数不符）。"""
    headers = await _admin_headers(client)
    payload = _payload(3)
    payload["allMajors"]["rows"] = payload["allMajors"]["rows"][:1]  # 3 行截成 1 行
    r = await _import(client, headers, payload)
    assert r.status_code == 400
    assert "raw_total" in r.json()["detail"]
    assert await _job_count() == 0


async def test_missing_meta_rejected(client: AsyncClient):
    """门禁：meta 缺失必须整体拒绝——无守恒锚点的快照不允许 optional validation。"""
    headers = await _admin_headers(client)
    payload = {"allMajors": {"rows": [_row("2026", 0)]}}
    r = await _import(client, headers, payload)
    assert r.status_code == 400
    assert "meta" in r.json()["detail"]
    assert await _job_count() == 0


async def test_bad_job_id_format_rejected(client: AsyncClient):
    """门禁：job_id 格式非法必须拒绝（旧实现解析不了就放过——fail-open 回归锁）。"""
    headers = await _admin_headers(client)
    for bad in ("job-test-0000", "hello", "job-26-aaaaaaaaaaaaaaaaaaaa"):
        payload = _payload(0)
        payload["allMajors"]["rows"] = [_row("2026", 0, job_id=bad, row_id=bad)]
        payload["allMajors"]["meta"] = {"total": 1, "raw_total": 1, "excluded": 0, "recruits": 2}
        r = await _import(client, headers, payload)
        assert r.status_code == 400, (bad, r.text)
        assert await _job_count() == 0


async def test_cycle_mismatch_rejected(client: AsyncClient):
    """门禁：格式合法但年份不一致的 job_id 必须拒绝（job-2024-* 混入 2026）。"""
    headers = await _admin_headers(client)
    payload = _payload(1)
    foreign = _row("2024", 0)
    payload["allMajors"]["rows"] = [foreign]
    payload["allMajors"]["meta"] = {"total": 1, "raw_total": 1, "excluded": 0, "recruits": 2}
    r = await _import(client, headers, payload)
    assert r.status_code == 400
    assert "周期不匹配" in r.json()["detail"]
    assert await _job_count() == 0


async def test_duplicate_job_id_rejected(client: AsyncClient):
    """门禁：重复 job_id 必须拒绝。"""
    headers = await _admin_headers(client)
    base = _row("2026", 0)
    payload = _payload(0)
    payload["allMajors"]["rows"] = [base, {**base}]
    payload["allMajors"]["meta"] = {"total": 2, "raw_total": 2, "excluded": 0, "recruits": 4}
    r = await _import(client, headers, payload)
    assert r.status_code == 400
    assert "重复" in r.json()["detail"]
    assert await _job_count() == 0


async def test_canonical_all_majors_key_and_provenance_accepted(client: AsyncClient):
    """门禁：canonical 真源（all_majors + total=raw 约定 + provenance 指纹）必须可直接导入。"""
    from app.services.import_service import _job_id_set_sha256

    headers = await _admin_headers(client)
    rows = [_row("2026", 0), _row("2026", 1, record_status="duplicate",
                                  exclusion_reason="cross_city_source_duplication",
                                  exclusion_evidence="d2_resolution_report.txt",
                                  excluded_at="2026-09-05")]
    payload = {
        "schema": "wanyu-cycle-bundle/v1",
        "cycle": "2026",
        "label": "2026 · 测试快照",
        "all_majors": {
            "meta": {"total": 2, "raw_total": 2, "excluded": 1, "recruits": 4},
            "rows": rows,
        },
        "provenance": {"job_id_set_sha256": _job_id_set_sha256([r["job_id"] for r in rows])},
    }
    r = await _import(client, headers, payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_total"] == 2
    assert body["deactivated"] == 0
    assert await _job_count() == 2

    # DB 中 canonical 排除行必须落成 excluded，且公共查询不可见
    async with get_test_session_factory()() as session:
        job = (await session.execute(select(Job).where(Job.record_status == "excluded"))).scalar_one()
        assert job.job_id == rows[1]["job_id"]

    search = await client.get("/api/v1/jobs/search", params={"cycle": "2026"})
    assert search.status_code == 200
    assert search.json()["total"] == 1
    detail = await client.get(f"/api/v1/jobs/{rows[1]['job_id']}")
    assert detail.status_code == 404


async def test_provenance_mismatch_rejected(client: AsyncClient):
    """门禁：provenance.job_id_set_sha256 与行集不一致必须拒绝。"""
    headers = await _admin_headers(client)
    rows = [_row("2026", 0)]
    payload = {
        "cycle": "2026",
        "all_majors": {"meta": {"total": 1, "raw_total": 1, "excluded": 0, "recruits": 2}, "rows": rows},
        "provenance": {"job_id_set_sha256": "0" * 64},
    }
    r = await _import(client, headers, payload)
    assert r.status_code == 400
    assert "job_id_set_sha256" in r.json()["detail"]
    assert await _job_count() == 0


async def test_validation_failure_leaves_db_unchanged(client: AsyncClient):
    """门禁：校验失败后 DB 一行都不能变化。"""
    headers = await _admin_headers(client)
    r1 = await _import(client, headers, _payload(3))
    assert r1.status_code == 200
    before = await _job_count()

    bad = _payload(1, cycle="2024")  # 行全为 2024 job_id → 周期不匹配
    r2 = await _import(client, headers, bad)
    assert r2.status_code == 400
    assert await _job_count() == before


async def test_snapshot_semantics_deactivate_reactivate_and_exact_overwrite(client: AsyncClient):
    """快照语义全链：stale 下线 → 公共查询不可见 → 重新出现自动恢复 active；
    字段 exact overwrite（源清空 → DB 清空，不做 `new or old` 残留）。"""
    headers = await _admin_headers(client)

    # 第 1 次：3 行，job0 带 xz（政治面貌）
    p1 = _payload(3)
    p1["allMajors"]["rows"][0]["xz"] = "中共党员"
    r1 = await _import(client, headers, p1)
    assert r1.status_code == 200, r1.text
    j0 = p1["allMajors"]["rows"][0]["job_id"]

    # 第 2 次：快照只剩 2 行（job0/job1），job2 被"下线"；job1 的 xz 被源清空
    p2 = _payload(2)
    r2 = await _import(client, headers, p2)
    assert r2.status_code == 200, r2.text
    assert r2.json()["deactivated"] == 1
    j2 = _row("2026", 2)["job_id"]

    async with get_test_session_factory()() as session:
        s0 = (await session.execute(select(Job).where(Job.job_id == j0))).scalar_one()
        s2 = (await session.execute(select(Job).where(Job.job_id == j2))).scalar_one()
        assert s2.record_status == "excluded"
        assert s0.record_status == "active"
        # exact overwrite：第 2 次快照 job0 无 xz → DB 必须清空，不允许残留"中共党员"
        assert s0.xz is None

    # 公共查询必须看不到 excluded
    search = await client.get("/api/v1/jobs/search", params={"cycle": "2026"})
    assert search.json()["total"] == 2
    assert (await client.get(f"/api/v1/jobs/{j2}")).status_code == 404
    by_city = (await client.get("/api/v1/jobs/stats/by-city", params={"cycle": "2026"})).json()
    assert sum(by_city.values()) == 2

    # 第 3 次：job2 重新出现在快照（无 record_status 字段）→ 必须自动恢复 active
    p3 = _payload(3)
    r3 = await _import(client, headers, p3)
    assert r3.status_code == 200, r3.text
    assert r3.json()["deactivated"] == 0
    async with get_test_session_factory()() as session:
        s2b = (await session.execute(select(Job).where(Job.job_id == j2))).scalar_one()
        assert s2b.record_status == "active"

    search2 = await client.get("/api/v1/jobs/search", params={"cycle": "2026"})
    assert search2.json()["total"] == 3
