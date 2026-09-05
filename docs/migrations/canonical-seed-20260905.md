# canonical 种子迁移证明（canonical-seed-20260905）

> 阶段 G（任务书「如果永远找不回来」分支）。migration_origin = **audited_production_snapshot**。
> 本文档声明：canonical 不是 raw official source rebuild，也不冒充它。

## 一、为什么种子迁移

legacy_v11（`deliverables/legacy_v11/皖域择岗总览.html`，v12 单文件页面的数据载体）在设备灾难中丢失。
恢复尝试（2026-09-05 穷尽）：百度网盘全库文件名检索 `*总览*`/`deliverables`（仅 20260905 快照，与本机一致、无 legacy）、
本机工作区（无任何 legacy HTML/历史压缩包）、E 盘（不存在）。剩余途径只有 COS 月备回捞/另一设备（站长动作）。

若未来 legacy 被找回：执行一次 `legacy → parse → canonical → hash freeze` 对账后，canonical 以 legacy 为准重播种（--force），
本文档追加"legacy 恢复重播种"一节。在那之前 canonical 是唯一正式数据输入。

## 二、种子内容与冻结哈希（baseline commit 7ef107f）

| 周期 | canonical 文件 | canonical sha256(前16) | 种子 jobs.json sha256(前16) | job_id 集合 sha256(前16) | 事实 |
|---|---|---|---|---|---|
| 2024 | canonical/cycles/2024.json | e2774daecb82880a | bb02d6397471222a | 0cbe022e2fda407f | raw 10017 = 10017 + 0；recruits 15331/15331 |
| 2025 | canonical/cycles/2025.json | b5507bebfb8e6169 | bc74938447eb437b | 91d1355e9a6ac022 | raw 10150 = 10150 + 0；recruits 14721/14721 |
| 2026 | canonical/cycles/2026.json | 733abcc8d417a0af | adc38573f9c5f568 | 230697a751445824 | raw 8511 = 8401 + 110；recruits 11883/12006 |

score_state 引用（loader 逐次校验 sha）：2026 → `tools/anhui_web/data/score_lists.json`（4d6d85dfe3d69f48，与 sources.lock 一致）；
2024/2025 → `tools/anhui_web/data/cycles/{c}/score_lists.json`（5452a443f91019b5 / f03747201e06bd3d）。

## 三、种子输入的审计依据

- 行数据：RC2 再生后的生产 raw 行（`网站/data/cycles/{c}/jobs.json allMajors.rows`）——其正确性由
  RC2 门禁链背书：verifier 294/0、110 生命周期证据（overrides × source_note × D2 交叉核对）、
  keyed.resolution_20260905（116/116/0）、冻结基线 10017/10150/8511、标定断言（行级公式复现 bundle 原始 meta）。
- cycleInfo/label：来自生产 overview（v12 构建期快照字段，非派生计数）。
- 城市维度：行内 city 已归一化（16市+省直，off_dimension_source_values 三周期均为空）；source_city 回填列入后续（canonical schema 已留位）。

## 四、哪些事实可以继续验证 / 哪些不能

**可以（canonical 之上的全部构建与门禁照常）**：active 口径全模块、生命周期守恒、unresolved 全投影、
目录 rollup、clean rebuild 事实对比（8511=8401+110/12006/11883/0/116）、浏览器烟测。

**不能（诚实登记）**：
1. 从 `source_data/` 零成本重放 2026 行的跨会话累积修正历史（哨兵 629 复活合并、city_norm、D2 打标的中间路径）——
   修正结果已冻结在 canonical 行内，重放引擎属 v17.9+ 结构化构建链任务。
2. v12 单文件页面的 page_content（legacy 页面模板）——单文件保持 7ef107f 冻结快照，重建引擎列入 v17.9。

## 五、纪律

- canonical 文件是**输入**：任何构建产物（lite/catalog/manifest/positions…）变更不得回写 canonical。
- 重播种仅允许两种触发：legacy 恢复对账（以 legacy 为准）或全量数据迁移（专项设计+证据），均需 `--force` 并更新本文档。
- `gen_canonical_bundles.py` 拒绝从任何派生模块读取（只读 jobs.json rows/overview cycleInfo/审计与分数文件引用）。
