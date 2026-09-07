# record_status 生命周期契约（wanyu-record-status/v1）

> 生效版本：v17.9.11（词表自 v17.8.5-RC2 起未变；v17.9.11 补 DB 层折叠契约）。
> 唯一 Python 实现：`项目源码/tools/anhui_web/record_lifecycle.py`；
> API 侧白名单镜像：`项目源码/wan-api/app/services/import_service.py` `_VALID_RECORD_STATUS`。
> 前端 `isActiveRow()` 只是**防御层**，不是业务正确性的唯一来源（用户模块数据本身必须 active-only）。
> 排除证据外置构建输入：`项目源码/tools/anhui_web/data/record_status_overrides.json`。

## 一、状态集与判定

```
record_status 缺失 或 "active"  => active
duplicate / invalid_source / withdrawn / superseded / needs_review => 排除出用户口径
```

- Python：`record_status_of(row)` / `is_active_record(row)` / `split_records(rows)`。
- **DB 层折叠（wan-api，v17.9.11）**：导入时上述 5 个排除态与 DB 派生态 `excluded`
  一律折叠为二值 `record_status ∈ {active, excluded}`；源侧具体排除态连同
  `exclusion_reason / exclusion_evidence / excluded_at` 三件套原样落库供审计。
  被后续快照移除的行记 `exclusion_reason='snapshot_removed_in_later_snapshot'`、
  证据=新快照 source_sha256。公共查询只见 active；excluded 仅管理/审计入口可见。
  扩展词表必须先改本契约 + `record_lifecycle.ALLOWED_STATUSES` + API 白名单三处。
- JS（防御层）：`isActiveRow = (row) => !row || !row.record_status || row.record_status === "active"`。
- 未知新状态值按“排除”处理并必须先补进本契约，禁止前端静默放行。

## 二、状态 × 模块矩阵

| 状态 | 定义/证据要求 | 用户统计 | 搜索(lite) | 地图/趋势/榜单 | 详情访问 | 收藏 | 审计(jobs raw) |
|---|---|---|---|---|---|---|---|
| active | 无标记或显式 active | 是 | 是 | 是 | 是 | 是 | 是 |
| duplicate | 与他源同岗重复收录；必须给 exclusion_reason/evidence/excluded_at | 否 | 否 | 否 | 否（raw 源可查） | 否 | 是 |
| invalid_source | 来源被认定无效 | 否 | 否 | 否 | 否 | 否 | 是 |
| withdrawn | 官方撤岗 | 否 | 否 | 否 | 否 | 否 | 是 |
| superseded | 被修正行取代 | 否 | 否 | 否 | 否 | 否 | 是 |
| needs_review | 待复核（当前无存量） | 否（按本契约保守排除；若未来需要展示待复核，须先定义 review 三态并改契约） | 否 | 否 | 否 | 否 | 是 |

## 三、口径与守恒式（wanyu-metrics/v1）

- `raw_posts = active_posts + excluded_posts`（2026：8511 = 8401 + 110）。
- `recruits` = active（有效岗位）招录人数；`raw_recruits` = 含排除行（2026：12006 / 11883）。
- manifest 周期条目：`posts` 仅为 `active_posts` 的兼容别名（deprecated），禁止按 raw 解读。
- 用户口径模块（overview/jobs_lite/catalog/positions/major_city/major_index/derived/changes/palette/trend/ranking）一律 active-only；
  `jobs.json` 保留 raw 行（审计真源，排除行带完整生命周期四字段）。

## 四、生命周期标记的唯一合法来源

1. 构建输入 `record_status_overrides.json`（schema wanyu-record-status-overrides/v1）：
   每 cycle 列 `duplicate_job_ids` + `exclusion_reason/exclusion_evidence/excluded_at`，禁止无证据排除。
2. builder 在业务派生前调用 `apply_overrides(rows, overrides, cycle)`；幂等，且与已带标记的行做一致性断言。
3. 现存 110 行（2026）来自华图快照 `source_note`「疑似重复收录」标注，overrides 生成时与该标记交叉核对（`gen_record_status_overrides.py`）。

## 五、禁止事项

- 禁止对网站产物直接加 record_status 字段而不经过 overrides + builder（外科手术）。
- 禁止让前端过滤成为排除的唯一防线。
- 禁止 `needs_review` 在未经契约修订的情况下进入任何用户模块。
- 排除行进入审计工件时必须保留四字段（record_status/exclusion_reason/exclusion_evidence/excluded_at）。
