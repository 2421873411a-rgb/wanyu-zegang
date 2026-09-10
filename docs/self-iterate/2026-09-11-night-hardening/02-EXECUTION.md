# 02 · 执行记录（night-20260911）

分支 `hardening/night-20260911`（自 main@9f87d772 切出）。纪律：先红后绿、逐包提交、每包可独立回滚。

## Commit 清单

| Commit | 包 | 内容 | 对应问题 |
| --- | --- | --- | --- |
| ba82ae9 | 阶段0 | 冻结基线 + 业务不变量快照（invariants.py，canonical 聚合 SHA） | — |
| bdcbadd | PR-1A | DataStore：cacheAddressed 与 verifyIntegrity 解耦；有 SHA 必验 digest；无 Web Crypto fail closed（integrity_policy=compatible 显式降级）；IntegrityError 带 code；14 场景损坏矩阵 | P1-02 |
| d8c5bad | PR-1A/B | profile 字段映射抽纯函数进 user-store（站点不再碰存储 key/全局 event）；StorageAdapter 收敛 SecurityError/Quota/corrupt 为状态 + UI 明示降级；importAll 原子化 + 去重 + job-YYYY-20hex 校验 + ignored_invalid/deduplicated 统计；17 用例 | P1-01、P2-12、P2-13 |
| 4f9b90a | PR-2 | nginx 64m 收窄到 admin import 专属、普通 API 512k；login/refresh/logout 字段上限；bcrypt 全线程池化（含 dummy 路径）；loop 响应探针 + 边界矩阵测试 | P1-04、P1-05 |
| 49fbafd | PR-3 | `_to_int` 只认 JSON int（3.0/"3"/bool 全拒）；admin import 显式 commit 后才 invalidate（回归：invalidate 瞬间新连接必须看到已提交行） | P1-07、P1-03 |
| 030caf4 | PR-3 | snapshot 配额 pg_advisory_xact_lock；compare 撞槽回滚→分辨语义→重试≤3；PG 并发测试 2 条（SQLite 环境跳过，PG CI 实测） | P2-08、P2-09 |
| 236478b | PR-3 | WEB_CONCURRENCY 单一真源派生限流稀释；生产不变量（多 worker 须 redis、禁 sqlite）拒绝启动；启动打非敏感容量摘要 | P2-10 |
| 8fc9c6f | PR-4 | site-release-gate 工作流（parity/单测/干净重建+302verifier/三浏览器烟测/证据归档）；SMOKE_BROWSER 参数化；check_site_parity.py 生成漂移门禁；dependabot + npm | P1-CI-001、P2-11 |
| （本条） | PR-5 | readiness_check.py + dr-evidence.schema.json + RISK_REGISTER.md + v17.9.2/v17.10.2 版本提升 + 本目录文档 | P1-OPS 文档化 |

## 测试矩阵（本地实测）

- 站点 Python 套件：234 passed / 6 skipped（PR-1 后）→ 收尾复跑见 05
- Node：wanyu-core + major-city + user-store 26 passed；datastore 14 场景 PASS
- 站点 verifier：302 passed / 0 failed（模板改动后 + 干净重建后各跑一次）
- API 套件：118 passed / 5 skipped（PR-2 后）→ 新增 12 用例后收尾复跑见 05
- 干净重建（python -m build → /tmp）：verifier 302/302，三周期 jobs SHA 与发布 manifest 逐字节一致 → 确定性构建成立
- 不变量：canonical 聚合 SHA 前后一致；业务数字零变化；唯一差异 site_release v17.9.1→v17.9.2（预期）

## 本轮刻意不做（控制 blast radius / 按计划排序）

1. maintainable-site.js 拆分——前 12 阶段未在 CI 全绿前不进大重构（停止规则）。
2. legacy builder 退休——冻结即可，不为"代码漂亮"重构 278KB。
3. provenance attestation / 真 fresh-host / COS 实弹——需要真实云端与服务器操作，本轮只把证据格式和 readiness 判定建好。
4. review queue 7 个缺口——等官方材料，绝不猜数。
5. wan-api 不解除 EXPERIMENTAL——DR 未闭环（R005），CONTRACT 口径不变。
