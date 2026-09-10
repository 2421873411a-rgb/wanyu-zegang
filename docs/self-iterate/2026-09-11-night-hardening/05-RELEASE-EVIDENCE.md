# 05 · 发布证据（RC1：v17.9.2 网站 / v17.10.2 API）

> 本轮为工程 RC：未提升正式 tag（按发布纪律，PR 合入 main 且 CI 全绿后才打 tag）。

## 机器验证记录（2026-09-11 本地实测）

| 门禁 | 结果 |
| --- | --- |
| 站点 Python 全套（tests/） | 235+ passed / 6 skipped（doc gate 修复后 2/2 PASS） |
| Node 契约（core/major-city/user-store） | 26 passed / 0 failed |
| DataStore 完整性矩阵 | 14 scenarios PASS |
| 站点 verifier | 302 passed / 0 failed |
| API 全套（ENV=test, SQLite） | 128 passed / 7 skipped（PG 专属并发测试 SQLite 下 skip，CI postgres job 实测） |
| 生成漂移门禁 check_site_parity | PASS（12 复制资产 + sw.js + 54 gz 伴生） |
| 干净重建 → verifier | 302/302，三周期 jobs SHA256 与发布 manifest 一致（确定性构建） |
| 业务不变量 invariants.py | canonical 聚合 SHA `fe2303a3…` 前后一致；2024=10,017 / 2025=10,150 / 2026 raw 8,511 · active 8,401 · excluded 110 · recruits 11,883 · score unresolved 0 · review queue 7 open/1 high-risk——零变化 |
| 文档真源门禁 doc_truth_gate | 2/2 PASS（README v17.9.2 + current-status.md 重生成） |

## 已知剩余风险（如实）

1. Firefox/WebKit 烟测本地未跑（引擎未安装），由 site-release-gate 在 GitHub runner 上首跑；若 WebKit 大面积失败，按停止规则保持旧 release、分支修复。
2. snapshot 配额/compare 槽位并发测试仅在 CI postgres job 生效，本地 SQLite 跳过。
3. nginx 分层配置改动需在下次真机部署时经 `nginx -t` + 冒烟验证。
4. DR 仍未闭环：无 COS 异地副本证据，dr_ready=false（R005），wan-api 保持 EXPERIMENTAL。
5. 上一版 stash@{0}（2026-09-10 同步前本地 WIP）仍保留，确认不需要后可 drop。

## 提升清单（合并后动作）

- [ ] site-release-gate 成为 main 必需检查（branch protection 增加同名 context）
- [ ] RC2 破坏性验证（corrupt-site / SW 旧缓存 / Redis stop / DB commit 异常）
- [ ] 打 tag v17.9.2（site）与 v17.10.2（api），release 页贴本文件
