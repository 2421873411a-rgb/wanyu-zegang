# 皖域择岗前端数据全量审计与修复计划

> 目标：在不改写源事实、不把未知值补成 0 的前提下，审计并修复 full-update 与 wan-lite 维护站的前端数据链路，重点解决“三年对照”在考试筛选下的城市拆分、年度汇总错口径和辅助工具未跟随细分筛选的问题。

## 已复现的根因

1. `maintainable-site.js` 的 `slopeGraph()` 在“事业编/上半年”或“下半年”筛选时直接使用 `row.city`，没有复用 `mapCityFor()`；2024 年存在县区级城市值，导致同一地市被拆成多行，其他年份显示为 `—`。
2. `renderCompare()` 的“三年数据概况”直接读取 manifest 的全周期 `posts/recruits`，但标题带有当前考试筛选；筛选后的岗位数和招录人数因此与表头不一致。
3. 对照页的竞争热力图/城市对比工具只接收 `examFilter`，没有接收 `examSub`，选择上半年或下半年时会把事业编全年数据混入辅助表。
4. 全局考试口径没有贯穿总览、岗位榜单和岗位检索；地图和三年趋势会筛选，其他岗位视图仍展示全量行。
5. 对照年度表的行已经输出“公开缺口、待复核成绩、外置模块”三组信息，但表头只有三列，造成数据列无语义对应。
6. 部分源表未单列职位名称时，检索表直接显示空白，没有显示已有的 `display_title` 安全状态文案；这是真实来源缺口，前端应明确显示而不是留下视觉空洞。

## 数据基线（审计前读取）

- 周期：2024、2025、2026。
- 岗位/招录：10,017/15,331、10,150/14,721、8,511/12,006。
- 事业编上半年岗位：4,819、4,840、3,521；下半年：396、651、655。
- `jobs.json`、`jobs_lite.json`、`positions.json`、`palette.json` 的稳定 ID 与行数需逐周期对账；`derived.city_trend` 必须与 mapped/unmapped 行数守恒。
- 已知公开边界和 2026 年 116 条无法唯一匹配成绩必须继续显示为边界/待复核，不进行数据补造。

## 执行任务

### Task 1：建立全模块数据质量回归门禁

**文件：**

- 新增 `tests/test_frontend_data_audit.py`
- 新增 `docs/audits/2026-09-04-frontend-data-audit.md`

**检查内容：**

- manifest 中三周期、模块路径、字节数和 SHA-256 与磁盘一致。
- jobs/lite/positions/palette/major_city 的行数、ID 集合、招录合计和来源哈希一致。
- overview 元数据、examCounts、derived mix 和 city trend 可由 jobs 行复算。
- 事业编上半年/下半年及公务员子口径的三年计数可复算。
- changes 的 base/target ID 均能回到对应周期岗位行。
- 明确统计源字段缺失（如职位名称未单列）与前端静默空白不是同一类问题。

**命令：**

```powershell
python -m unittest tests.test_frontend_data_audit -v
```

先写出会锁定当前问题的失败断言，再实现修复；数据剖面结果写入审计报告，保留可检查的计数和证据路径。

### Task 2：统一前端考试口径和地市归并

**文件：**

- 修改 `tools/anhui_web/templates/maintainable-site.js`
- 修改 `tools/anhui_web/templates/v17-tools.js`
- 修改 `tests/maintainable_browser_smoke.js`

**实现：**

- 增加复用 `mapCityFor()` 的趋势城市键；筛选趋势按地市聚合，保留“省直”，未知城市不静默丢弃。
- 对照页年度汇总按当前 `examFilter + examSub` 从各周期 jobs 复算岗位数/招录人数。
- 变化摘要按目标/基准岗位 ID 回查并按当前口径统计；公开缺口和成绩待复核仍标注为周期级证据。
- 将当前考试口径传给 v17 辅助工具，并让上半年/下半年标题、热力图和城市对比共用同一行筛选。
- 总览、岗位榜单、岗位检索统一使用 `scopeExamPayload()`；待遇地图和审计视图保留各自独立口径并在界面说明。
- 对照年度表补齐列头和筛选口径说明，避免裸数据列。
- 检索表对职位名称使用 `row.zw || row.display_title || '源表未单列披露'`，保留来源状态。

### Task 3：补浏览器端数据回归

**浏览器断言：**

- 进入三年对照，选择“事业编 → 上半年联考”，三年概况显示 4,819/4,840/3,521 岗及 6,345/6,028/4,323 人。
- 对照趋势只出现归并后的地市，不出现把 2024 县区值拆成独立行；辅助工具显示同一上半年口径。
- 切到下半年，显示 396/651/655 岗，并且趋势、热力图、城市表同步切换。
- 切换到总览、榜单、检索，计数继续遵守当前考试口径；清空/切换周期后恢复对应全量。
- 继续验证详情、收藏、审计中心、响应式宽度和无远程资源。

**命令：**

```powershell
node tests/maintainable_browser_smoke.js
node tests/ui_upgrade_browser_smoke.cjs
```

### Task 4：重建、同步和静态验收

**动作：**

- 用当前统一构建器重建 `wan-full-update/site` 与 `wan-lite/site`，不修改 `E:\zcode\皖域择岗交接包_20260904_v17.6.4.tar.gz` 源包。
- 校验模板、full-update、wan-lite 资产一致，Service Worker 预缓存版本与 JS 查询指纹一致。
- 运行 Python/Node 语法检查、模块磁盘校验、性能预算和完整相关测试。

**命令：**

```powershell
python -m py_compile tools/anhui_web/build_maintainable_site.py
node --check tools/anhui_web/templates/maintainable-site.js
node --check tools/anhui_web/templates/v17-tools.js
python tools/anhui_web/verify_maintainable_site.py ..\site
python tools/anhui_web/verify_maintainable_site.py ..\..\wan-lite\site
python tools/anhui_web/perf_budget.py ..\site
```

### Task 5：内置浏览器最终验收

- 刷新带新资产指纹的本地服务，在内置浏览器逐项点选 2024/2025/2026、事业编上半年/下半年、三年对照、地图、总览、检索和详情。
- 记录实际显示计数、当前 URL、截图/可访问性树和页面错误状态。
- 最终报告区分“源数据未发布/无法唯一匹配”与“前端曾经漏算但已修复”，不宣称官方数据全部补齐。

## 完成定义

- 全部核心岗位视图对同一全局考试口径显示一致的行数和招录人数。
- 三年对照按真实地市归并，不因跨年城市粒度差异制造假缺失。
- 所有模块数据链路通过行数、ID、招录、哈希和派生守恒检查。
- Python、Node、浏览器、磁盘校验和内置浏览器实测均有新证据。
- 报告、计划和交接材料记录修复范围、剩余真实边界和可复现命令。
