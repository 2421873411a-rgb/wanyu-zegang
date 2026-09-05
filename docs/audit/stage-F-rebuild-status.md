# 阶段 F：全链重建验证（v17.8.5）

## 结论：BLOCKED_BY_EVIDENCE（部分）

任务书 F1 要求「删除旧网站后从源码重建」。当前状态：

### 受阻环节（证据）
1. `unified_cycle_bundle.py:150-168` 需要输入 `deliverables/legacy_v11/皖域择岗总览.html`
   （或 `安徽公考数据网页/`、`deliverables/` 候选）——本仓库均不存在。
2. 该输入是历史单文件页工件，随 2026-09-05 凌晨另一设备的工作区灾难丢失。
3. 因此 build_pages.py → bundle → maintainable 全链在本机不可执行；test_maintainable_site
   的一键重建用例同样因缺输入挂（已知的 4-6 个环境性 ERROR 即此）。

### 未受阻、且本轮已完成的验证
1. 现树 `verify_maintainable_site.py` 255/255（含本轮新增 17 条语义不变式：
   unresolved 五位一致 / raw=active+excluded / 版本四链一致 / overview.active 口径）。
2. `check_release.sh` 全绿（版本链 release.json=v17.8.5=manifest=index ?v=SW v48）。
3. `check_secrets.sh` 干净；磁盘校验器通过。
4. `fetch_sources.py --verify` 10 项源锁全部一致。
5. `build_major_index.py` 三周期 record_status 口径重建 PASS。
6. 内置浏览器人工/脚本走查：检索三级匹配、画像、收藏提醒、日历、匹配榜、决策条全过。

### 恢复全链重建所需（列给下一任）
- 从 COS 月备或另一设备找回 `deliverables/legacy_v11/{2024,2025,2026}/皖域择岗总览.html`，
  或修改 `unified_cycle_bundle._candidate_files` 接受新的工件来源——
  该改动影响数据真源定义，须站长确认后实施（勿在收口批次顺手改）。
