# 成熟度矩阵 · 2026-09-09 窗口

| # | 维度 | 状态 | 证据 |
|---|---|---|---|
| 1 | 数据真源（canonical schema/守恒/指纹/排除证据） | ✅ PASS | verify_sources --manifest-only PASS；verify_sources FULL PASS（14 项）；validate_canonical_core PASS，三周期数字与基线逐一吻合（10017/10150/8511-8401-110） |
| 2 | canonical↔网站对账 + manifest 哈希 | ✅ PASS | verify_maintainable_site（网站/）302 passed 0 failed |
| 3 | 真数据端到端（三周期导入/MirrorState/salary=160/review=7/幂等） | ✅ PASS | e2e_real_data EXIT=0 |
| 4 | 静态站全链重建（只读 canonical/零自签） | ✅ PASS | clean_rebuild EXIT=0（promote=False→tmp，内嵌 3 smoke PASS） |
| 5 | 前端纯函数契约（node ×4） | ✅ PASS | final-sweep-part1 全 PASS |
| 6 | 浏览器门禁（三 smoke：三周期走查/地图/搜索流/移动端） | ✅ PASS | final-sweep-part3 全 PASS（ui smoke 修复后确定性） |
| 7 | API 静态门禁（ruff/bash -n ×4/alembic 往返+漂移） | ✅ PASS | final-sweep-part2：RUFF-OK、4×OK、ROUNDTRIP_EXIT=0 |
| 8 | API 全量测试（SQLite） | ✅ PASS | 101 passed + 5 skipped（5 skip=PG/Redis 专属用例，非业务跳过） |
| 9 | API 全量测试（PG16+Redis7 真实后端） | ✅ PASS（CI 通道） | CI postgres job：PR#21/PR#22/main 369be13 三次 success（RATE_LIMIT_BACKEND=redis） |
| 10 | 依赖安全（pip-audit 双 lock strict） | ✅ PASS | 两 lock 均 No known vulnerabilities |
| 11 | 部署链 20 项清单审计 | ⚠️ 审计完成→修复落地 | FAIL×4（自动回滚/前置校验）+PARTIAL×4 → P1-002/004/005 + smoke 钉死修复（PR#22）；PARTIAL #1 状态文件、#4 迁移位次、#13 nginx 缺席分支记 DEPLOY-AUDIT-PARTIAL |
| 12 | 升级漂移演练（upgrade_drill 真机） | ⛔ BLOCKED_BY_ENVIRONMENT | 需 Linux root；语义由 ops/linkage 测试覆盖；真机演练列下轮 |
| 13 | 灾备链（备份 checksum/restore drill） | ⚠️ 代码层 PASS/真机证据未复核 | backup/restore 行为 19 条 ops 测试 PASS；真机 restore drill 本窗口不可连生产（红线 14） |
| 14 | 前端安全与 UX 抽查（innerHTML 12 sink/escapeHtml ×241/hash 键查找/CSV 公式防护） | ✅ PASS | 定向扫描 findings 记录；CSV 防护由契约测试锁定 |
| 15 | 架构决策记录（ADR） | ✅ DONE | docs/architecture/ADR-001/002/003 |
| 16 | 文档同步（CHANGELOG/RUNBOOK/README 状态） | ✅ PASS | CHANGELOG v17.9.20/v17.9.21；README 顶部状态为窗口前写入且与 CONTRACT §7 一致 |
| 17 | 生产资格（fresh-host/COS 异机/回滚/公网 smoke 可复现证据） | ❌ GAP | 红线 14 禁连生产→本窗口不可取得；历史证据属 v17.9.18 时代且不可继承 |

## 判级

- **STAGING_READY**：代码、构建、测试、staging 流程全部可用且本窗口全绿；生产证据存在缺口（#17）。
- 上界论证：CONTRACT §7 的 fresh-host/COS 异机/回滚/公网 smoke 均需生产访问，红线 14 已封死；按规范 §14 判级表，生产证据不完整时最高为 STAGING_READY。
