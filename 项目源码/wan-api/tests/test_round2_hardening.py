"""v17.9.12 Round-2 加固回归门禁。

覆盖 Round-2 三镜头审计的确认发现：
- P0 用户筛选快照端点（写/读/删除 + 上限）
- P1 登录限流并发竞态（20 并发错密码 ≤5 过）
- P1 SECRET_KEY 门禁矩阵
- P2 乐观锁 refresh 轮换（SQLite 不再双花）/ LIKE 通配符转义 / page 溢出 /
  控制字符 422 / salary 零值 / RecursionError 400 / 邮箱归一
"""
import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.models.job import Job
from app.models.salary_data import SalaryData
from app.utils import rate_limit as rl

from tests.conftest import (
    get_test_session_factory,
    _auth,
    _register,
    _seed_jobs,
)
from tests.test_admin import _admin_headers, _import, _payload, _row

pytestmark = pytest.mark.asyncio


# ============ P1 登录限流原子化 ============

async def test_concurrent_wrong_password_logins_cannot_race_through(client: AsyncClient):
    """审计 T1 红绿对照：修复前 20/20 全穿透；修复后 ≤5 个 401，其余 429。"""
    await _register(client)
    payload = {"email": "u1@example.com", "password": "wrong-password-1"}

    async def attempt():
        async with AsyncClient(transport=ASGITransport(app=client._transport.app),
                               base_url="http://test") as c:
            return (await c.post("/api/v1/auth/login", json=payload)).status_code

    results = await asyncio.gather(*(attempt() for _ in range(20)))
    from collections import Counter
    dist = Counter(results)
    assert dist.get(401, 0) <= 5, f"并发穿透仍存在：{dist}"
    assert dist.get(429, 0) >= 15, f"限流未生效：{dist}"


async def test_unknown_user_login_still_costs_bcrypt(monkeypatch):
    """时序侧信道：未知邮箱也必须执行一次 bcrypt（调用计数断言）。"""
    from app.api.v1 import auth as auth_mod
    calls = {"n": 0}
    real_verify = auth_mod.verify_password

    def counting_verify(plain, hashed):
        calls["n"] += 1
        return real_verify(plain, hashed)

    monkeypatch.setattr(auth_mod, "verify_password", counting_verify)
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/auth/login",
                         json={"email": "nobody@example.com", "password": "whatever123"})
    assert r.status_code == 401
    assert calls["n"] >= 1, "未知用户未执行哑 bcrypt——时序侧信道回归"


# ============ P1 SECRET_KEY 门禁矩阵 ============

async def test_secret_key_gate_matrix():
    """SECRET_KEY 门禁矩阵（module 级 asyncio mark：本测试无 await，语义不变）。"""
    from app.config import Settings, _validate_production_safety

    # 非测试环境缺失 → 拒启（含模糊 test 写法：' TEST '/'Test' 不享受豁免——RA-5）
    for env in ("dev", "production", "staging", "Production", " TEST ", "Test", "TEST"):
        with pytest.raises(RuntimeError):
            _validate_production_safety(Settings(ENV=env, SECRET_KEY=""))
    # 公开测试密钥在正式环境 → 拒启（RA-4：该值已随公开仓库扩散）
    with pytest.raises(RuntimeError):
        _validate_production_safety(
            Settings(ENV="production", SECRET_KEY="wanyu-test-only-secret-key-0123456789abcdef"))
    # 公开默认值 → 拒启（无论环境）
    with pytest.raises(RuntimeError):
        _validate_production_safety(Settings(ENV="dev", SECRET_KEY="your-secret-key-change-in-production"))
    # 弱密钥（<32 字符）在任何正式环境 → 拒启（审计 T2：'secret' 曾在生产放行）
    with pytest.raises(RuntimeError):
        _validate_production_safety(Settings(ENV="production", SECRET_KEY="secret"))
    # 足够长的随机密钥 → 通过
    _validate_production_safety(Settings(ENV="production", SECRET_KEY="a" * 64))


# ============ P0 用户筛选快照端点 ============

async def test_snapshot_crud_roundtrip_with_unicode_filters(client: AsyncClient):
    """P0 回归：修复前 POST/GET 双向 500。"""
    data = await _register(client)
    headers = _auth(data["access_token"])
    filters = {"city": "合肥", "exam": "省考", "薪资≥10": True, "nested": {"a": [1, 2]}}
    r = await client.post("/api/v1/user/snapshots", headers=headers,
                          json={"cycle": "2026", "view": "table", "filters": filters})
    assert r.status_code == 201, r.text
    assert r.json()["filters"] == filters

    g = await client.get("/api/v1/user/snapshots", headers=headers)
    assert g.status_code == 200
    items = g.json()
    assert len(items) == 1
    assert items[0]["filters"] == filters

    d = await client.delete(f"/api/v1/user/snapshots/{items[0]['id']}", headers=headers)
    assert d.status_code == 204
    g2 = await client.get("/api/v1/user/snapshots", headers=headers)
    assert g2.json() == []


async def test_snapshot_oversize_filters_rejected(client: AsyncClient):
    data = await _register(client)
    headers = _auth(data["access_token"])
    big = {"k": "x" * (33 * 1024)}
    r = await client.post("/api/v1/user/snapshots", headers=headers,
                          json={"cycle": "2026", "view": "table", "filters": big})
    assert r.status_code == 400
    assert "32KB" in r.json()["detail"]


async def test_snapshot_count_limit_50(client: AsyncClient):
    data = await _register(client)
    headers = _auth(data["access_token"])
    for i in range(50):
        r = await client.post("/api/v1/user/snapshots", headers=headers,
                              json={"cycle": "2026", "view": "table",
                                    "filters": {"i": i}})
        assert r.status_code == 201, (i, r.text)
    r51 = await client.post("/api/v1/user/snapshots", headers=headers,
                            json={"cycle": "2026", "view": "table", "filters": {"i": 51}})
    assert r51.status_code == 400
    assert "上限" in r51.json()["detail"]


# ============ refresh 乐观锁（SQLite 并发双花封死） ============

async def test_concurrent_refresh_same_token_no_double_spend(client: AsyncClient):
    data = await _register(client)
    old_refresh = data["refresh_token"]

    async def rotate():
        async with AsyncClient(transport=ASGITransport(app=client._transport.app),
                               base_url="http://test") as c:
            return (await c.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})).status_code

    results = await asyncio.gather(rotate(), rotate())
    assert sorted(results) == [200, 401], f"SQLite 下并发轮换仍双花：{results}"


# ============ LIKE 通配符转义 / 控制字符 / page 溢出 ============

async def test_like_wildcards_escaped_in_search(client: AsyncClient):
    (real,) = await _seed_jobs(1)
    for evil in ("%", "%%", "测试单位_", "' OR 1=1 --"):
        r = await client.get("/api/v1/jobs/search", params={"keyword": evil})
        assert r.status_code == 200
        assert r.json()["total"] == 0, f"keyword={evil!r} 通配符未转义"


async def test_control_char_and_page_overflow_rejected(client: AsyncClient):
    r1 = await client.get("/api/v1/jobs/search", params={"keyword": "a\x00b"})
    assert r1.status_code == 422
    r2 = await client.get("/api/v1/jobs/search", params={"page": 10 ** 18})
    assert r2.status_code == 422


# ============ salary 零值不冒充未知 ============

async def test_salary_zero_value_preserved(client: AsyncClient):
    async with get_test_session_factory()() as session:
        session.add(SalaryData(city="合肥", employment_type="公务员", stage="3年",
                               value_wan=0, snapshot_year="2026"))
        await session.commit()
    r = await client.get("/api/v1/salary")
    assert r.status_code == 200
    assert r.json()["合肥"]["公务员"]["3年"] == 0.0


# ============ admin 导入深嵌套 JSON → 400 ============

async def test_deep_nested_json_import_returns_400(client: AsyncClient):
    from tests.conftest import _login, _make_admin
    await _make_admin()
    data = await _login(client, "admin@example.com", "abc1234567")
    headers = _auth(data["access_token"])
    r = await client.post("/api/v1/admin/import/2026", headers=headers,
                          files={"file": ("jobs.json", b"[" * 100000, "application/json")})
    assert r.status_code == 400, f"深嵌套 JSON 应 400 而非 {r.status_code}"


# ============ 邮箱归一 ============

async def test_email_normalized_to_lowercase(client: AsyncClient):
    data = await _register(client, email="MixedCase@EXAMPLE.com", username="mix1")
    r = await client.post("/api/v1/auth/login",
                          json={"email": "mixedcase@example.com", "password": "abc1234567"})
    assert r.status_code == 200, "邮箱大小写未归一，登录失败"


# ============ stats 缓存一致性 ============

async def test_stats_cache_consistent(client: AsyncClient):
    await _seed_jobs(2)
    a = (await client.get("/api/v1/jobs/stats/by-city", params={"cycle": "2026"})).json()
    b = (await client.get("/api/v1/jobs/stats/by-city", params={"cycle": "2026"})).json()
    assert a == b and sum(a.values()) == 2


# ============ Round-3 复审回归（escape 正向匹配 / stats 失效 / 在场排除级联 / bm 校验） ============

async def test_like_escape_preserves_literal_percent_underscore(client: AsyncClient):
    """Round-3 P1 正向门禁：转义不得破坏字面量匹配（此前只测了 total==0 反向）。"""
    async with get_test_session_factory()() as session:
        session.add(Job(job_id="job-2026-aaaaaaaaaaaaaaaa0001", cycle="2026", code="90001",
                        city="合肥", exam="省考", unit="价格50%上限岗", zw="x", zy="法学",
                        num=1, record_status="active"))
        session.add(Job(job_id="job-2026-aaaaaaaaaaaaaaaa0002", cycle="2026", code="90002",
                        city="合肥", exam="省考", unit="本科_定向岗", zw="x", zy="法学",
                        num=1, record_status="active"))
        await session.commit()
    r1 = await client.get("/api/v1/jobs/search", params={"keyword": "50%"})
    assert r1.status_code == 200 and r1.json()["total"] >= 1, "字面量 % 被转义破坏"
    r2 = await client.get("/api/v1/jobs/search", params={"keyword": "本科_"})
    assert r2.status_code == 200 and r2.json()["total"] >= 1, "字面量 _ 被转义破坏"
    # 语义修正（Round-3）：转义后 keyword='%' 表示"匹配含字面 % 的行"——
    # 种子中恰有一行（价格50%上限岗），应命中它而不是返回 0
    r3 = await client.get("/api/v1/jobs/search", params={"keyword": "%"})
    assert r3.json()["total"] == 1, "字面 % 搜索应命中含 % 的行"


async def test_stats_cache_invalidated_after_import(client: AsyncClient):
    """Round-3 P2：admin 导入后 stats 必须立即可见新数据（不允许 60s 脏读）。"""
    from tests.conftest import _login, _make_admin
    await _make_admin()
    data = await _login(client, "admin@example.com", "abc1234567")
    headers = _auth(data["access_token"])

    def payload(city):
        rows = [dict(job_id=f"job-2026-{'b'*17}{1:03d}", row_id=f"job-2026-{'b'*17}{1:03d}",
                     code="1", city=city, exam="省考", unit="u", zw="z", zy="法学", num=1)]
        return {"allMajors": {"meta": {"total": 1, "raw_total": 1, "excluded": 0, "recruits": 1},
                               "rows": rows}, "cycle": "2026"}

    r1 = await client.post("/api/v1/admin/import/2026", headers=headers,
                           files={"file": ("j.json", json.dumps(payload("合肥")).encode(), "application/json")})
    assert r1.status_code == 200, r1.text
    stats1 = (await client.get("/api/v1/jobs/stats/by-city", params={"cycle": "2026"})).json()
    assert stats1.get("合肥") == 1

    r2 = await client.post("/api/v1/admin/import/2026", headers=headers,
                           files={"file": ("j.json", json.dumps(payload("芜湖")).encode(), "application/json")})
    assert r2.status_code == 200
    stats2 = (await client.get("/api/v1/jobs/stats/by-city", params={"cycle": "2026"})).json()
    assert stats2.get("芜湖") == 1 and "合肥" not in stats2, f"stats 未随导入失效：{stats2}"


async def test_incoming_excluded_row_cascades_ghost_references(client: AsyncClient):
    """Round-3 P2：快照'在场但被标记排除'的岗位同样要清理收藏/对比幽灵引用。"""
    from app.models.saved_position import SavedPosition

    from tests.conftest import _seed_jobs
    headers = await _admin_headers(client)
    data = await _register(client)
    (real,) = await _seed_jobs(1)
    await client.post("/api/v1/user/positions", headers=_auth(data["access_token"]),
                      json={"record_id": real, "cycle": "2026"})

    from app.services.import_service import _job_id_set_sha256
    rows = [dict(_row("2026", 99), record_status="withdrawn",
                 exclusion_reason="r", exclusion_evidence="e", excluded_at="d")]
    payload = {"cycle": "2026",
               "all_majors": {"meta": {"total": 1, "raw_total": 1, "excluded": 1, "recruits": 2},
                               "rows": rows},
               "provenance": {"job_id_set_sha256": _job_id_set_sha256([r["job_id"] for r in rows])}}
    r = await client.post("/api/v1/admin/import/2026", headers=headers,
                          files={"file": ("j.json", json.dumps(payload).encode(), "application/json")})
    assert r.status_code == 200, r.text
    async with get_test_session_factory()() as session:
        left = (await session.execute(
            select(SavedPosition).where(SavedPosition.record_id == real))).scalar_one_or_none()
        assert left is None, "在场排除行的收藏引用未被级联清理"


async def test_float_bm_rejected(client: AsyncClient):
    """Round-3 P2：bm 浮点与 num 同罪——拒绝而非静默 NULL。"""
    headers = await _admin_headers(client)
    payload = _payload(1)
    payload["allMajors"]["rows"][0]["bm"] = 3.7
    r = await _import(client, headers, payload)
    assert r.status_code == 400
    assert "bm" in r.json()["detail"]
