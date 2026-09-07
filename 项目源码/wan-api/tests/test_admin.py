"""管理员门禁：权限、快照导入、事务、最后管理员、上传上限。"""
import json

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.job import Job
from app.models.user import User
from tests.conftest import _auth, _login, _make_admin, _register, get_test_session_factory

pytestmark = pytest.mark.asyncio


def _payload(n: int = 3, canonical: bool = False) -> dict:
    rows = [{
        "job_id": f"job-test-{i:04d}",
        "code": f"1{i:05d}",
        "city": "合肥",
        "exam": "省考",
        "unit": "测试单位",
        "zw": "测试职位",
        "zy": "法学",
        "num": 2,
        "xl": "本科及以上",
        "xz": "不限",
        "title_status": "verified",
        "display_title": f"测试职位{i}",
        "record_status": "active",
        "score_observation": {"status": "observed", "scale_id": "s1", "value": 70 + i},
        "competition_observations": {"metric_type": "signup", "base": 10 + i, "source": "official"},
        "ratio_comparable": True,
        "source": {"url": f"https://example.test/{i}"},
    } for i in range(n)]
    key = "all_majors" if canonical else "allMajors"
    return {key: {"meta": {"total": n, "recruits": n * 2}, "rows": rows}}


async def _admin_headers(client: AsyncClient) -> dict:
    await _make_admin()
    return _auth((await _login(client, "admin@example.com", "abc1234567"))["access_token"])


async def test_non_admin_cannot_access_admin(client: AsyncClient):
    data = await _register(client)
    assert (await client.get("/api/v1/admin/dashboard", headers=_auth(data["access_token"]))).status_code == 403
    assert (await client.get("/api/v1/admin/users")).status_code in (401, 403)


async def test_import_writes_rows_and_reconciles(client: AsyncClient):
    headers = await _admin_headers(client)
    r = await client.post(
        "/api/v1/admin/import/2026",
        headers=headers,
        files={"file": ("jobs.json", json.dumps(_payload(3)).encode(), "application/json")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_total"] == 3
    assert body["imported"] == 3
    assert body["deleted"] == 0
    assert body["imported"] + body["updated"] + body["skipped"] == 3
    assert len(body["source_sha256"]) == 64
    async with get_test_session_factory()() as session:
        assert (await session.execute(select(func.count(Job.id)).where(Job.cycle == "2026"))).scalar() == 3


async def test_canonical_shape_full_field_update_and_stale_delete(client: AsyncClient):
    """正式 all_majors 结构可直接重建镜像；旧字段和旧行不能残留。"""
    headers = await _admin_headers(client)
    first = _payload(3, canonical=True)
    r1 = await client.post(
        "/api/v1/admin/import/2026", headers=headers,
        files={"file": ("canonical.json", json.dumps(first).encode(), "application/json")},
    )
    assert r1.status_code == 200, r1.text

    second = _payload(2, canonical=True)
    row0 = second["all_majors"]["rows"][0]
    row0.update({
        "xz": "中共党员",
        "title_status": "corrected",
        "display_title": "修订职位",
        "ratio_comparable": False,
        "source": {"url": "https://example.test/revised"},
    })
    row0["score_observation"] = {"status": "unresolved", "scale_id": "s2", "value": None}
    row0["competition_observations"] = {"metric_type": "pay", "base": 99, "source": "official-v2"}
    r2 = await client.post(
        "/api/v1/admin/import/2026", headers=headers,
        files={"file": ("canonical.json", json.dumps(second).encode(), "application/json")},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["deleted"] == 1

    async with get_test_session_factory()() as session:
        jobs = (await session.execute(select(Job).where(Job.cycle == "2026").order_by(Job.job_id))).scalars().all()
        assert len(jobs) == 2
        changed = jobs[0]
        assert changed.xz == "中共党员"
        assert changed.title_status == "corrected"
        assert changed.display_title == "修订职位"
        assert changed.score_observation_status == "unresolved"
        assert changed.score_observation_scale_id == "s2"
        assert changed.competition_metric_type == "pay"
        assert changed.competition_base == 99
        assert changed.competition_source == "official-v2"
        assert changed.ratio_comparable is False
        assert changed.source["url"].endswith("/revised")


async def test_import_rejects_bad_structure_and_cycle(client: AsyncClient):
    headers = await _admin_headers(client)
    assert (await client.post(
        "/api/v1/admin/import/2026", headers=headers,
        files={"file": ("jobs.json", b'{"hello": 1}', "application/json")},
    )).status_code == 400
    assert (await client.post(
        "/api/v1/admin/import/1999", headers=headers,
        files={"file": ("jobs.json", json.dumps(_payload(1)).encode(), "application/json")},
    )).status_code == 400
    assert (await client.post(
        "/api/v1/admin/import/2026", headers=headers,
        files={"file": ("jobs.json", b"not json", "application/json")},
    )).status_code == 400
    async with get_test_session_factory()() as session:
        assert (await session.execute(select(func.count(Job.id)))).scalar() == 0


async def test_import_oversize_returns_413(client: AsyncClient, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ADMIN_IMPORT_MAX_BYTES", 1024)
    headers = await _admin_headers(client)
    r = await client.post(
        "/api/v1/admin/import/2026", headers=headers,
        files={"file": ("jobs.json", json.dumps(_payload(2000)).encode(), "application/json")},
    )
    assert r.status_code == 413, r.text


async def test_last_admin_cannot_be_demoted_or_disabled(client: AsyncClient):
    headers = await _admin_headers(client)
    async with get_test_session_factory()() as session:
        admin_id = (await session.execute(select(User).where(User.email == "admin@example.com"))).scalar_one().id
    assert (await client.put(f"/api/v1/admin/users/{admin_id}?is_admin=false", headers=headers)).status_code == 400
    assert (await client.put(f"/api/v1/admin/users/{admin_id}?is_active=false", headers=headers)).status_code == 400
    assert (await client.put(f"/api/v1/admin/users/{admin_id}?is_admin=true", headers=headers)).status_code == 200
    await _make_admin(email="admin2@example.com", username="admin2")
    assert (await client.put(f"/api/v1/admin/users/{admin_id}?is_admin=false", headers=headers)).status_code == 200


async def test_register_cannot_reach_admin_endpoints_even_with_admin_email(client: AsyncClient):
    from app.config import settings

    settings.ADMIN_EMAIL = "sneaky@kaogong.art"
    data = await _register(client, email="sneaky@kaogong.art", username="sneaky")
    for path in ("/api/v1/admin/dashboard", "/api/v1/admin/users"):
        assert (await client.get(path, headers=_auth(data["access_token"]))).status_code == 403
