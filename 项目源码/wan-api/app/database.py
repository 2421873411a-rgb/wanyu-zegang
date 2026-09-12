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

# v17.10.0 慢查询日志：>SLOW_QUERY_MS 记 warning（语句截断 200 字符），计数进 /metrics
import json as _json
import logging as _logging
import time as _time

from sqlalchemy import event as _event

from app.observability import metrics as _metrics

_db_logger = _logging.getLogger("wanyu.db")


@_event.listens_for(engine.sync_engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("_query_start", []).append(_time.perf_counter())


@_event.listens_for(engine.sync_engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    starts = conn.info.get("_query_start")
    if not starts:
        return
    duration_ms = (_time.perf_counter() - starts.pop()) * 1000
    threshold = settings.SLOW_QUERY_MS
    if threshold > 0 and duration_ms > threshold:
        _metrics.observe_slow_query(duration_ms, statement)
        _db_logger.warning(_json.dumps({
            "event": "slow_query",
            "duration_ms": round(duration_ms, 1),
            "threshold_ms": threshold,
            "statement": statement[:200],
        }, ensure_ascii=False))

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

    env = settings.env_normalized
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
                # 检查 alembic 当前 revision == head（用 API，不走 subprocess——subprocess
                # 自身失败时 head="" 会导致 fail-open）
                # v17.9.12：fetchall——多行（多头迁移/污染版本表）必须拒绝，
                # fetchone 无 ORDER BY 曾使判定取决于物理行序（审计实测两种结果）。
                rows = sync_conn.execute(sa_text("SELECT version_num FROM alembic_version")).fetchall()
                if not rows:
                    raise RuntimeError("alembic_version 表为空——迁移未完成")
                if len(rows) != 1:
                    raise RuntimeError(
                        f"alembic_version 表有 {len(rows)} 行（多头/污染版本表）——拒绝启动，"
                        "请人工核对迁移历史"
                    )
                try:
                    from alembic.config import Config
                    from alembic.script import ScriptDirectory
                    cfg = Config("alembic.ini")
                    script = ScriptDirectory.from_config(cfg)
                    heads = script.get_heads()
                    if len(heads) != 1:
                        raise RuntimeError(f"alembic heads 数量异常（{len(heads)}），期望恰好 1 个")
                    if rows[0][0] != heads[0]:
                        raise RuntimeError(
                            f"alembic 版本不一致：DB={rows[0][0][:12]} HEAD={heads[0][:12]}——"
                            "请运行 alembic upgrade head"
                        )
                except FileNotFoundError:
                    raise RuntimeError("alembic.ini 不存在——无法验证迁移版本")
            await conn.run_sync(_check_tables)
        else:
            await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """关闭数据库连接"""
    await engine.dispose()
