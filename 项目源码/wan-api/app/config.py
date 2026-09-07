from pydantic_settings import BaseSettings
from typing import List, Optional
import json
import os
from pathlib import Path

# v17.9.1 S0：已知默认秘密清单——生产环境命中任一即拒绝启动（fail-closed）
_KNOWN_INSECURE_SECRETS = {
    "your-secret-key-change-in-production",
    "your-super-secret-key-change-this-in-production",
    "",
}


def _version_from_release_json() -> Optional[str]:
    """API 版本单一真源：wan-api/release.json 的 release 字段（wanyu-api-release/v1）。

    仓库布局（app/config.py → parents[1] = wan-api/）直接命中；部署布局
    /opt/wanyu/api 下同样命中（release.json 随载荷部署）；找不到再试项目级
    release.json，仍无则返回 None 交还 env（deploy.sh 注入）。
    """
    marker = Path(__file__).resolve()
    for parent in marker.parents[:4]:
        candidate = parent / "release.json"
        if candidate.is_file():
            try:
                doc = json.loads(candidate.read_text(encoding="utf-8"))
                if doc.get("schema") == "wanyu-api-release/v1":
                    return str(doc["release"])
            except (OSError, ValueError, KeyError):
                continue
    return None


class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "皖域择岗 API"
    # v17.9.11：APP_VERSION 不再手工硬编码——默认从 release.json 单一真源读取，
    # 部署布局由 deploy.sh 注入 .env。手工版本号曾连续十个版本漂移（v17.9.1~v17.9.10）。
    APP_VERSION: str = _version_from_release_json() or "unknown"
    # ENV: dev / test / production。production 下强制安全门（SECRET_KEY 不得为已知默认值）
    ENV: str = "dev"
    DEBUG: bool = False

    # 数据库配置（本地开发使用SQLite，生产环境使用PostgreSQL）
    DATABASE_URL: str = "sqlite+aiosqlite:///./wanyu.db"
    DATABASE_ECHO: bool = False

    # Redis配置
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT配置
    # v17.9.12：SECRET_KEY 不再有默认值——公开默认密钥=任何非 production 环境可离线伪造
    # 任意用户 token（审计 R2-T2 实证）。ENV=test 自动注入测试密钥；其余环境缺失/过弱拒启。
    SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS配置
    CORS_ORIGINS: List[str] = ["https://wan.kaogong.art", "http://localhost:8765"]

    # 静态数据路径（用于数据导入）
    STATIC_DATA_PATH: str = "/opt/wanyu/static/maintainable/data"

    # 注册配置
    ALLOW_REGISTRATION: bool = True
    # ADMIN_EMAIL 仅作为 scripts/create_admin.py 引导管理员的核对口径，
    # 注册接口永远不得依据邮箱授予管理员（v17.9.1 S0：消除抢注册路径）。
    ADMIN_EMAIL: str = ""

    # 分页配置
    DEFAULT_PAGE_SIZE: int = 60
    MAX_PAGE_SIZE: int = 200

    # 管理导入上限（字节）：超过直接 413，防止超大 JSON 打爆内存
    ADMIN_IMPORT_MAX_BYTES: int = 64 * 1024 * 1024

    # 限流（v17.9.12：原子化 + 可选 Redis 后端）
    RATE_LIMIT_BACKEND: str = "memory"  # memory | redis
    LOGIN_MAX_FAILURES: int = 5
    LOGIN_WINDOW_SECONDS: int = 300
    REGISTER_MAX_EVENTS: int = 5
    REGISTER_WINDOW_SECONDS: int = 300
    REFRESH_MAX_EVENTS: int = 30
    REFRESH_WINDOW_SECONDS: int = 60
    LOGOUT_MAX_EVENTS: int = 10
    LOGOUT_WINDOW_SECONDS: int = 60
    # Redis 不可达时进程内兜底按 worker 数收紧的分母上限
    RATE_LIMIT_FALLBACK_WORKERS: int = 4

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


def _validate_production_safety(settings: "Settings") -> None:
    """SECRET_KEY 安全门（v17.9.12 全面收紧）。

    - ENV=test：允许空并注入固定测试密钥（测试需要真实签发/校验 token）。
    - 其余任何环境：缺失或命中已知公开默认值 → 拒绝启动；
      长度 <32 字符 → 拒绝启动（此前 'secret' 这类弱密钥在生产也放行）。
    """
    env = settings.ENV.strip().lower()
    if env == "test":
        if not settings.SECRET_KEY:
            settings.SECRET_KEY = "wanyu-test-only-secret-key-0123456789abcdef"
        return
    if not settings.SECRET_KEY:
        raise RuntimeError(
            "拒绝启动：SECRET_KEY 缺失。请提供独立随机密钥（openssl rand -hex 32）。"
        )
    if settings.SECRET_KEY in _KNOWN_INSECURE_SECRETS:
        raise RuntimeError(
            "拒绝启动：SECRET_KEY 为公开已知默认值，任何人可离线伪造任意用户 token。"
            "请更换（openssl rand -hex 32）。"
        )
    if len(settings.SECRET_KEY) < 32:
        raise RuntimeError("拒绝启动：SECRET_KEY 强度不足（至少 32 字符，建议 openssl rand -hex 32）。")


settings = Settings()
_validate_production_safety(settings)
