"""门禁场景 1/2/3/9：注册权限模型、生产秘密门、refresh 形态与轮换。"""
import pytest
from httpx import AsyncClient

from app.config import Settings, _validate_production_safety, settings

from tests.conftest import _auth, _login, _make_admin, _register, _valid_password

pytestmark = pytest.mark.asyncio


async def test_admin_email_register_creates_normal_user(client: AsyncClient):
    """门禁1：用 ADMIN_EMAIL 注册必须得到普通用户（抢注册路径已封死）。"""
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
    """门禁补充：密码策略（<10 位 / 纯字母 / 纯数字 → 422）。"""
    for bad in ("short1a", "abcdefghij", "1234567890"):
        r = await client.post("/api/v1/auth/register", json={
            "email": f"p{bad[:3]}@example.com", "username": f"p{bad[:3]}", "password": bad})
        assert r.status_code == 422, f"密码 {bad!r} 应被拒绝"
    r = await client.post("/api/v1/auth/register", json={
        "email": "good@example.com", "username": "good", "password": _valid_password})
    assert r.status_code == 201


def test_production_rejects_default_secret_key():
    """门禁2：ENV=production + 已知默认 SECRET_KEY → 拒绝启动。"""
    with pytest.raises(RuntimeError):
        _validate_production_safety(Settings(_env_file=None, ENV="production"))
    # 正确配置不应抛错
    _validate_production_safety(Settings(
        _env_file=None, ENV="production", SECRET_KEY="a" * 64))


async def test_refresh_does_not_accept_query_token(client: AsyncClient):
    """门禁3：refresh token 走 JSON body；旧 query 形态绝不放行。"""
    data = await _register(client)
    # 旧攻击/误用形态：token 放 query，body 为空 → 必须 4xx
    r = await client.post(f"/api/v1/auth/refresh?refresh_token={data['refresh_token']}")
    assert r.status_code in (401, 422)
    assert r.status_code != 200


async def test_refresh_rotation_and_reuse_detection(client: AsyncClient):
    """门禁9：轮换后旧 token 失效；重用旧 token 触发 family 全撤销。"""
    data = await _register(client)
    old_refresh = data["refresh_token"]

    r1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r1.status_code == 200
    new_refresh = r1.json()["refresh_token"]

    # 轮换后新 token 可用
    r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert r2.status_code == 200
    newest_refresh = r2.json()["refresh_token"]

    # 重用已轮换的旧 token → 401，且 family 全撤销
    r3 = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r3.status_code == 401

    # 同族最新的 token 也已被连带撤销
    r4 = await client.post("/api/v1/auth/refresh", json={"refresh_token": newest_refresh})
    assert r4.status_code == 401


async def test_logout_revokes_family(client: AsyncClient):
    data = await _register(client)
    r = await client.post("/api/v1/auth/logout", json={"refresh_token": data["refresh_token"]})
    assert r.status_code == 204
    r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert r2.status_code == 401


async def test_login_rate_limited(client: AsyncClient):
    """登录限流：同 IP+账号 5 次失败后 → 429。"""
    await _register(client, email="rl@example.com", username="rl")
    for _ in range(5):
        bad = await client.post("/api/v1/auth/login", json={
            "email": "rl@example.com", "password": "wrongwrong12"})
        assert bad.status_code == 401
    sixth = await client.post("/api/v1/auth/login", json={
        "email": "rl@example.com", "password": "wrongwrong12"})
    assert sixth.status_code == 429
    # 正确密码在限流窗口内也被拒（防爆破窗口不因密码正确而重置计数）
    blocked = await client.post("/api/v1/auth/login", json={
        "email": "rl@example.com", "password": _valid_password})
    assert blocked.status_code == 429


async def test_me_requires_bearer(client: AsyncClient):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code in (401, 403)


async def test_legacy_bcrypt_rehash_on_login(client: AsyncClient):
    """bcrypt 兼容：旧 $2b$ hash 登录成功后自动 rehash 为 bcrypt_sha256。"""
    from sqlalchemy import select
    from app.models.user import User
    from app.utils.security import pwd_context
    from tests.conftest import get_test_session_factory

    # 注册用户
    data = await _register(client, email="legacy@example.com", username="legacy")
    # 伪造旧 bcrypt hash（覆盖 DB 中的 bcrypt_sha256 hash）
    async with get_test_session_factory()() as session:
        result = await session.execute(select(User).where(User.email == "legacy@example.com"))
        user = result.scalar_one()
        old_hash = pwd_context.hash(_valid_password)
        # 确认是 bcrypt_sha256 hash（以 $bcrypt-sha256$ 开头）
        assert user.password_hash.startswith("$bcrypt-sha256$") or user.password_hash.startswith("$2b$")
        # 强制改为普通 bcrypt hash
        from passlib.context import CryptContext
        old_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        user.password_hash = old_ctx.hash(_valid_password)
        assert user.password_hash.startswith("$2b$")
        await session.commit()

    # 登录（旧 bcrypt hash 应该能验证成功）
    login_data = await _login(client, "legacy@example.com", _valid_password)
    assert "access_token" in login_data

    # 验证 hash 已被 rehash 为 bcrypt_sha256
    async with get_test_session_factory()() as session:
        result = await session.execute(select(User).where(User.email == "legacy@example.com"))
        user = result.scalar_one()
        assert user.password_hash.startswith("$bcrypt-sha256$"), f"未 rehash: {user.password_hash[:30]}"
