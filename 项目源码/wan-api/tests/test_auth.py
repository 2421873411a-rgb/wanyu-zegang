"""认证门禁：注册权限、生产秘密、refresh 形态、轮换、限流和 bcrypt 兼容。"""
import pytest
from httpx import AsyncClient

from app.config import Settings, _validate_production_safety, settings
from tests.conftest import _auth, _login, _register, _valid_password

pytestmark = pytest.mark.asyncio


async def test_admin_email_register_creates_normal_user(client: AsyncClient):
    settings.ADMIN_EMAIL = "boss@kaogong.art"
    data = await _register(client, email="boss@kaogong.art", username="boss")
    assert data["user"]["is_admin"] is False
    me = await client.get("/api/v1/auth/me", headers=_auth(data["access_token"]))
    assert me.status_code == 200
    assert me.json()["is_admin"] is False


async def test_register_duplicate_email_and_username(client: AsyncClient):
    await _register(client, email="dup@example.com", username="dup")
    r1 = await client.post("/api/v1/auth/register", json={
        "email": "dup@example.com", "username": "other", "password": _valid_password})
    assert r1.status_code == 400
    r2 = await client.post("/api/v1/auth/register", json={
        "email": "other@example.com", "username": "dup", "password": _valid_password})
    assert r2.status_code == 400


async def test_password_policy_enforced(client: AsyncClient):
    for bad in ("short1a", "abcdefghij", "1234567890"):
        r = await client.post("/api/v1/auth/register", json={
            "email": f"p{bad[:3]}@example.com", "username": f"p{bad[:3]}", "password": bad})
        assert r.status_code == 422, f"密码 {bad!r} 应被拒绝"
    r = await client.post("/api/v1/auth/register", json={
        "email": "good@example.com", "username": "good", "password": _valid_password})
    assert r.status_code == 201


async def test_production_rejects_default_secret_key():
    """保持 async 形态，避免模块级 pytest.mark.asyncio 对同步测试产生噪声。"""
    with pytest.raises(RuntimeError):
        _validate_production_safety(Settings(_env_file=None, ENV="production"))
    _validate_production_safety(Settings(
        _env_file=None, ENV="production", SECRET_KEY="a" * 64))


async def test_refresh_does_not_accept_query_token(client: AsyncClient):
    data = await _register(client)
    r = await client.post(f"/api/v1/auth/refresh?refresh_token={data['refresh_token']}")
    assert r.status_code in (401, 422)
    assert r.status_code != 200


async def test_refresh_rotation_and_reuse_detection(client: AsyncClient):
    data = await _register(client)
    old_refresh = data["refresh_token"]
    r1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r1.status_code == 200
    new_refresh = r1.json()["refresh_token"]
    r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert r2.status_code == 200
    newest_refresh = r2.json()["refresh_token"]
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})).status_code == 401
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": newest_refresh})).status_code == 401


async def test_logout_revokes_family(client: AsyncClient):
    data = await _register(client)
    assert (await client.post(
        "/api/v1/auth/logout", json={"refresh_token": data["refresh_token"]}
    )).status_code == 204
    assert (await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]}
    )).status_code == 401


async def test_login_rate_limited(client: AsyncClient):
    await _register(client, email="rl@example.com", username="rl")
    for _ in range(5):
        bad = await client.post("/api/v1/auth/login", json={
            "email": "rl@example.com", "password": "wrongwrong12"})
        assert bad.status_code == 401
    sixth = await client.post("/api/v1/auth/login", json={
        "email": "rl@example.com", "password": "wrongwrong12"})
    assert sixth.status_code == 429
    blocked = await client.post("/api/v1/auth/login", json={
        "email": "rl@example.com", "password": _valid_password})
    assert blocked.status_code == 429


async def test_me_requires_bearer(client: AsyncClient):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code in (401, 403)


async def test_legacy_bcrypt_rehash_on_login(client: AsyncClient):
    from passlib.context import CryptContext
    from sqlalchemy import select

    from app.models.user import User
    from tests.conftest import get_test_session_factory

    await _register(client, email="legacy@example.com", username="legacy")
    async with get_test_session_factory()() as session:
        user = (await session.execute(
            select(User).where(User.email == "legacy@example.com")
        )).scalar_one()
        old_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        user.password_hash = old_ctx.hash(_valid_password)
        assert user.password_hash.startswith("$2b$")
        await session.commit()

    login_data = await _login(client, "legacy@example.com", _valid_password)
    assert "access_token" in login_data

    async with get_test_session_factory()() as session:
        user = (await session.execute(
            select(User).where(User.email == "legacy@example.com")
        )).scalar_one()
        assert user.password_hash.startswith("$bcrypt-sha256$"), f"未 rehash: {user.password_hash[:30]}"
