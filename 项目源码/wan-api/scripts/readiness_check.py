#!/usr/bin/env python3
"""readiness_check（v17.10.2 PR-5）：API 生产就绪度从"文档 TODO"升级为机器判定。

用法：
    python scripts/readiness_check.py            # 输出 JSON 摘要，exit 0/1
    python scripts/readiness_check.py --production  # 额外要求 ENV=production 硬门

判定规则（与 CONTRACT.md 对齐）：
- database: 能连接且 alembic head 一致
- redis:    多 worker 时必须可达；单 worker 可选
- static_data: 2024/2025/2026 目录存在
- backup.offsite / restore_drill / secret_rotation: 读 docs/ops/dr-evidence.json
  证据文件（schema 见同目录 dr-evidence.schema.json），证据不齐 → dr_ready=false。
- 不虚报：COS 异地副本与异机恢复演练没有真实证据前，dr_ready 永远是 false。
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

EVIDENCE = PROJECT / "docs" / "ops" / "dr-evidence.json"


async def check_database(settings) -> dict:
    from sqlalchemy import text

    from app.database import async_session_factory

    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return {"backend": settings.DATABASE_URL.split("://", 1)[0], "ok": True}
    except Exception as exc:  # noqa: BLE001 — readiness 报告不挑异常类型
        return {"backend": settings.DATABASE_URL.split("://", 1)[0], "ok": False, "error": str(exc)[:200]}


def check_redis(settings) -> dict:
    required = settings.WEB_CONCURRENCY > 1 or settings.RATE_LIMIT_BACKEND == "redis"
    if settings.RATE_LIMIT_BACKEND != "redis":
        return {"required": required, "reachable": False, "note": "memory 后端：单 worker 专用"}
    import redis as redis_lib

    try:
        client = redis_lib.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        client.ping()
        return {"required": required, "reachable": True}
    except Exception as exc:  # noqa: BLE001
        return {"required": required, "reachable": False, "error": str(exc)[:200]}


def static_data_dir(settings):
    """与 deploy.sh 预检、import_all_data 共用的真实布局：<STATIC_DATA_PATH>/cycles/<cycle>/jobs.json"""
    return Path(settings.STATIC_DATA_PATH) / "cycles"


def check_static_data(settings) -> dict:
    # 审计 API-004：旧实现查 <base>/<cycle>，生产上永远 false
    base = static_data_dir(settings)
    out = {}
    for cycle in ("2024", "2025", "2026"):
        out[cycle] = (base / cycle / "jobs.json").is_file()
    return out


def load_dr_evidence() -> dict:
    if not EVIDENCE.exists():
        return {}
    try:
        return json.loads(EVIDENCE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def dr_ready(evidence: dict) -> dict:
    def flag(key):
        return bool(evidence.get(key))

    offsite = flag("offsite_object") and flag("backup_sha256") and bool(evidence.get("download_verified"))
    restore = flag("restore_host") and flag("restored_revision") and bool(evidence.get("application_smoke"))
    rotation = flag("secret_rotated_at")
    return {
        "offsite_backup": offsite,
        "offsite_restore_drill": restore,
        "secret_rotation": rotation,
        "dr_ready": offsite and restore,
        "evidence_file": str(EVIDENCE.relative_to(PROJECT)) if EVIDENCE.exists() else None,
    }


def migration_ok(rows, heads) -> dict:
    """与 init_db 同谓词：alembic_version 恰一行且等于唯一 head。
    空/缺失 → ok False（init_db 生产路径对空表直接拒启——评审 P2：就绪信号不得与可启动性相反；
    表缺失的异常由 check_migration_head 的 except 捕获为 ok False）。"""
    if not rows:
        return {"ok": False, "error": "alembic_version 为空（迁移未完成或非迁移管理库）"}
    if len(rows) != 1:
        return {"ok": False, "error": f"alembic_version 行数异常：{[str(r) for r in rows]}"}
    if len(heads) != 1:
        return {"ok": False, "error": f"alembic heads 异常：{heads}"}
    ok = str(rows[0]) == str(heads[0])
    return {"ok": ok, "current": str(rows[0]), "head": str(heads[0])}


def compute_ready(db_ok: bool, redis_required: bool, redis_reachable: bool, static_all_ok: bool) -> bool:
    """审计 API-005：旧表达式的 and/or 优先级会在 redis 非必需时短路掉 db_ok。"""
    return bool(db_ok and (redis_reachable or not redis_required) and static_all_ok)


async def check_migration_head() -> dict:
    from sqlalchemy import text

    from app.database import async_session_factory

    try:
        cfg = _alembic_config()
        from alembic.script import ScriptDirectory

        heads = [str(h) for h in ScriptDirectory.from_config(cfg).get_heads()]
        async with async_session_factory() as session:
            rows = (await session.execute(text("SELECT version_num FROM alembic_version"))).fetchall()
        return migration_ok([row[0] for row in rows], heads)
    except Exception as exc:  # noqa: BLE001 — readiness 报告不挑异常类型
        return {"ok": False, "error": str(exc)[:200]}


def _alembic_config():
    from alembic.config import Config

    return Config(str(PROJECT / "alembic.ini"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()

    from app.config import settings

    database = asyncio.run(check_database(settings))
    migration = asyncio.run(check_migration_head()) if database["ok"] else {"ok": False, "error": "database unreachable"}
    report = {
        "release": settings.APP_VERSION,
        "environment": settings.env_normalized,
        "workers": settings.WEB_CONCURRENCY,
        "rate_limit_backend": settings.RATE_LIMIT_BACKEND,
        "database": database,
        "migration": migration,
        "redis": check_redis(settings),
        "static_data": check_static_data(settings),
        "dr": dr_ready(load_dr_evidence()),
    }
    ok = compute_ready(
        database["ok"] and migration["ok"],
        report["redis"]["required"],
        report["redis"]["reachable"],
        all(report["static_data"].values()),
    )
    if args.production:
        ok = ok and settings.env_normalized == "production"
    report["ready"] = bool(ok)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.production and not report["dr"]["dr_ready"]:
        print("NOT READY: dr_ready=false（COS 异地副本 / 异机恢复演练证据缺失）", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
