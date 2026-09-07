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

    # 非测试环境缺失 → 拒启
    for env in ("dev", "production", "staging", "Production"):
        with pytest.raises(RuntimeError):
            _validate_production_safety(Settings(ENV=env, SECRET_KEY=""))
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
