# 00 · 冻结基线（2026-09-11 夜间工程加固）

本轮为**纯工程升级**：不触碰岗位事实数据，不人工修改 canonical 业务数据，不为清 review queue 猜数据。

| 项目 | Baseline |
| --- | --- |
| main SHA | `9f87d77263870c37478d0f5fe2b7bf830f8141a2`（PR #45 合并点，Git Bash 部署路径修复） |
| 工作分支 | `hardening/night-20260911`（自 main@9f87d77 切出） |
| 网站 release | v17.9.1（`项目源码/release.json`） |
| API release | v17.10.1（`项目源码/wan-api/release.json`） |
| Required checks（GitHub main） | test / canonical / postgres |
| 前端正式入口 | `网站/`（静态站，唯一正式产品，ADR-001） |
| 数据真源 | `项目源码/canonical`（ADR-002，本轮零变更） |
| API 状态 | experimental / staging（本轮**不**解除） |
| 本地工具链 | Python 3.12.10 · Node v24.19.0 · npm 11.17.0 · pytest 9.1.1 |
| 本地数据源 | `项目源码/source_data` 存在（交接包携带，gitignored） |

## 业务事实不变量（收工前必须逐项复核）

以下数字取自基线 `网站/data/site-manifest.json` 与 review queue，本轮结束时必须**逐字相同**：

- 2024 岗位：10,017
- 2025 岗位：10,150
- 2026 raw：8,511 · active：8,401 · lifecycle excluded：110 · effective recruits：11,883
- score unresolved = 0
- review queue：open event = 7 · high risk = 1 · resolved score collision = 116

## 停止规则

- canonical 目录出现 diff → 立即停止该改动
- 无法解释的岗位数量变化 → 回到最近绿色 commit
- DataStore SHA 改造导致 WebKit 大面积失败 → 不关闭 SHA，保持旧 release 继续在分支修
- 事务重构波及大量普通 endpoint → 收缩到 admin import 范围
- 前 12 个核心阶段未全绿 → 不进入大规模 JS 拆分
