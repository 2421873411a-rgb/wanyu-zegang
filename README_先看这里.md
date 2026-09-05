# 皖域择岗 v17.8.6 · 项目入口

> 版本/口径数字一律以自动生成的 [`docs/current-status.md`](docs/current-status.md) 为准（真源：release.json + site-manifest.json + review-queue.json），本 README 不手抄关键数字。

## 先打开哪里

```text
网站/index.html
```

这是当前完整维护站：2024/2025/2026 三周期、岗位检索、为我匹配、岗位地图、待遇对比、城市排行、三年趋势、报考日历、收藏与快照。本地预览：

```powershell
cd .\网站
python -m http.server 18766 --bind 127.0.0.1
# 访问 http://127.0.0.1:18766/?cycle=2026#overview
```

## 构建图（RC3 起的纪律）

```text
canonical/cycles/*.json（唯一正式数据输入，wanyu-cycle-bundle/v1）
  ├─ 维护站（build_maintainable_site.assemble → 网站或空目录）
  ├─ 审计（audit_three_years，canonical 行源）
  ├─ 索引（major_index / job_history，canonical 行源）
  └─ 产物（HTML/JSON/gz 永远只是 OUTPUT，禁止任何正式构建读回）
```

- canonical 种子来源：audited_production_snapshot（见 `docs/migrations/canonical-seed-20260905.md`）。
- 数据源完整性：`sources.lock.json`（文件 sha256 + 目录 rollup）；构建前必跑 `python 项目源码/verify_sources.py`。
- 空目录全链重建门禁：`python 项目源码/tools/anhui_web/clean_rebuild.py`（事实闸 + verifier）。
- 正式发布：`python 项目源码/tools/anhui_web/release.py`（缺 Chromium 必 FAIL；`--allow-missing-browser` 会标记 degraded_validation 且禁止打正式 tag）。

## 目录

- `网站/`：部署形态维护站（canonical 全链产物）。
- `项目源码/`：canonical 数据真源、构建工具、测试、文档（`tools/anhui_web/` 为工具链核心）。
- `docs/`：契约（data-contract）、审计证据（audit）、迁移证明（migrations）、当前状态（current-status.md）。

## 当前数据边界（摘要，详见 current-status.md）

- 2026：110 条跨市重复收录行带完整生命周期证据（record_status=duplicate），退出一切用户口径，保留于 raw 审计层。
- 116 条撞码成绩已全部归属（公告来源定市），进入 resolution_history；active gap 归零。
- 待官方职位表核对后可物理删除 110 行（站长动作）；legacy_v11/冻结单文件快照的恢复介质=COS 月备/另一设备。

## 历史文档

`交接包清单.txt`（v17.6.5~17.7.0 修订史）、`docs/audit/`（RC1/RC2/RC3 审计与失败映射）保留作历史证据；入口以本文档为准。
