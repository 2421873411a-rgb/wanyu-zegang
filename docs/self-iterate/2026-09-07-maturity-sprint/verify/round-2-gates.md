# Round 2 本地全量门禁输出（§10 九门）

1. pytest（SQLite）：66 passed, 5 skipped（+13 Round-2 回归；PG 并发×2 与 Redis 限流×3 在 CI 服务容器执行）
2. Alembic：upgrade 含 0004（GIN trgm/复合索引/record_status 回填，SQLite 走 batch 分支）→ check 零漂移
3. bash -n deploy.sh：OK
4. ruff：All checks passed（含 database.py F821 顺手修复）
5. pip-audit 双 lock --no-deps --strict：No known vulnerabilities（Windows 侧 marker 兼容；CI ubuntu 走默认模式）
6. canonical core：PASS
7. verify_sources --manifest-only：PASS；canonical discovery 模拟：ALL PASS（含新模块 test_round2_hardening/test_rate_limit_redis 自动入门禁）
8. 真数据 e2e：PASS（幂等重跑含 review 不翻倍实证）
9. workflow YAML：OK
版本：APP_VERSION=v17.9.12（单一真源 wan-api/release.json）
