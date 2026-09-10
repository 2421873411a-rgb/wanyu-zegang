# 风险登记册（RISK REGISTER）

> 规则：每个 P1 修复必须对应一条风险；修复后"剩余风险"如实标注，不写"已消除"。
> 本表从"修 bug 思维"转向"风险管理思维"的落点，随版本更新。

| ID | 风险 | 概率 | 影响 | 当前控制 | 剩余风险 | Owner | 关联修复 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R001 | canonical 与 网站/ 派生产物漂移 | 中 | 高 | build gate + check_site_parity.py 字节级门禁 | 低 | CI | PR-4 site-release-gate |
| R002 | SW 旧缓存导致用户拿到过期资产 | 中 | 中 | 版本化缓存（?v=/?sha=）+ SW version bump | 低 | FE | v17.9.2 wanyu-shell-v52 |
| R003 | bcrypt 阻塞事件循环拖垮全 API | 中 | 高 | hash/verify 全部线程池化 + loop 响应探针测试 | 低 | API | PR-2 |
| R004 | Redis 故障时限流降级失真 | 低 | 中 | 降级到 memory limiter 且稀释倍数=真实 worker 数 | 中（Redis 单点仍在） | API | PR-3 worker 单源 |
| R005 | 单机灾难（DB/磁盘全损） | 低 | 极高 | 本机 dump + checksum + 日/周/月恢复点 | **高（无异地副本）** | OPS | P1-OPS-001 未完成 |
| R006 | source→canonical 溯源断链 | 中 | 高 | sources.lock + 来源哈希 + verify_sources | 中（CI 无法复验原始 bytes） | DATA | P2-DATA-001 未完成 |
| R007 | 数据模块被篡改后前端照常渲染 | 低 | 高 | DataStore 对 manifest SHA 无条件 digest 校验，无 Web Crypto 时 fail closed | 低 | FE | PR-1 datastore |
| R008 | 导入事务与统计缓存竞态 | 中 | 中 | admin import 显式 commit 后才 invalidate + 回归测试 | 低 | API | PR-3 commit 49fbafd |
| R009 | 匿名接口被大 body / 超长字段打满 | 中 | 中 | nginx 分层 body 上限 + Pydantic 字段上限 + 流式 413 兜底 | 低 | API | PR-2 |
| R010 | profile 输入依赖非标准全局 event | 中 | 中 | 纯函数映射 + 三浏览器烟测矩阵 | 低（CI 尚未跑满三引擎） | FE | PR-1 + PR-4 |
| R011 | 旧版浏览器/隐私模式 localStorage 抛异常炸页面 | 低 | 低 | StorageAdapter 全异常收敛 + UI 明示降级 | 低 | FE | PR-1 user-store |
| R012 | 工作台导入把坏数据写进 localStorage | 低 | 中 | 原子导入 + ID 形态校验 + 去重统计 | 低 | FE | PR-1 importAll |
| R013 | 快照/对比并发写突破业务上限 | 低 | 中 | PG 事务级咨询锁 + 槽位冲突重试 + 并发测试（PG CI） | 低 | API | PR-3 commit 030caf4 |
