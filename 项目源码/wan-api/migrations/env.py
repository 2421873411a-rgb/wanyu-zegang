import os
# 迁移工具上下文默认按 test 语义加载 app 配置（SECRET_KEY 门禁针对应用启动，
# 不应阻断 alembic；显式导出的 ENV 仍被尊重，生产下 .env 会提供完整配置）。
os.environ.setdefault("ENV", "test")

import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# 导入所有模型以便Alembic能够检测
from app.database import Base
from app.models import *  # noqa

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# v17.9.1 S4：迁移 URL 以应用配置为唯一真源（.env / 环境变量），alembic.ini 里的
# sqlalchemy.url 仅为离线兜底——避免迁移目标与运行库漂移。
from app.config import settings as _app_settings  # noqa: E402

config.set_main_option("sqlalchemy.url", _app_settings.DATABASE_URL)


def _include_object(obj, name, type_, reflected, compare_to):
    """非 PG 方言下排除 PG 专属的 GIN trgm 索引（迁移里用方言分支创建），
    避免 SQLite 的 autogenerate/check 把它们当成漂移。"""
    if type_ == "index" and name in ("ix_jobs_record_status_num",):
        # 迁移 0004 独占管理（textual 'num DESC' 与 ORM 元数据比较恒不相等）
        return False
    if type_ == "index" and name and name.endswith("_trgm"):
        from alembic import context as _ctx
        try:
            if _ctx.get_context().dialect.name != "postgresql":
                return False
        except Exception:
            pass
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_object=_include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata,
                      include_object=_include_object)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
