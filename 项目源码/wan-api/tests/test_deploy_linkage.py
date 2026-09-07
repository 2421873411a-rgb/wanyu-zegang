"""部署链 linkage 门禁（v17.9.10 P0 教训，v17.9.11 扩面）。

deploy.sh 的 alembic/gunicorn/heredoc/smoke 分别依赖以下符号与文件事实；
PR #8 曾删除 import_all_data 而 deploy.sh 仍在调用，bash -n 语法检查发现不了
Python ImportError。这里把部署面用到的每个 import / 关键配置都锁进测试：
任何断链直接 CI 红，SQLite/Postgres 两个 job 都会跑本文件。

v17.9.11 新增（Round-1 部署链审计 A8/A10/C6/C7）：
- gunicorn worker_class 字符串与 lock 二进制存在性（防最晚暴露点断链）
- lock 必含部署硬依赖（gunicorn/alembic/uvicorn-worker/uvloop——后者是
  uvicorn[standard] 在 Linux 的 extra，Windows 生成的 freeze 曾静默丢失）
- systemd unit / nginx 模板关键行（日志目录权限、root 而非 alias、强制跳转来源）
- 版本单一真源一致性：settings.APP_VERSION == release.json.release
"""
import re
from pathlib import Path

WAN_API = Path(__file__).resolve().parents[1]


def _deploy_sh() -> str:
    return (WAN_API / "deploy.sh").read_text(encoding="utf-8")


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


def test_gunicorn_worker_class_importable():
    """gunicorn.conf.py 的 worker_class 是纯字符串：包被删时只有 import 能抓住。

    注意 gunicorn 包本身没有 gunicorn.conf 子模块（conf 是用户配置文件），
    必须按路径加载部署配置。worker_class 指向的类只能在 POSIX 上 import
    （uvicorn_worker 依赖 fcntl），Windows 开发机跳过该半边、CI ubuntu 必跑。
    """
    import importlib.util
    import sys

    conf_path = WAN_API / "gunicorn.conf.py"
    spec = importlib.util.spec_from_file_location("deploy_gunicorn_conf", conf_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.worker_class == "uvicorn_worker.UvicornWorker"
    if sys.platform != "win32":
        from gunicorn.util import import_class

        assert import_class(mod.worker_class) is not None


def test_runtime_lock_contains_deploy_hard_dependencies():
    """deploy 用 runtime lock 安装：部署硬依赖缺一行，生产启动/迁移就断。"""
    lock = (WAN_API / "requirements.lock.txt").read_text(encoding="utf-8").lower()
    for pkg in ("gunicorn==", "alembic==", "uvicorn-worker==", "uvloop==", "asyncpg=="):
        assert pkg in lock, f"runtime lock 缺部署硬依赖：{pkg}"
    # uvloop 是 uvicorn[standard] 在 Linux 的 extra：Windows 生成的 freeze 曾静默丢失
    assert "\nuvloop==" in f"\n{lock}"


def test_deploy_sh_uses_correct_pg_function_and_restart():
    """deploy.sh 必须用真实存在的 pg_get_userbyid（拼错=二次部署必炸）+ systemctl restart。"""
    script = _deploy_sh()
    assert "pg_get_userbyid(datdba)" in script
    assert "pg_get_userby(" not in script
    assert "systemctl restart" in script
    assert "set -Eeuo pipefail" in script


def test_deploy_sh_log_dir_permissions_and_no_silent_swallow():
    """P0 回归锁：日志目录必须 chown www-data；不得有新增的 || true 吞错。"""
    script = _deploy_sh()
    assert 'chown www-data:www-data "$LOG_DIR"' in script
    # v17.9.11 清零历史唯一吞错点；仅豁免 read_existing_db_password 里
    # "读不到旧密码行"这一显式允许为空的 grep 兜底，其余一律禁止（注释行不计）。
    code_lines = "\n".join(l for l in script.splitlines() if not l.lstrip().startswith("#"))
    whitelisted = re.compile(
        r"\(grep -m1 '\^DATABASE_URL=' \"\$env_file\" \|\| true\)"
    )
    assert "|| true" not in whitelisted.sub("", code_lines), "deploy.sh 出现新的 || true 吞错"


def test_systemd_unit_and_nginx_template_invariants():
    """unit/nginx 模板关键行：日志目录、root（非 alias）、certbot --redirect。"""
    script = _deploy_sh()
    assert "ReadWritePaths=${LOG_DIR} ${APP_DIR}" in script  # unit 模板（展开式 heredoc）
    assert "User=www-data" in script
    assert "root /opt/wanyu/static;" in script  # nginx: root 修复（alias+try_files 是 trac#97 缺陷）
    assert "alias /opt/wanyu" not in script
    assert "--redirect" in script  # certbot 强制 HTTP→HTTPS


def test_app_version_single_source():
    """API 版本单一真源：settings.APP_VERSION == wan-api/release.json 的 release
    （wanyu-api-release/v1）。项目级 release.json 描述网站产品，互不捆绑。

    v17.9.1~v17.9.10 十次发布 config 默认值从未 bump（三处版本互相矛盾）——
    v17.9.11 起 config 启动时读 API release.json，此测试锁死一致性。
    """
    import json

    from app.config import settings

    release_json = WAN_API / "release.json"
    assert release_json.is_file()
    doc = json.loads(release_json.read_text(encoding="utf-8"))
    assert doc.get("schema") == "wanyu-api-release/v1"
    declared = doc["release"]
    assert settings.APP_VERSION == declared, (
        f"版本漂移：APP_VERSION={settings.APP_VERSION} vs wan-api/release.json={declared}"
    )


def test_health_endpoint_exposes_version():
    """/health 必须携带 version（deploy smoke 的"部署真正生效"证据）。"""
    import asyncio

    from app.main import health

    body = asyncio.run(health())
    assert re.fullmatch(r"v\d+\.\d+\.\d+", body.get("version", "")), body
