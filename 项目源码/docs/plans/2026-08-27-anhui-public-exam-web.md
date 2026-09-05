# 皖域择岗档案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将两份安徽公考 Word 数据文档转换成内容完整、可离线打开、具有安徽航图与薪资热力图的精美双网页。

**Architecture:** Python 构建器按 WordprocessingML 正文顺序解析段落与表格，生成中立的数据模型，再注入两套专用 HTML 模板。最终 HTML 内嵌 CSS、JavaScript、SVG 与数据，不依赖网络；测试同时核对 Word 原文、生成 DOM 和浏览器运行状态。

**Tech Stack:** Python 3、python-docx、lxml、HTML/CSS/原生 JavaScript、内嵌 SVG、Node.js Playwright、Python unittest

## Global Constraints

- 完整保留源文档事实、标题、段落、表格、合并单元格、星号、破折号、置信等级、来源及风险说明。
- 不新增文档未给出的岗位、待遇、排名、结论、推荐标签或政策判断。
- 两个最终 HTML 必须可直接双击打开，不依赖服务器、CDN、外部字体或外部脚本。
- 地图固定为明确标注的“城市导航示意”，不表达精确地理边界。
- 待遇图形只读取源表数据，不插值、不预测、不把估算值包装为官方工资。
- 输出目录固定为 `安徽公考数据网页`。
- 当前工作区不是 Git 仓库，计划中的每个“检查点”以测试结果和文件清单代替 commit，不虚构提交记录。

## File Structure

- Create: `tools/anhui_web/build_pages.py` — Word XML 解析、内容模型、数据提取和最终构建入口
- Create: `tools/anhui_web/templates/common.css` — 双页共享令牌、排版、导航、表格、无障碍和打印样式
- Create: `tools/anhui_web/templates/jobs.html` — 岗位页语义骨架
- Create: `tools/anhui_web/templates/jobs.css` — 岗位页航图、筛选器、城市档案样式
- Create: `tools/anhui_web/templates/jobs.js` — 搜索、筛选、折叠、地图联动
- Create: `tools/anhui_web/templates/salary.html` — 待遇页语义骨架
- Create: `tools/anhui_web/templates/salary.css` — 等高线、热力图和研究档案样式
- Create: `tools/anhui_web/templates/salary.js` — 身份/工龄切换、热力着色、城市定位
- Create: `tests/test_anhui_web.py` — 解析、完整性、离线性和生成结果测试
- Create: `安徽公考数据网页/安徽十六市2026软件工程可报岗位.html` — 岗位页最终交付物
- Create: `安徽公考数据网页/安徽全省16市本科普通岗全包分析.html` — 待遇页最终交付物
- Create: `安徽公考数据网页/制作说明.md` — 打开方式、页面功能和口径提示

---

### Task 1: Word 顺序解析与完整性模型

**Files:**
- Create: `tools/anhui_web/build_pages.py`
- Create: `tests/test_anhui_web.py`

**Interfaces:**
- Consumes: 两个固定 Word 路径和 WordprocessingML 元素
- Produces: `parse_docx(path: Path) -> DocumentModel`、`render_blocks(blocks: list[Block], page_kind: str) -> str`

- [ ] **Step 1: 写解析失败测试**

```python
class ParseDocxTests(unittest.TestCase):
    def test_source_counts_and_text(self):
        jobs = parse_docx(JOBS_DOCX)
        salary = parse_docx(SALARY_DOCX)
        self.assertEqual(jobs.paragraph_node_count, 156)
        self.assertEqual(len(jobs.tables), 106)
        self.assertEqual(salary.paragraph_node_count, 228)
        self.assertEqual(len(salary.tables), 31)
        self.assertIn("软件工程专业可报岗位汇总", jobs.all_text)
        self.assertIn("公务员 / 事业编年度全包分析报告", salary.all_text)

    def test_table_merge_metadata(self):
        jobs = parse_docx(JOBS_DOCX)
        html = render_blocks(jobs.blocks, "jobs")
        self.assertIn("<table", html)
        self.assertEqual(html.count("data-source-table="), 106)
        self.assertNotIn("None", html)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.test_anhui_web.ParseDocxTests -v`  
Expected: FAIL，因为 `tools.anhui_web.build_pages` 尚不存在。

- [ ] **Step 3: 实现最小数据模型与解析器**

在 `build_pages.py` 定义：

```python
@dataclass
class CellModel:
    text: str
    colspan: int = 1
    rowspan: int = 1
    header: bool = False

@dataclass
class TableModel:
    index: int
    rows: list[list[CellModel]]

@dataclass
class Block:
    kind: str
    text: str = ""
    style: str = ""
    table: TableModel | None = None

@dataclass
class DocumentModel:
    blocks: list[Block]
    tables: list[TableModel]
    paragraph_node_count: int
    all_text: str
```

解析规则：遍历 `document.element.body.iterchildren()`；`w:p` 读取所有 `w:t`、`w:tab`、`w:br`，包括超链接内部文字；`w:tbl` 逐行读取 `w:gridSpan` 与 `w:vMerge` 并计算 `colspan/rowspan`。空段落保留为 `Block(kind="paragraph", text="")`，渲染时只保留必要间隔。

- [ ] **Step 4: 实现安全 HTML 渲染**

`render_blocks()` 对所有原文调用 `html.escape()`；段落样式映射为 `h2/h3/h4/p/li`，表格写入 `data-source-table="N"`，表头使用 `th`，所有合并信息写入 `rowspan`/`colspan`。

- [ ] **Step 5: 运行解析测试**

Run: `python -m unittest tests.test_anhui_web.ParseDocxTests -v`  
Expected: PASS，段落节点数与表格数精确匹配。

- [ ] **Step 6: 检查点**

Run: `Get-Item tools/anhui_web/build_pages.py,tests/test_anhui_web.py | Select-Object FullName,Length`  
Expected: 两个文件存在且非空。

### Task 2: 共享视觉系统与模板装配

**Files:**
- Create: `tools/anhui_web/templates/common.css`
- Create: `tools/anhui_web/templates/jobs.html`
- Create: `tools/anhui_web/templates/salary.html`
- Modify: `tools/anhui_web/build_pages.py`
- Modify: `tests/test_anhui_web.py`

**Interfaces:**
- Consumes: `DocumentModel`、模板文件和页面专用 CSS/JS 字符串
- Produces: `assemble_page(template_name: str, context: dict[str, str]) -> str`

- [ ] **Step 1: 写装配失败测试**

```python
def test_assembled_pages_are_offline_and_semantic(self):
    build_all(OUTPUT_DIR)
    for page in (JOBS_HTML, SALARY_HTML):
        text = page.read_text(encoding="utf-8")
        self.assertIn("<!doctype html>", text.lower())
        self.assertIn("<main", text)
        self.assertIn("prefers-reduced-motion", text)
        self.assertIn("@media print", text)
        self.assertNotRegex(text, r'https?://[^\"\']+\.(?:js|css|woff2?)')
        self.assertNotIn("{{", text)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.test_anhui_web.GeneratedPageTests.test_assembled_pages_are_offline_and_semantic -v`  
Expected: FAIL，因为模板和 `build_all()` 尚不存在。

- [ ] **Step 3: 创建共享 CSS**

实现设计规格中的六个颜色令牌、三类字体栈、阅读进度、吸顶导航、表格滚动容器、焦点样式、空状态、打印模式、390px 响应式和减少动画模式。公共选择器使用 `.site-header`、`.section-nav`、`.data-table`、`.source-note`、`.floating-tools`，避免和页面专用选择器互相覆盖。

- [ ] **Step 4: 创建两个语义模板**

模板固定包含：`lang="zh-CN"`、`meta viewport`、跳转到正文的链接、`header/nav/main/footer`、`noscript`、互链和三个内嵌槽位：

```html
<style>{{COMMON_CSS}}\n{{PAGE_CSS}}</style>
<main id="main-content">{{PAGE_CONTENT}}</main>
<script type="application/json" id="page-data">{{PAGE_DATA}}</script>
<script>{{PAGE_JS}}</script>
```

- [ ] **Step 5: 实现装配器与写入入口**

`assemble_page()` 只替换已定义槽位；`build_all(output_dir)` 创建目录并以 UTF-8 写入两个最终 HTML。构建使用模板文件，不通过字符串拼接改变原文。

- [ ] **Step 6: 运行装配测试**

Run: `python -m unittest tests.test_anhui_web.GeneratedPageTests.test_assembled_pages_are_offline_and_semantic -v`  
Expected: PASS。

### Task 3: 岗位页城市航图与岗位检索

**Files:**
- Create: `tools/anhui_web/templates/jobs.css`
- Create: `tools/anhui_web/templates/jobs.js`
- Modify: `tools/anhui_web/build_pages.py`
- Modify: `tests/test_anhui_web.py`

**Interfaces:**
- Consumes: `DocumentModel.blocks` 和 16 城市摘要表
- Produces: `build_jobs_context(model: DocumentModel) -> dict[str, str]` 与最终岗位 HTML

- [ ] **Step 1: 写岗位页失败测试**

```python
def test_jobs_page_preserves_content_and_features(self):
    build_all(OUTPUT_DIR)
    text = JOBS_HTML.read_text(encoding="utf-8")
    self.assertEqual(text.count("data-source-table="), 106)
    for city in ("合肥", "滁州", "马鞍山", "黄山"):
        self.assertIn(f'data-city="{city}"', text)
    self.assertIn('id="job-search"', text)
    self.assertIn('id="city-map"', text)
    self.assertIn("城市导航示意", text)
    self.assertIn("544岗 / 825人", text)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.test_anhui_web.GeneratedPageTests.test_jobs_page_preserves_content_and_features -v`  
Expected: FAIL，岗位专用内容尚未生成。

- [ ] **Step 3: 构建岗位页上下文**

从总览表读取 16 市的岗位数与招录数；使用固定城市节点坐标生成内嵌 SVG：

```python
CITY_POSITIONS = {
 "亳州": (31, 14), "淮北": (55, 10), "宿州": (67, 16), "阜阳": (24, 28),
 "蚌埠": (58, 31), "淮南": (43, 34), "滁州": (73, 38), "六安": (29, 46),
 "合肥": (49, 48), "马鞍山": (72, 55), "芜湖": (68, 61), "铜陵": (55, 65),
 "安庆": (35, 68), "池州": (48, 73), "宣城": (69, 73), "黄山": (54, 88),
}
```

每个节点的 `aria-label` 包含城市、岗位数和招录人数；图形下方明确写“城市导航示意，节点位置仅用于快速定位”。

- [ ] **Step 4: 实现岗位页面 UI**

首屏采用不对称双栏：左侧标题和总量，右侧抽象皖形坐标板；下方建立十六市“档案抽屉”矩阵。逐市章节使用城市侧标、汇总台和完整分类表；视觉只强调一处主签名，不给每张表添加装饰卡片。

- [ ] **Step 5: 实现搜索和筛选**

`jobs.js` 解析 `#job-search`、`#city-filter`、`#exam-filter`；为每个 `.job-group` 使用 `dataset.search`、`dataset.city`、`dataset.exam`。输入事件经 80ms 防抖后更新可见分组、命中数和空状态；清除按钮重置三个条件。地图和城市矩阵点击后清除不相容城市筛选并滚动至目标章节。

- [ ] **Step 6: 运行岗位页测试**

Run: `python -m unittest tests.test_anhui_web.GeneratedPageTests.test_jobs_page_preserves_content_and_features -v`  
Expected: PASS。

### Task 4: 待遇页等高线与薪资热力图

**Files:**
- Create: `tools/anhui_web/templates/salary.css`
- Create: `tools/anhui_web/templates/salary.js`
- Modify: `tools/anhui_web/build_pages.py`
- Modify: `tests/test_anhui_web.py`

**Interfaces:**
- Consumes: 源表 3 和源表 4 的 16 市五工龄节点数据、逐城正文与表格
- Produces: `extract_salary_series(model: DocumentModel) -> dict`、`build_salary_context(model: DocumentModel) -> dict[str, str]`

- [ ] **Step 1: 写待遇页失败测试**

```python
def test_salary_page_preserves_content_and_features(self):
    build_all(OUTPUT_DIR)
    text = SALARY_HTML.read_text(encoding="utf-8")
    self.assertEqual(text.count("data-source-table="), 31)
    self.assertIn('id="salary-map"', text)
    self.assertIn('id="career-stage"', text)
    self.assertIn('id="employment-type"', text)
    self.assertIn("城市级导航热力示意", text)
    self.assertIn("9.1-16.3万元", text)
    data = extract_salary_series(parse_docx(SALARY_DOCX))
    self.assertEqual(data["公务员"]["合肥"]["3年"], 16.3)
    self.assertEqual(data["事业编"]["亳州"]["3年"], 8.0)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest tests.test_anhui_web.GeneratedPageTests.test_salary_page_preserves_content_and_features -v`  
Expected: FAIL，待遇数据接口与 UI 尚未实现。

- [ ] **Step 3: 提取待遇序列**

严格读取两张 17×8 市直表的列名 `刚入职/1年/3年/5年/10年`；数值无法解析时保留 `None`。生成 JSON 时使用 `ensure_ascii=False` 并将 `<` 转义为 `\u003c`，避免脚本标签注入。

- [ ] **Step 4: 构建热力图与等高线 UI**

复用岗位页同一城市坐标，填充抽象皖形热力节点；颜色使用固定的 7 档皖江蓝至朱砂色阶，并显示当前最小/最大值。等高线区域为 16 条可横向浏览的城市轨迹，五个节点均来自源表；默认 `公务员 + 3年`。

- [ ] **Step 5: 实现交互联动**

`salary.js` 读取 `#page-data`；`employment-type` 和 `career-stage` 变化时统一调用 `renderSalaryView(type, stage)`，更新地图颜色、节点文本、排行刻度和图例。城市节点点击滚动至对应 `.city-dossier`，不生成新的排名结论文本。

- [ ] **Step 6: 运行待遇页测试**

Run: `python -m unittest tests.test_anhui_web.GeneratedPageTests.test_salary_page_preserves_content_and_features -v`  
Expected: PASS。

### Task 5: 全量内容核对、浏览器验收与说明文件

**Files:**
- Modify: `tests/test_anhui_web.py`
- Create: `安徽公考数据网页/制作说明.md`
- Regenerate: 两个最终 HTML

**Interfaces:**
- Consumes: 两个最终 HTML、两个源 Word、Playwright 浏览器
- Produces: 全量测试结果、桌面/移动截图、最终交付说明

- [ ] **Step 1: 写全量文本核对测试**

```python
def test_every_nonempty_source_text_appears(self):
    pairs = [(JOBS_DOCX, JOBS_HTML), (SALARY_DOCX, SALARY_HTML)]
    for docx_path, html_path in pairs:
        model = parse_docx(docx_path)
        visible = html.unescape(re.sub(r"<[^>]+>", " ", html_path.read_text(encoding="utf-8")))
        normalized = normalize_text(visible)
        for block in model.blocks:
            if block.kind == "paragraph" and normalize_text(block.text):
                self.assertIn(normalize_text(block.text), normalized)
            if block.table:
                for row in block.table.rows:
                    for cell in row:
                        if normalize_text(cell.text):
                            self.assertIn(normalize_text(cell.text), normalized)
```

- [ ] **Step 2: 运行完整 Python 测试**

Run: `python -m unittest tests.test_anhui_web -v`  
Expected: 全部 PASS，且没有缺失原文或表格。

- [ ] **Step 3: 构建最终文件**

Run: `python tools/anhui_web/build_pages.py`  
Expected: 输出目录包含两个 HTML，表格标记分别为 106 和 31。

- [ ] **Step 4: Playwright 桌面与移动验收**

打开两个 `file:///` 页面，桌面使用 1440×900，移动使用 390×844。对每页执行：

```javascript
const errors = [];
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', e => errors.push(e.message));
await page.goto(fileUrl, { waitUntil: 'load' });
await page.screenshot({ path: output, fullPage: true });
expect(errors).toEqual([]);
```

同时操作岗位搜索/清除和待遇身份/工龄切换，确认状态变化、正文仍在、页面未出现整体水平溢出。

- [ ] **Step 5: 可访问性与降级检查**

检查所有按钮可通过 Tab 聚焦；`aria-label` 存在；模拟 `prefers-reduced-motion: reduce` 后无主位移动画；禁用 JavaScript 后正文和 137 张源表仍可阅读。

- [ ] **Step 6: 写制作说明**

说明两个 HTML 的用途、直接打开方式、交互功能、地图为导航示意、待遇为估算口径以及源 Word 文件名。不得增加岗位或待遇建议。

- [ ] **Step 7: 最终检查点**

Run: `Get-ChildItem -LiteralPath '安徽公考数据网页' | Select-Object Name,Length,LastWriteTime`  
Expected: 两个非空 HTML 和一份 `制作说明.md`；报告实际测试与截图结果，不声称未执行的验证。
