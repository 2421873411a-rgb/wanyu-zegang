# Round 1 本地全量门禁输出（§10 九门）

1. pytest（SQLite）：53 passed, 2 skipped（基线 35+2 → +18 个 Round-1 门禁测试；2 skip 为 PG 专属并发测试）
2. Alembic 往返+漂移：upgrade(0001→0002→0003) → check 零漂移 → downgrade base → upgrade → check 零漂移
3. bash -n deploy.sh：OK
4. ruff check app tests scripts --select E9,F63,F7,F82 --ignore E402：All checks passed
5. pip-audit：runtime lock --strict = No known vulnerabilities（uvloop 带 sys_platform marker）；dev lock --strict = No known vulnerabilities
6. canonical core：PASS (schema + conservation + ids + exclusion evidence + reference metadata)
7. verify_sources --manifest-only：PASS（14 项）
8. 真数据 e2e（scripts/e2e_real_data.py）：6 快照校验 PASS → 全量导入对账 PASS（10017/10150/8511，2026 active=8401，salary=160，review=7）→ 幂等重跑 PASS
9. CI 模拟（工作树副本按 EXCLUDED 清单跑 discovery 循环）：18 模块 ALL PASS；18 模块第三方 import 扫描 = 纯 stdlib
附：两个 workflow YAML 解析 OK；uvloop 平台标记后 Windows 侧 lock 安装/审计恢复可用
