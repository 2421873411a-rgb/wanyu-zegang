# Round 3 复审 + 修复（v17.9.13）门禁输出

复审结论：Round 3 不干净——回归对抗抓出 P1×2（转义缺陷实现 + 首署 mkdir）+ P2×约14（含 4 项是 v17.9.12 新引入问题的再发现），全部关闭于 v17.9.13。

九门：
1. pytest（SQLite）：70 passed, 5 skipped（+4 Round-3 正向门禁：字面量匹配/stats 失效/在场排除级联/bm 浮点）
2. alembic 往返（0004）+ check：零漂移
3. bash -n deploy.sh：OK（含 OS 支持矩阵/停服窗口/mkdir 修复）
4. ruff：clean
5. pip-audit 双 lock：clean（前轮已验，本轮无依赖变更）
6. canonical core：PASS
7. verify_sources manifest：PASS；discovery 模拟：ALL PASS
8. e2e 真数据：PASS
9. YAML：OK
