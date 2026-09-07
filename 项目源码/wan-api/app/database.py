from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


# 创建异步引擎
# v17.9.1 S1：SQLite（aiosqlite/NullPool）不接受 pool_size/max_overflow，
# 池参数仅对 PostgreSQL 等队列池后端传入——否则默认开发配置在导入即崩。
def _build_engine():
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        return create_async_engine(url, echo=settings.DATABASE_ECHO)
    return create_async_engine(
        url,
        echo=settings.DATABASE_ECHO,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )


engine = _build_engine()

# 创建异步会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    """声明式基类"""
    pass


async def get_db() -> AsyncSession:
    """获取数据库会话的依赖注入"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库（创建所有表）。

    v17.9.1 S4：生产环境的 schema 唯一管理者是 Alembic migration
    （deploy.sh 只执行 `alembic upgrade head`）；create_all 仅保留给
    dev/test 环境——生产下建表动作直接被拒绝，防止 schema 双真源。
    """
    if settings.ENV.strip().lower() == "production":
        raise RuntimeError(
            "拒绝 create_all：ENV=production 的 schema 由 Alembic 管理"
            "（先运行 alembic upgrade head）。如确需重建请用迁移。"
        )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """关闭数据库连接"""
    await engine.dispose()
