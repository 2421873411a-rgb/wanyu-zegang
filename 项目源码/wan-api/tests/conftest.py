"""wan-api 测试套件（v17.9.1 S3：门禁式——下面场景锁死，进 main 前必须全绿）。

覆盖用户定义的门禁场景：
1. 普通用户绝不能自注册成 admin（含 ADMIN_EMAIL 命中）
2. 默认 SECRET_KEY 不允许生产启动
3. refresh 不接受 query token（只走 JSON body）
4. 重复收藏/对比必须数据库拒绝（UNIQUE 兜底）
5. 对比列表永远 ≤4（func.count 路径可用，回归 NameError 修复）
6. 管理员导入：结构不符/非法周期必须失败，成功必须真实写库且行数对账
7. 最后管理员不能被降权/禁用
8. 超大 JSON upload 返回 413
9. refresh 轮换/重用检测/登出（family 撤销）
"""
import asyncio
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import *  # noqa: F401,F403 — 注册全部模型进 metadata
from app.models.user import User
from app.utils import rate_limit as rate_limit_module
from app.config import settings

import os
import tempfile

_test_engine = None
_TestSessionFactory = None


def get_test_session_factory():
    """测试期会话工厂访问器（fixture 在导入后才赋值全局，须走函数取）"""
    return _TestSessionFactory


def _make_engine():
    # CI postgres job 传 DATABASE_URL=postgresql+asyncpg://... 时直接用 PostgreSQL；
    # 本地/SQLite CI 不传或传 sqlite 时用临时文件 SQLite。
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
    global _test_engine, _TestSessionFactory
    _test_engine, _path = _make_engine()
    _TestSessionFactory = async_sessionmaker(_test_engine, expire_on_commit=False)
    # PG 共享库：每个测试前清表再重建（SQLite 每次新文件，PG 需要手动清理）
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
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
            pass  # Windows：aiosqlite 连接释放晚于 dispose，临时文件交给 %TEMP% 清理


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


_valid_password = "abc1234567"


async def _register(client: AsyncClient, email: str = "u1@example.com", username: str = "u1", password: str = None) -> dict:
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
        user = User(email=email, username=username, password_hash=get_password_hash(_valid_password), is_admin=True)
        session.add(user)
        await session.commit()
        return {"email": email, "password": _valid_password}


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
