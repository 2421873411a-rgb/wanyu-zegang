[DRILL PASS] v1 ghost file + six present (drill setup verified)
=== 构建 release v2（干净 N）===
=== 不变量1：幽灵文件在 N 中不存在 ===
[DRILL PASS] ghost file absent in v2
=== 不变量2：已删依赖在 N venv 中不存在 ===
[DRILL PASS] removed dependency absent in v2 venv
=== 不变量3：N → N 重复构建幂等 ===
[DRILL PASS] rebuild idempotent (no accumulation)
=== 不变量4：current 符号链接原子切换 + 回滚 ===
[DRILL PASS] atomic switch + rollback verified

==========================================
UPGRADE DRILL: ALL PASS（幽灵文件=0 / 依赖漂移=0 / 幂等 / 切换+回滚可用）
==========================================
