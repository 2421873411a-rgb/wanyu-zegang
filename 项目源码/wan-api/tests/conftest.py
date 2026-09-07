"""wan-api 门禁测试公共 fixture。

SQLite job 每个用例使用独立临时库；PostgreSQL job 直接使用 CI 提供的
DATABASE_URL，并在每个用例前 TRUNCATE 全部业务表。这样既保留 Alembic
创建的真实 PostgreSQL schema，又保证用例之间严格隔离。
"""
from typing import AsyncIterator

import os
import tempfile

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import *  # noqa: F401,F403 — 注册全部模型进 metadata
from app.models.user import User
from app.utils import rate_limit as rate_limit_module

_test_engine = None
_TestSessionFactory = None


def get_test_session_factory():
    """测试期会话工厂访问器。"""
    return _TestSessionFactory


def using_postgres() -> bool:
    """当前测试是否运行在真实 PostgreSQL。"""
    return os.environ.get("DATABASE_URL", "").startswith("postgresql")


def _make_engine():
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("postgresql"):
        return create_async_engine(db_url), None
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return create_async_engine(f"sqlite+aiosqlite:///{path}"), path


@pytest.fixture(autouse=True)
def _reset_limiters():
    rate_limit_module.login_limiter.reset()
    rate_limit_module.register_limiter.reset()
    yield
    rate_limit_module.login_limiter.reset()
    rate_limit_module.register_limiter.reset()


@pytest_asyncio.fixture(autouse=True)
async def _db() -> AsyncIterator[None]:
    """每个用例使用干净数据；PG 不重建 schema，确保验证 Alembic 产物。"""
    global _test_engine, _TestSessionFactory
    _test_engine, _path = _make_engine()
    _TestSessionFactory = async_sessionmaker(_test_engine, expire_on_commit=False)

    async with _test_engine.begin() as conn:
        if using_postgres():
            # PostgreSQL job 在 pytest 前已经 alembic upgrade head。
            # 这里只清业务数据，不 drop/create，避免测试绕过迁移 schema。
            table_names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
            if table_names:
                await conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
        else:
            await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with _TestSessionFactory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    await _test_engine.dispose()
    if _path:
        try:
            os.remove(_path)
        except PermissionError:
            pass


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


_valid_password = "abc1234567"


async def _register(
    client: AsyncClient,
    email: str = "u1@example.com",
    username: str = "u1",
    password: str | None = None,
) -> dict:
    resp = await client.post("/api/v1/auth/register", json={
        "email": email,
        "username": username,
        "password": password or _valid_password,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _make_admin(email: str = "admin@example.com", username: str = "admin1") -> dict:
    """直接在库里造一个管理员（模拟 CLI 引导后的状态）。"""
    from app.utils.security import get_password_hash

    async with _TestSessionFactory() as session:
        user = User(
            email=email,
            username=username,
            password_hash=get_password_hash(_valid_password),
            is_admin=True,
        )
        session.add(user)
        await session.commit()
        return {"email": email, "password": _valid_password}


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
