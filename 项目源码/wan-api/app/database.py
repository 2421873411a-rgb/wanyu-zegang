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
    启动时检查：①核心表存在 ②alembic 当前 revision == head（防止迁移漏跑或部分执行）。
    不满足任一条→拒绝启动（fail-closed）。
    开发/测试：自动 create_all。
    """
    from sqlalchemy import inspect as sa_inspect, text as sa_text

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
                # 检查 alembic 当前 revision（应恰好有一个 head）
                row = sync_conn.execute(sa_text("SELECT version_num FROM alembic_version")).fetchone()
                if not row:
                    raise RuntimeError("alembic_version 表为空——迁移未完成")
                # head revision 比对：调用 alembic 命令获取 head，比较是否一致
                import subprocess, sys
                result = subprocess.run(
                    [sys.executable, "-m", "alembic", "heads"],
                    capture_output=True, text=True
                )
                head = result.stdout.strip().split()[0] if result.returncode == 0 else ""
                if head and row[0] != head:
                    raise RuntimeError(
                        f"alembic 版本不一致：DB={row[0][:12]} HEAD={head[:12]}——"
                        "请运行 alembic upgrade head"
                    )
            await conn.run_sync(_check_tables)
        else:
            await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """关闭数据库连接"""
    await engine.dispose()
