# ADR-002：canonical 真源与 API 镜像的发布纪律

- 状态：已接受（Accepted）
- 日期：2026-09-09
- 关联：ADR-001（产品边界）、ADR-003（用户状态）、CONTRACT.md §1/§2、docs/data-contract/*

## 背景

岗位数据有多层呈现：canonical bundle（唯一正式真源）→ 静态站构建产物（jobs.json /
jobs_lite / positions / major_city / audit / …）→ wan-api 数据库镜像表 → 用户查询。
2026-09-09 窗口实测发现一处由**陈旧产物层**引发的门禁污染：`deliverables/maintainable`
停留在 v17.7 时代快照（jobs_lite 含 8511 行 raw 口径），`ui_upgrade_browser_smoke` 的
站点解析曾优先命中它，导致烟测「3,521 ≠ 3,411」的非确定失败——产物层一旦失去
"当前性"纪律，下游所有门禁都会被旧真源喂假信号。

## 决策

1. **canonical/cycles/*.json 是唯一正式数据真源**（wanyu-cycle-bundle/v1 + provenance
   指纹 + sources.lock）。任何层不得反向写回 canonical。
2. **构建产物（HTML/JSON/gz）永远只是 OUTPUT**：任何正式构建禁止读回旧产物作为输入
   （clean_rebuild 事实闸锁定）。产物可以陈旧，但**消费方必须显式声明自己消费哪一层**：
   - 流水线烟测：WANYU_SITE_DIR → 新 staging（已有纪律）；
   - 手动烟测：正式 `网站/`；
   - `deliverables/maintainable` 仅是历史快照，不作为任何门禁的默认对象
     （v17.9.21 已修 ui smoke 解析优先级与 verifier 默认值）。
3. **API 数据库只是 mirror，不是第二真源**：管理员导入必须能逐行回溯到 canonical 行
   （provenance.job_id_set_sha256 指纹强制）；`import_all_data` 三周期缺一不可；
   导入单事务、`imported + updated == rows_total` 对账、失败整体回滚；幂等重跑零漂移。
4. **排除行（record_status≠active）不出现在任何用户口径**：静态产物层按 active 口径
   出数（2026：8401），raw（8511）只存在于审计层；API 镜像同口径折叠为 active/excluded
   二值，排除证据三件套（reason/evidence/excluded_at）随行保留。
5. **镜像可随时重建**：数据库表 = canonical 的纯函数，删除重导必须得到逐行一致的结果
   （e2e_real_data 门禁：二次导入 0 imported / 0 deactivated / review 不翻倍）。
6. 数据差异处置纪律：任何基线数字漂移必须先归因（真数据变化 / 生成器变化 / 版本变化 /
   fixture 变化 / 真实回归），无确定原因不得修改任何一层。

## 理由

- 单向数据流让"哪一层错了"永远可二分定位；双层真源会让每次对账都变成考古。
- 陈旧产物 + 隐式回退（本窗口 P1-003 实证）比没有产物更危险：它看起来在测试产品，
  实际在测试尸体。消费方显式声明 + 门禁默认对象指向正式层，是结构性防御。

## 后果

- 正面：产物层可独立清理/重建而不影响真源；API 重导即修复，无需数据迁移考古。
- 负面：每个新消费方都要回答"你消费哪一层"（一次性认知成本）。
- 中性：deliverables/maintainable 的刷新（流水线重建）留给站长决策，本窗口仅解除其毒通道。

## 合规检查（2026-09-09 实测）

- verify_sources FULL：14 项 sha256 + rollup 一致 PASS。
- validate_canonical_core：三周期守恒 + 基线数字逐一吻合 PASS（2024=10017/10017，
  2025=10150/10150，2026=8511/8401/110）。
- e2e_real_data：三周期导入对账 + 幂等重跑 PASS；verify_maintainable_site（网站/）
  302/302 PASS。
