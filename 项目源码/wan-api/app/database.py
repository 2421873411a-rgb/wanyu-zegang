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
    """启动时 schema 检查与 dev 自动建表。

    生产（ENV=production）：schema 由 Alembic 管理（deploy.sh 先跑 upgrade head），
    启动时只检查核心表存在→不存在说明迁移没跑→拒绝启动（fail-closed）。
    开发/测试：自动 create_all。
    """
    from sqlalchemy import inspect as sa_inspect

    env = settings.ENV.strip().lower()
    async with engine.begin() as conn:
        if env == "production":
            def _check_tables(sync_conn):
                inspector = sa_inspect(sync_conn)
                tables = set(inspector.get_table_names())
                if "users" not in tables or "alembic_version" not in tables:
                    raise RuntimeError(
                        "ENV=production 但 users/alembic_version 表不存在——"
                        "请先运行 alembic upgrade head（deploy.sh 已包含此步骤）。"
                    )
            await conn.run_sync(_check_tables)
        else:
            await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """关闭数据库连接"""
    await engine.dispose()
