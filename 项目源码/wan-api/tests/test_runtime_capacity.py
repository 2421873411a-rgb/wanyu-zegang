"""容量不变量（v17.10.2 P2-10）：文档硬规则升级为拒绝启动的代码不变量。"""
import pytest

from app.config import Settings, _validate_runtime_capacity


def _settings(**overrides) -> Settings:
    overrides.setdefault("ENV", "production")
    overrides.setdefault("SECRET_KEY", "x" * 48)
    overrides.setdefault("CORS_ORIGINS", ["https://wan.kaogong.art"])
    overrides.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@db:5432/wan")
    overrides.setdefault("RATE_LIMIT_BACKEND", "redis")
    return Settings(**overrides)


def test_fallback_workers_default_to_web_concurrency():
    s = _settings(WANYU_WEB_CONCURRENCY="3")
    _validate_runtime_capacity(s)
    assert s.WEB_CONCURRENCY == 3
    assert s.RATE_LIMIT_FALLBACK_WORKERS == 3, "未显式配置时必须从 WEB_CONCURRENCY 派生"


def test_fallback_workers_explicit_override_respected():
    s = _settings(WANYU_WEB_CONCURRENCY="2", RATE_LIMIT_FALLBACK_WORKERS="2")
    _validate_runtime_capacity(s)
    assert s.RATE_LIMIT_FALLBACK_WORKERS == 2


def test_multi_worker_without_redis_refused_in_production():
    s = _settings(WANYU_WEB_CONCURRENCY="4", RATE_LIMIT_BACKEND="memory")
    with pytest.raises(RuntimeError, match="redis"):
        _validate_runtime_capacity(s)


def test_multi_worker_with_redis_allowed():
    s = _settings(WANYU_WEB_CONCURRENCY="4", RATE_LIMIT_BACKEND="redis")
    _validate_runtime_capacity(s)  # 不抛即通过


def test_sqlite_refused_in_production():
    s = _settings(DATABASE_URL="sqlite+aiosqlite:///./wanyu.db")
    with pytest.raises(RuntimeError, match="SQLite"):
        _validate_runtime_capacity(s)


def test_fuzzy_test_spelling_keeps_no_exemption():
    """RA-5 保持：' TEST '/'Test' 归一后虽为 test，但豁免仍走原文精确匹配 → 拒启。"""
    from app.config import _validate_production_safety

    for env in (" TEST ", "Test", "TEST"):
        with pytest.raises(RuntimeError):
            _validate_production_safety(_settings(ENV=env, SECRET_KEY=""))


def test_env_is_normalized_before_production_gates():
    """评审 P2 回归锁：ENV 大小写/空白变体必须归一，不得绕过生产门。"""
    from app.config import _validate_production_safety

    s = _settings(ENV=" PRODUCTION ", DATABASE_URL="sqlite+aiosqlite:///./wanyu.db")
    assert s.env_normalized == "production"
    with pytest.raises(RuntimeError, match="SQLite"):
        _validate_runtime_capacity(s)
    # CORS localhost 检查只在 production 段生效——归一前 " PRODUCTION " 会绕过它
    s2 = _settings(ENV=" production ", CORS_ORIGINS=["http://localhost:8765"])
    with pytest.raises(RuntimeError, match="开发 origin"):
        _validate_production_safety(s2)
