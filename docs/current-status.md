# 皖域择岗 · 当前状态（由真源自动生成，勿手改）

> 生成器：`项目源码/tools/anhui_web/generate_status_doc.py`；真源：release.json + site-manifest.json + review-queue.json。
> 真源快照：release **v17.8.6** · asset **17.8.6** · SW **wanyu-shell-v49** · 数据快照 2026-08-31。

## 口径（wanyu-metrics/v1）

| 周期 | raw_posts | active_posts | excluded_posts | raw_recruits | recruits（有效） | score_unresolved |
|---|---|---|---|---|---|---|
| 2024 | 10017 | 10017 | 0 | 15331 | 15331 | 0 |
| 2025 | 10150 | 10150 | 0 | 14721 | 14721 | 0 |
| 2026 | 8511 | 8401 | 110 | 12006 | 11883 | 0 |

## 复核队列

- open 事件：**7**（high_risk 1）
- resolved 历史：**1** 项（resolved_score_count=116，unresolved_score_count=0）
- 公开边界（manifest gaps 合计）：**7**

## 边界声明

- `posts` 是 `active_posts` 的兼容别名（deprecated），用户口径=active；raw_* 仅审计层。
- canonical 周期包为唯一正式数据输入（migration_origin=audited_production_snapshot，见 docs/migrations/canonical-seed-20260905.md）。
- HTML 永远只是 OUTPUT；网站成品与单文件快照都不是任何正式构建的输入。
