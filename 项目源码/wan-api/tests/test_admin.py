"""门禁场景 6/7/8：管理员导入真实性、最后管理员保护、超大上传 413。"""
import json

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.job import Job
from app.models.user import User

from tests.conftest import get_test_session_factory, _auth, _login, _make_admin, _register

pytestmark = pytest.mark.asyncio


def _payload(n: int = 3) -> dict:
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
    } for i in range(n)]
    return {"allMajors": {"meta": {"total": n, "recruits": n * 2}, "rows": rows}}


async def _admin_headers(client: AsyncClient) -> dict:
    await _make_admin()
    data = await _login(client, "admin@example.com", "abc1234567")
    return _auth(data["access_token"])


async def test_non_admin_cannot_access_admin(client: AsyncClient):
    data = await _register(client)
    r = await client.get("/api/v1/admin/dashboard", headers=_auth(data["access_token"]))
    assert r.status_code == 403
    r2 = await client.get("/api/v1/admin/users")
    assert r2.status_code in (401, 403)


async def test_import_writes_rows_and_reconciles(client: AsyncClient):
    """门禁6：导入必须真实写库——旧实现假成功已删除；响应含对账统计。"""
    headers = await _admin_headers(client)
    payload = _payload(3)
    r = await client.post("/api/v1/admin/import/2026", headers=headers,
                          files={"file": ("jobs.json", json.dumps(payload).encode(), "application/json")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_total"] == 3
    assert body["imported"] == 3
    assert body["imported"] + body["updated"] + body["skipped"] == body["rows_total"]
    assert len(body["source_sha256"]) == 64

    # 数据库真实存在这 3 行
    async with get_test_session_factory()() as session:
        count = (await session.execute(select(func.count(Job.id)).where(Job.cycle == "2026"))).scalar()
        assert count == 3


async def test_import_rejects_bad_structure_and_cycle(client: AsyncClient):
    """门禁6b：结构不符/非法周期必须失败（绝不假成功）。"""
    headers = await _admin_headers(client)
    r1 = await client.post("/api/v1/admin/import/2026", headers=headers,
                           files={"file": ("jobs.json", b'{"hello": 1}', "application/json")})
    assert r1.status_code == 400
    r2 = await client.post("/api/v1/admin/import/1999", headers=headers,
                           files={"file": ("jobs.json", json.dumps(_payload(1)).encode(), "application/json")})
    assert r2.status_code == 400
    r3 = await client.post("/api/v1/admin/import/2026", headers=headers,
                           files={"file": ("jobs.json", b"not json", "application/json")})
    assert r3.status_code == 400
    # 确认没有数据被写入（事务干净）
    async with get_test_session_factory()() as session:
        count = (await session.execute(select(func.count(Job.id)))).scalar()
        assert count == 0


async def test_import_oversize_returns_413(client: AsyncClient, monkeypatch):
    """门禁8：超大 JSON upload 返回 413。"""
    from app.config import settings
    monkeypatch.setattr(settings, "ADMIN_IMPORT_MAX_BYTES", 1024)
    headers = await _admin_headers(client)
    big = _payload(2000)
    r = await client.post("/api/v1/admin/import/2026", headers=headers,
                          files={"file": ("jobs.json", json.dumps(big).encode(), "application/json")})
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
