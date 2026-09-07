# Round 3 审计 · 数据链完整性复查（子代理产出，含探针实测）

- P1 _escape_like 替换模板损坏（反斜杠+SOH）：含 %/_ 字面量搜索恒为空 + 注入控制字符。
  门禁盲区：只断言 total==0 从不断言字面量可命中。【已确认，主控字节级证实，已修】
- P2 stats 缓存零收益：查询在 _cached 之前执行（命中仍打库）+ 无失效钩子（热导入 60s 脏读）。属缺陷非取舍。【已修：execute 移入 builder + invalidate 钩子】
- P2 第二轮导入无 label 包时 MirrorState.release 被无条件覆盖清空（与 Cycle.label 守卫矛盾）。【修复中】
- P2 快照内在场 excluded 行不触发级联清理（幽灵收藏与 CONTRACT 承诺不符）。【修复中】
- P2 MirrorState 字段口径无契约文档 + line356 注释自相矛盾（recruits 实为 active 口径非 raw）。【修复中】
- 零发现（实测）：e2e 全 PASS 口径精确；import_all_data 单事务连带回滚；级联删除范围安全（job_id 强格式下无跨周期碰撞）；conftest×0004 无影响；无循环导入。
