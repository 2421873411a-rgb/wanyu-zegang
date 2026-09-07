# Round 4 复审 + 修复（v17.9.14）门禁输出

复审结论：Round 4 不干净——回归验证抓出"声称已修未落地"的 P1（反斜杠转义）+ 盲区终扫 P1×1（release 列宽）+ P2×13，全部关闭于 v17.9.14。

九门：
1. pytest（SQLite）：73 passed, 5 skipped（+3：反斜杠正反门禁/release 列宽/三路由冒烟）
2. alembic 往返 + check：零漂移
3. bash -n deploy.sh：OK（停服窗口前移/TimeoutStopSec 45/*.db 排除）
4. ruff：clean
5. pip-audit：本轮无依赖变更（前轮 clean）
6. canonical core：PASS
7. verify_sources manifest：PASS
8. e2e 真数据：PASS
9. workflow YAML：OK
流程修复实证：jobs.py 反斜杠转义字节级验证入树（2 个反斜杠字节）；README 重复 cp/测试数/命令修正；
无效门禁测试改为同 id 真覆盖。
