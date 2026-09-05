# 皖域择岗档案观测台持续迭代 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在离线和语义保真的边界内，修复移动导航、深链容错、岗位对比篮和导出反馈，使观测台更可靠、更易用。

**Architecture:** 继续使用现有原生 HTML/CSS/JavaScript 模板和构建时内联数据；状态校验集中在各产品脚本入口，对比篮状态仅由岗位检索页管理，公共壳层只提供既有页面数据解析和通用导航样式。测试沿用 Python `unittest` 与 bundled Playwright smoke，不引入运行时依赖。

**Tech Stack:** Python 3.12、原生 HTML/CSS/JavaScript、Playwright 1.62.1、Python `unittest`。

## Global Constraints

- 保持 544 条岗位、825 人、16 市和 106/31 张源表不变。
- 成品继续是可双击打开、无需服务器、无需联网的单文件 HTML。
- 不生成岗位推荐、录取概率、竞争等级、城市综合评分或未经源数据支持的趋势结论。
- 对比篮最多 4 条，持久化键使用 `wanyu.jobCompare.v1`，恢复时过滤不存在的记录。
- CSV 使用 UTF-8 BOM、双引号转义和公式注入防护。

### Task 1: 建立升级回归测试

**Files:**
- Modify: `tests/browser_smoke_v2.js`
- Modify: `tests/test_anhui_web.py`

- [x] **Step 1: 增加移动导航、非法深链、对比篮和键盘行为断言**

新增断言覆盖 `390×844` 导航链接不出现逐字竖排、岗位页非法 `metric` 回退、待遇页非法 `type/stage` 回退、岗位对比篮刷新恢复、`/` 聚焦和 `Esc` 清空。

- [x] **Step 2: 增加 CSV 公式注入和固定字段顺序测试**

在 Python 测试中调用导出辅助函数，验证 `=SUM(1,1)`、`+1`、`-1`、`@cmd` 均以前导单引号导出，普通字段仍正确转义。

- [x] **Step 3: 使用 bundled Playwright 和 Python 运行新增测试确认红灯**

只运行新增测试，确认失败原因是缺少目标行为而不是测试语法错误。

### Task 2: 修复公共移动导航和产品参数容错

**Files:**
- Modify: `tools/anhui_web/templates/product-shell.css`
- Modify: `tools/anhui_web/templates/product-jobs.js`
- Modify: `tools/anhui_web/templates/product-salary.js`
- Modify: `tools/anhui_web/templates/product-jobs-ranking.js`
- Modify: `tools/anhui_web/templates/product-salary-ranking.js`

- [x] **Step 1: 让移动导航项保持单行并可横向滚动**

在 `720px` 规则中为导航容器和链接设置 `min-width: 0`、`flex: 0 0 auto`、`white-space: nowrap`，不改变桌面布局。

- [x] **Step 2: 为岗位和待遇脚本增加白名单解析**

岗位 `metric` 只接受 `jobs/recruits/ratio`，`exam` 只接受已有考试类别或 `全部`，`city` 只接受数据中的城市；待遇 `type/stage/city` 只接受数据中的值，无效值回退到当前页面默认值。

- [x] **Step 3: 运行参数与布局回归测试**

使用 bundled Playwright 跑 v2 smoke，确认所有正式页面无控制台错误、无页面级横向溢出且非法深链不崩溃。

### Task 3: 完善岗位检索对比篮和键盘/播报反馈

**Files:**
- Modify: `tools/anhui_web/templates/product-jobs-search.js`
- Modify: `tools/anhui_web/templates/product-shell.css`
- Modify: `tools/anhui_web/build_pages.py`

- [x] **Step 1: 增加版本化 localStorage 恢复**

保存 `record_id` 数组到 `wanyu.jobCompare.v1`，加载时只保留 `recordById` 中存在的 ID，超过 4 条截断并重新渲染。

- [x] **Step 2: 增加快捷键和明确反馈**

页面级 `/` 聚焦关键词框且不干扰输入控件；`Esc` 清空关键词并保留城市/考试筛选；结果数量和对比篮状态写入 `aria-live` 节点；复制摘要显示成功/失败状态。

- [x] **Step 3: 用生成器输出安全的对比数据属性和空状态**

为按钮补充 `aria-label`，为空结果显示可读提示，不修改源单元格文字。

- [x] **Step 4: 运行岗位检索回归测试和全文保真测试**

确认 544 行仍存在、对比篮刷新恢复、最多 4 条约束有效，源段落和单元格完整性继续通过。

### Task 4: 安全导出与最终 QA

**Files:**
- Modify: `tools/anhui_web/build_pages.py`
- Modify: `tools/anhui_web/templates/product-jobs-search.js`
- Modify: `tests/test_anhui_web.py`
- Modify: `tests/browser_smoke_v2.js`
- Modify: `HANDOFF.md`
- Modify: `design-qa.md`

- [x] **Step 1: 提取并测试统一 CSV 单元格转义逻辑**

让 Python 构建输出和浏览器对比导出遵守同一字段顺序及公式防护规则。

- [x] **Step 2: 完整运行 Python、bundled Playwright 和静态离线检查**

运行 `test.ps1`、两个浏览器 smoke、远程资源扫描和关键数据计数检查。

- [x] **Step 3: 更新 QA/交接记录**

记录实际通过数量、浏览器运行时路径、移动导航和深链容错结果；不写未经验证的结论。
