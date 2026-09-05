# 2026-09-04 补充资料交接验收

## 结论

补充资料已完成本地归档和完整性核验，但“资料回收完成”不等于“正式业务数据已全部合并”。本轮采用证据台账接入方式：正式岗位、成绩、变化和审计基线保持不变；可安全引用的资料、下载阻断和待复核边界在维护站“数据审计”中可见。

## 磁盘与清单核验

- `source_data/supplement_20260904/raw/` 实际有 43 个文件，总计 10,825,379 bytes。
- 其中 41 个为可解析 XLS/XLSX/PDF，2 个为 404 HTML 响应；后者已标记 `blocked`，不作为岗位表。
- `checksums.sha256` 的 43 个哈希条目与 43 个 raw 文件逐项匹配，0 个不匹配、0 个缺失。
- `source_manifest.jsonl` 现有 245 行，其中 43 行引用本轮 supplement，43 个 raw 文件全部覆盖，补充行没有空 SHA-256。
- 代理报告中的“38 个文件”是汇总偏差，已在 `reports/supplement_summary.md` 增加更正段。

可复现结果：

- `source_data/supplement_20260904/integrity_audit.json`
- `tools/anhui_web/build_supplement_evidence.py`
- `tests/test_supplement_integrity.py`

## 集成门禁决定

| 资料类别 | 当前处理 | 原因 |
|---|---|---|
| 合肥、省地矿局、省人社厅、省应急厅等岗位表 | 证据归档，不追加岗位行 | 与现有岗位代码存在重叠，直接追加会重复计数 |
| 拟聘用名单 | 独立 evidence inventory | 这是结果/公示证据，不等同于公开招聘岗位表 |
| 宣城公开选聘名单 | 证据归档 | 公开选聘不改写公开招聘基线 |
| 116 条 `0901xxx` 成绩 | `probable` 证据，继续待复核 | 需要逐条解决六安/马鞍山交叉行归属，不能仅凭代码自动写入 |
| 24 条专业/职位名称候选 | 候选清单 | 未完成官方逐条佐证，不覆盖原值 |

因此 `jobs.json`、`jobs_lite.json`、`positions.json`、`changes.json`、`overview.json` 和 `review-queue.json` 的正式业务记录没有被本轮台账改写。独立 inventory 当前记录 27 批、835 条拟聘用证据，不计入正式岗位总数。

## 前端交付

台账已同步到三套输出：

- `deliverables/maintainable/data/audit/supplement-20260904.json`
- `wan-full-update/site/data/audit/supplement-20260904.json`
- `wan-lite/site/data/audit/supplement-20260904.json`

“数据审计”页面新增“补充证据台账”区块，展示三周期文件分解、可解析资料、阻断下载、哈希匹配、正式入库数和待复核成绩数。Service Worker 已升级为 `wanyu-shell-v30`，脚本指纹改为 `v17.6.4-supplement-evidence`，避免内置浏览器复用旧前端壳。

## 当前仍需说明的阻塞

原始交接包 `E:\zcode\皖域择岗交接包_20260904_v17.6.4.tar.gz` 未修改。包内缺少全量重建所需的部分已审计页面输入，直接运行全量构建器仍会在 2024 周期触发 `CycleBundleError`。本轮因此只同步可追溯的证据模块和已验证前端输出，没有伪造“全量重建成功”。
