# 皖域择岗 成熟度窗口报告（12:00–21:00 规范窗口）

- 实际执行：2026-09-09 00:50–02:55 (+0800)（接管预检 00:39 起；规范窗口的时钟块作为阶段预算执行）
- 结论一句话：**STAGING_READY 达成**——数据/构建/测试/staging 流程全绿，两个 P1 基础设施级门禁缺陷与三个 P1 部署链缺陷修复并全部合入 main（v17.9.21，main=369be13）；生产证据按红线 14（不连生产）本窗口不可取得，**未宣称 Production Ready**。

## 1. 本轮实际读取和审计的目录

- 仓库根 `E:\zcode\择岗`：README_先看这里.md、docs/current-status.md、docs/architecture/**（新增 ADR 三篇）、.github/workflows/{wan-api-ci,canonical-ci}.yml、docs/self-iterate/（近 7 轮运行产物）
- `项目源码/`：release.json、canonical/cycles/{2024,2025,2026}.json + schema.json、sources.lock.json、verify_sources.py、tests/（40 个文件，重点 8 个 cjs）、deliverables/CHANGELOG.md、deliverables/maintainable（陈旧快照取证）
- `项目源码/wan-api/`：README.md、docs/CONTRACT.md、docs/ops/RUNBOOK.md、release.json、deploy.sh（六处修改）、scripts/{backup_database,restore_drill,upgrade_drill}.sh、tests/（11 个文件全部）、app 门禁全量运行
- `项目源码/tools/anhui_web/`：validate_canonical_core.py、clean_rebuild.py、verify_maintainable_site.py（修改）、release_pipeline.py（门禁链审计）
- `网站/`：index.html、assets/（maintainable-site.js、maintainable-user-store.js 等注入面定向扫描）、data/（manifest 与 2026 数据对账）
- 远端：GitHub 仓库 check-runs/PR API（REST）

## 2. 当前 commit 和版本

- **main = 369be13**（v17.9.21，PR#22 squash）；上游链：bef9fe9(v17.9.19) → b5e3ece(v17.9.20, PR#21) → 369be13(v17.9.21, PR#22)
- 网站产品版本：v17.9.0（项目源码/release.json，未动）
- API 版本：**v17.9.21**（wan-api/release.json；版本单一真源纪律保持，两源未捆绑）

## 3. 当前数据基线（canonical 实测，与站长口径一致）

| 周期 | raw | active | excluded | 有效招录 |
|---|---|---|---|---|
| 2024 | 10017 | 10017 | 0 | 15331 |
| 2025 | 10150 | 10150 | 0 | 14721 |
| 2026 | 8511 | 8401 | 110 | 11883 |

salary=160 条；review queue open=7；零差异、零修改（canonical 原文未动一字）。

## 4. 已发现的问题（详见 findings.json）

- P1-001 Windows 下 fake-bin 注入静默失效（本地基线红 6 failed）
- P1-003 ui 烟测把陈旧 deliverables 快照置于正式 网站/ 之前（长期在测死站）
- P1-002 deploy.sh 切换先于迁移/导入/冒烟且无自动回滚
- P1-004 静态数据前置只查 cycles 目录（名不副实）
- P1-005 deploy.sh 生成的 unit 缺 PrivateTmp=true（fresh-host 重装即回退已知崩溃）
- P2-002 deliverables 陈旧快照（v17.7 产物混装）；P2-005 verifier 无失败明细+默认目标错位
- 部署审计 PARTIAL×3（状态文件/迁移位次/nginx 缺席分支）→ DEPLOY-AUDIT-PARTIAL
- 假设被证伪撤回 ×2：P2-004（瞬闪）、P2-006（CSV 公式）——证伪纪律两次拦住错误修改

## 5. 已修复的问题

P1-001、P1-003（PR#21，v17.9.20）；P1-002、P1-004、P1-005、P2-005、smoke 302 目标钉死（PR#22，v17.9.21）。全部按「先写失败测试→修根因→全量验证」执行：新增回归测试 4 条 + 假设验证探针 3 个。

## 6. 未修复的问题

- P2-002 deliverables 快照本体刷新（103 个 git 跟踪文件的机械重建，留站长决策；毒通道已切断）
- DEPLOY-AUDIT-PARTIAL：部署状态持久化文件（候补）；迁移位次维持 stop-window 设计（改动收益<风险，受 MIGRATION_DONE 门保护）；nginx 缺席分支保持 WARN（分步适配模式契约）
- CONTRACT §7 未勾选项：S8 真机、COS 异地、密钥轮换（见 §7 阻断项）

## 7. 被环境阻断的测试（BLOCKED_BY_ENVIRONMENT）

- BLK-001 本机 PG16/Redis7：docker/psql/redis-cli 缺失 → 证据通道 = CI postgres job 三次 success（真 PG16+Redis7+redis 限流全量）
- BLK-002 upgrade_drill.sh 真机执行：需 Linux root → 语义由 ops/linkage 测试覆盖（19+16 条），真机演练列入下轮
- 灾备真机复核（restore drill / COS 异机）：红线 14 禁连生产 → 不可取得（非环境缺失，为任务约束，两者均已如实区分记录）

## 8. 所有验证命令和结果（终局全量，见 verify/final-sweep-*.md）

| 门禁 | 结果 |
|---|---|
| verify_sources --manifest-only / FULL | PASS / PASS（14 项 sha256+rollup） |
| validate_canonical_core | PASS（守恒+基线吻合） |
| e2e_real_data（三周期+幂等+对账） | PASS |
| verify_maintainable_site（网站/） | 302 passed 0 failed |
| clean_rebuild（空目录全链重建） | EXIT=0（含内嵌 3 smoke PASS） |
| node --test ×4 契约套件 | PASS ×4 |
| 浏览器 smoke ×3（含修复后 ui smoke 3/3 + staging 模式） | PASS ×3 |
| pytest（SQLite 全量） | 101 passed + 5 skipped |
| pytest（PG16+Redis7 真实后端） | PASS（CI postgres job：PR#21/22/main 三次 success） |
| ruff（E9,F63,F7,F82） | All checks passed |
| bash -n（deploy.sh + scripts ×3） | OK ×4 |
| alembic upgrade/check/downgrade/upgrade/check | EXIT=0（无漂移） |
| pip-audit --strict（runtime + dev 双 lock） | 0 已知漏洞 ×2 |
| main CI 三 required（369be13） | test/canonical/postgres 全 success |

## 9. 变更文件（已全部合入 main）

- PR#21（v17.9.20）：`wan-api/tests/test_ops_scripts.py`、`tests/ui_upgrade_browser_smoke.cjs`、`wan-api/release.json`、`deliverables/CHANGELOG.md`
- PR#22（v17.9.21）：`wan-api/deploy.sh`（回滚/前置/unit/smoke 六处）、`wan-api/tests/test_ops_scripts.py`（+3 行为测试）、`wan-api/tests/test_deploy_linkage.py`（+1 不变量测试）、`tools/anhui_web/verify_maintainable_site.py`、`wan-api/release.json`、`deliverables/CHANGELOG.md`
- PR#23（本 PR，纯证据/文档）：docs/architecture/ADR-001/002/003、docs/self-iterate/2026-09-09-12to21-maturity/**（本报告与全部证据）

## 10. 生成的 evidence 文件

verify/：phase4-pytest-baseline.md、phase4-pytest-after-fix.md、phase6-clean-rebuild.md、phase8-ci-pr21.txt、phase9-upgrade-drill.md、final-sweep-part1/2/3.md
findings/：probe-map-facts.cjs、probe-variant-detail.cjs、probe-exact-flow.cjs（三步证伪链全存档）
findings.json、baseline.json、maturity-matrix.md、本报告、state.json、RESUME.md
（artifacts/served-jobs-lite.json 为 7MB 临时对账副本，提交前删除，可由命令复现）

## 11. 当前成熟度等级

**STAGING_READY**。判级上界论证：CONTRACT §7 生产前置（fresh-host/PG restore/COS 异机/回滚真机/公网 smoke）全部需要生产访问，红线 14 封死取证通道；历史 PASS 已被本项目自身撤回（v17.9.19 CHANGELOG），不可继承。

## 12. 下一轮只做什么

1. fresh-host 演练（v17.9.21 代码）：部署 + 升级漂移 drill + **触发一次人为失败的自动回滚验证**（rollback_to_previous 从未真机走过）
2. restore drill 真机复核 + COS 异地副本配置与异机恢复演练（CONTRACT §7 闭环）
3. deliverables/maintainable 流水线刷新 + 部署状态持久化文件（候补）
4. 全部通过后才允许生产部署决策（v17.9.21）

## 13. 是否允许部署

**不允许**。缺 §17 生产证据闭环；且 v17.9.21 的自动回滚/前置硬化需先经 fresh-host 演练验证。站内静态站产品（网站/ v17.9.0）不受影响。

## 14. 生产环境声明

**本窗口未连接生产服务器、未修改生产数据库、未部署任何东西到线上**（红线 14/15 全程遵守；服务器相关操作为零）。生产 wan.kaogong.art 仍运行 v17.9.18，与本轮 main（v17.9.21）存在版本差，属已知待部署状态。

---

最终声明（规范 §14 原文）：
**本轮完成代码和测试层成熟化，但未宣称 Production Ready；剩余阻断项是 fresh-host 部署演练、真实 PostgreSQL restore 复核、COS 异地副本与异机恢复、升级失败回滚真机验证、公网 smoke——全部因红线 14（不连生产）无法在本窗口取得。**
