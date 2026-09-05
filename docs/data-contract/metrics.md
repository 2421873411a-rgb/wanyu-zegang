# 数据事实字典（metrics contract）

本项目所有岗位数量表述自 v17.8.5 起使用以下受控词表。禁止无口径的 `total/posts/count`。

| 术语 | 定义 | 计算口径 |
|---|---|---|
| **raw_posts** | 原始纳入审计的数据记录总数 | jobs.json allMajors.rows 行数（含被排除记录） |
| **active_posts** | 允许进入用户产品统计的有效岗位数 | `record_status` 缺失或 = `active` 的行数 |
| **excluded_posts** | 经证据核验不进入用户统计的记录数 | `record_status` ∈ 排除态的行数 |
| **raw_recruits** | 全部记录的招录人数合计 | sum(num) over raw |
| **recruits** | 有效岗位招录人数合计 | sum(num) over active |
| **score_unresolved** | 成绩无法唯一归属的职位代码数 | 唯一真源：`cycles/<y>/audit.json → scoreLists.keyed.unresolved`（数组的长度或标量），其余位置一律为该值的投影 |

## 不变式（verifier 强制）

1. `raw_posts = active_posts + excluded_posts`
2. 用户全视图（overview/检索/地图/榜单/匹配）岗位总数 = `active_posts`
3. `score_unresolved` 在 manifest/overview/audit(coverage+keyed)/review-queue 五处一致
4. `release.json.release = manifest.release = index ?v = sw VERSION`

## record_status 受控词表

`active`（默认，可缺省）/ `duplicate` / `invalid_source` / `withdrawn` / `superseded` / `needs_review`

排除记录必须携带：`exclusion_reason`、`exclusion_evidence`、`excluded_at`。审计痕迹永不删除。
