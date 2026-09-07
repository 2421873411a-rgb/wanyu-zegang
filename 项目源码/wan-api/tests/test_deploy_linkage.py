"""部署链 linkage 门禁（v17.9.10 P0 教训）。

deploy.sh 的 alembic/gunicorn/heredoc 分别依赖以下符号；PR #8 曾删除
import_all_data 而 deploy.sh 仍在调用，bash -n 语法检查发现不了 Python
ImportError。这里把部署面用到的每个 import 都锁进测试：任何断链直接 CI 红，
SQLite/Postgres 两个 job 都会跑本文件。
"""


def test_deploy_sh_import_surface_intact():
    """deploy.sh heredoc: from app.services.import_service import import_all_data"""
    from app.services.import_service import import_all_data
    assert callable(import_all_data)


def test_deploy_sh_heredoc_imports_intact():
    """deploy.sh heredoc: from app.database import init_db, async_session_factory"""
    from app.database import async_session_factory, init_db
    assert callable(init_db)
    assert async_session_factory is not None


def test_gunicorn_entrypoint_imports():
    """systemd ExecStart: gunicorn app.main:app"""
    import app.main  # noqa: F401


def test_import_service_public_api():
    """管理导入与生产引导共用的服务面必须完整可用"""
    from app.services.import_service import (
        CYCLES,
        ImportService,
        SnapshotValidationError,
        validate_snapshot,
    )
    assert set(CYCLES) == {"2024", "2025", "2026"}
    assert issubclass(SnapshotValidationError, Exception)
    assert callable(validate_snapshot)
    assert hasattr(ImportService, "snapshot_replace")
    assert hasattr(ImportService, "import_salary_data")
    assert hasattr(ImportService, "import_review_events")
