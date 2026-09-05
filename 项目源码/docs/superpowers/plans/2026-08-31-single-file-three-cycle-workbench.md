# 皖域择岗三年单文件工作台实施计划

> **For Codex:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. 每个任务必须先运行失败测试，再做最小实现，再运行通过测试；未经对应验收，不得跳到发布。

**目标：** 将 2024、2025、2026 三个招录周期完整整合进唯一离线入口 `deliverables/皖域择岗总览.html`，完成 UI、功能、数据架构和真实性复核升级，并交付可独立验收的 v12.0 压缩包。

**架构：** 构建期用纯函数装载三个 `CycleBundle`，写入一个 HTML 的三个独立 JSON 载荷；浏览器端由 `WanyuCycleStore` 统一管理激活周期、URL 和订阅更新，所有数据视图根据周期事件幂等重绘。真实性审计贯穿源数据、构建对象、HTML 载荷、浏览器 DOM 和最终 ZIP 五个物理层级，并在构建前、构建后、打包后三次执行。

**技术栈：** Python 3、标准库 `unittest`、现有 `tools/anhui_web` 构建脚本、原生 HTML/CSS/JavaScript、Node.js、Playwright、PowerShell、离线 `file://` 运行模式。

---

## 一、执行总则

### 1. 不可变约束

- 正式用户入口只能有一个：`deliverables/皖域择岗总览.html`。
- 三个周期必须在同一个 HTML 内切换，不使用 iframe，不跳转到 2024/2025 子目录网页。
- 不引入网络依赖、CDN、远程字体、分析脚本或在线 API。
- 不猜测、不补造、不把空值改成 0；歧义关联继续留空并说明原因。
- 待遇数据只能标注为“2026 快照”，不能随年份切换冒充 2024/2025 历史待遇。
- 三年数据的岗位记录、成绩记录、来源说明和已知缺口必须全部被打包；“完整”指结构和已收集材料完整，不得扩大表述为所有官方原文都已经获得。
- 当前目录不是 Git 仓库。计划中的阶段检查点使用测试报告、文件哈希和可恢复备份，不伪造提交记录。
- 所有旧交付物先保留；只有 v12 全量验收通过后，才将旧独立网页移动到 `deliverables/legacy_v11/`。

### 2. 冻结数据基线

| 周期 | 岗位数 | 招录人数 | 省考 | 事业编 | 国考 | 成绩关联 | 未消歧 |
| --- | ---: | ---: | --- | --- | --- | ---: | ---: |
| 2024 | 10,017 | 15,331 | 4,243 岗 / 7,235 人 | 5,215 岗 / 6,911 人 | 559 岗 / 1,185 人 | 4,087 | 0 |
| 2025 | 10,150 | 14,721 | 4,116 岗 / 6,620 人 | 5,491 岗 / 6,956 人 | 543 岗 / 1,145 人 | 4,107 | 0 |
| 2026 | 8,511 | 12,006 | 3,784 岗 / 5,791 人 | 4,176 岗 / 5,065 人 | 551 岗 / 1,150 人 | 6,521 | 116 |

2026 还必须保留：来源组件 8,457 岗 / 11,951 人，页面调整 54 岗 / 55 人。

### 3. 已知缺口白名单

白名单只允许“如实存在”，不允许静默消失或数量变化。当前审计快照逐项为：

- 2024：省考合格/缴费官方无逐岗表；
- 2024：拟聘用市级批次约 30+ 批未回收；
- 2024：133 个定向岗主表行由镜像/分数线源合成，备注已经标注；
- 2024：事业编下半年官方原始 XLSX 未逐单位回收；
- 2024：候选复合键存在 1 个重复键、涉及 2 行；不自动去重，必须以完整记录主键区分；
- 2025：省考合格/缴费官方无逐岗表；
- 2025：事业编逐岗报名人数官方未发布，仅有考区汇总；
- 2025：事业编上半年单位名称列待修复；
- 2025：拟聘用材料覆盖 13 市和省直，仍缺 4 市；
- 2026：事业编页面比当前组件源包增加 54 岗/55 人，属于已说明的来源包差异；
- 2026：东至县下半年 30 岗成绩公告未发布，省直除粮食局 8 岗外的 564 岗实证不可得；
- 2026：岗位 `0801048` 待官方复核；
- 2026：`300110013003`、`300147355001`、`300147357001` 三条国考备注待官方复核；
- 2026：116 条成绩关联存在歧义并安全留空。

### 4. 目标性能与质量门槛

- 单一 HTML 目标不超过 75 MiB，硬上限 80 MiB；
- 当前验收机器 `file://` 首次可交互目标不超过 8 秒，硬上限 12 秒；
- 首次激活尚未解析的年份目标不超过 1 秒，硬上限 2 秒；
- 激活后的常用筛选目标不超过 150ms，硬上限 300ms；
- 浏览器冒烟必须覆盖三个年份、九个主视图、URL 恢复、收藏迁移和 ZIP 解包入口；
- 所有最终断言必须来自刚执行的命令输出，不能沿用旧报告结论。

## 二、文件变更总图

### 新建文件

- `tools/anhui_web/unified_cycle_bundle.py`
- `tools/anhui_web/verify_single_file_v12.py`
- `tools/anhui_web/templates/cycle-runtime.js`
- `tools/anhui_web/templates/cycle-unified.css`
- `tests/test_single_file_cycle_workbench.py`
- `tests/browser_smoke_v12.js`
- `tools/anhui_web/data/single_file_baseline_v12.json`
- `tools/anhui_web/data/single_file_verification_v12.json`（脚本生成）
- `tools/anhui_web/data/single_file_diff_v12.json`（脚本生成）
- `docs/三年单文件数据复核报告_v12.md`（脚本生成）
- `deliverables/HANDOFF.md`
- `deliverables/MANIFEST.txt`

### 主要修改文件

- `tools/anhui_web/build_pages.py`
- `tools/anhui_web/audit_three_years.py`
- `tools/anhui_web/release.py`
- `tools/anhui_web/templates/master.js`
- `tools/anhui_web/templates/master.css`
- `tools/anhui_web/templates/product-shell.js`
- `tools/anhui_web/templates/product-all.js`
- `tools/anhui_web/templates/product-jobs-search.js`
- `tools/anhui_web/templates/product-jobs-detail.js`
- `tools/anhui_web/templates/product-jobs-ranking.js`
- `tools/anhui_web/templates/product-score-sim.js`
- `build.ps1`
- `test.ps1`
- `tests/test_anhui_web.py`
- `tests/test_three_year_audit.py`
- `tests/browser_smoke_v11.js`

### 只读输入，不应被重写

- 2024、2025、2026 的周期源 JSON；
- `tools/anhui_web/data/three_year_audit.json`；
- 2026 来源 Word 归档；
- 2024、2025 现有证据表和缺口登记；
- 当前 v11 HTML，直到最终验收完成。

## 三、分阶段实施

### Task 1：冻结输入盘点、基线和可恢复状态

**目的：** 在任何构建逻辑变化前，记录输入文件、现有交付物和三年统计基线，避免升级过程中无法判断是数据变化还是代码变化。

**Files:**

- Create: `tools/anhui_web/data/single_file_baseline_v12.json`
- Create: `tests/test_single_file_cycle_workbench.py`
- Modify: `tools/anhui_web/audit_three_years.py`
- Read: `tools/anhui_web/data/three_year_audit.json`
- Read: `deliverables/皖域择岗总览.html`
- Read: `deliverables/2024/皖域择岗总览.html`
- Read: `deliverables/2025/皖域择岗总览.html`

- [ ] **Step 1.1：建立基线 JSON 的精确结构**

`single_file_baseline_v12.json` 固定使用以下顶层字段：

```json
{
  "schema_version": "1.0",
  "release": "v12.0",
  "cycles": {
    "2024": {},
    "2025": {},
    "2026": {}
  },
  "known_gaps": [],
  "input_files": []
}
```

每个周期必须含 `posts`、`recruits`、`exam_types`、`score_joined`、`score_unresolved`；`input_files` 必须含相对路径、字节数、SHA-256，不存绝对用户目录。

- [ ] **Step 1.2：先写失败测试**

在 `tests/test_single_file_cycle_workbench.py` 新建 `TestFrozenBaseline`：

```python
class TestFrozenBaseline(unittest.TestCase):
    def test_frozen_totals_match_approved_values(self):
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(baseline["cycles"]["2024"]["posts"], 10017)
        self.assertEqual(baseline["cycles"]["2024"]["recruits"], 15331)
        self.assertEqual(baseline["cycles"]["2025"]["posts"], 10150)
        self.assertEqual(baseline["cycles"]["2025"]["recruits"], 14721)
        self.assertEqual(baseline["cycles"]["2026"]["posts"], 8511)
        self.assertEqual(baseline["cycles"]["2026"]["recruits"], 12006)

    def test_2026_adjustment_is_explicit(self):
        cycle = self.baseline["cycles"]["2026"]
        self.assertEqual(cycle["source_components"], {"posts": 8457, "recruits": 11951})
        self.assertEqual(cycle["documented_adjustment"], {"posts": 54, "recruits": 55})
```

- [ ] **Step 1.3：运行并确认失败原因正确**

```powershell
python -m unittest tests.test_single_file_cycle_workbench.TestFrozenBaseline -v
```

期望：因基线文件不存在或字段未写入而失败；不能因模块导入错误、编码错误等无关原因失败。

- [ ] **Step 1.4：填入冻结值和文件哈希**

从当前源文件重新计算哈希和统计值。若实时统计不等于冻结值，停止任务，先生成差异清单；不得为了让测试通过直接修改冻结值。

- [ ] **Step 1.5：扩展审计输出**

让 `audit_three_years.py` 在保持原有报告兼容的前提下增加：

```python
def collect_input_inventory(root: Path) -> list[dict[str, object]]: ...
def compare_with_frozen_baseline(
    audit: dict[str, object],
    baseline: dict[str, object],
) -> list[dict[str, object]]: ...
```

差异对象固定包含 `path`、`expected`、`actual`、`severity`、`allowed_gap_id`。

- [ ] **Step 1.6：运行基线测试和原审计测试**

```powershell
python -m unittest tests.test_single_file_cycle_workbench.TestFrozenBaseline tests.test_three_year_audit -v
```

期望：全部通过；原有 `test_three_year_audit.py` 不回归。

- [ ] **Step 1.7：保存阶段证据**

记录基线文件自身 SHA-256、测试数量、通过数量和执行时间到 `docs/三年单文件数据复核报告_v12.md` 的“构建前基线”节。此时报告可以标注为“进行中”，不能标注“交付完成”。

### Task 2：实现无全局串扰的三周期构建对象

**目的：** 解除 `_apply_cycle_paths(cycle)` 的全局路径副作用，让同一进程一次性安全装载三年数据。

**Files:**

- Create: `tools/anhui_web/unified_cycle_bundle.py`
- Modify: `tools/anhui_web/build_pages.py`
- Test: `tests/test_single_file_cycle_workbench.py`

- [ ] **Step 2.1：先写数据类和装载接口测试**

增加 `TestCycleBundleLoader`，精确断言：

```python
class TestCycleBundleLoader(unittest.TestCase):
    def test_loads_all_cycles_without_global_path_mutation(self):
        original_paths = snapshot_build_page_paths()
        bundles = build_unified_bundles(PROJECT_ROOT)
        self.assertEqual(tuple(bundles), ("2024", "2025", "2026"))
        self.assertEqual(snapshot_build_page_paths(), original_paths)

    def test_bundle_counts_match_frozen_baseline(self):
        bundles = build_unified_bundles(PROJECT_ROOT)
        for cycle, expected in FROZEN["cycles"].items():
            self.assertEqual(len(bundles[cycle].records), expected["posts"])
            self.assertEqual(
                sum(int(row["recruit_count"]) for row in bundles[cycle].records),
                expected["recruits"],
            )

    def test_global_record_id_is_cycle_scoped(self):
        self.assertEqual(global_record_id("2025", "001"), "2025:001")
```

- [ ] **Step 2.2：运行测试并确认接口尚不存在**

```powershell
python -m unittest tests.test_single_file_cycle_workbench.TestCycleBundleLoader -v
```

期望：`unified_cycle_bundle` 或指定符号不存在，测试失败。

- [ ] **Step 2.3：实现 `CycleBundle`**

在 `unified_cycle_bundle.py` 实现：

```python
@dataclass(frozen=True)
class CycleBundle:
    cycle: str
    label: str
    all_majors: dict[str, object]
    jobs: dict[str, object]
    records: list[dict[str, object]]
    score_lists: dict[str, object]
    cycle_info: dict[str, object]
    audit: dict[str, object]
```

约束：

- 路径都由 `root` 和 `cycle` 局部推导；
- 不修改 `build_pages.py` 的模块全局变量；
- 文件缺失时抛出包含相对路径和周期的 `CycleBundleError`；
- 记录中缺少周期时在构建对象中补 `cycle`，但不回写源 JSON；
- 不改变记录排序；
- 不把 `None`、空字符串和 0 互相转换。

- [ ] **Step 2.4：实现三年批量装载与唯一 ID**

```python
def load_cycle_bundle(root: Path, cycle: str) -> CycleBundle: ...
def build_unified_bundles(root: Path, cycles=("2024", "2025", "2026")) -> dict[str, CycleBundle]: ...
def global_record_id(cycle: str, record_id: str) -> str: ...
```

`global_record_id` 对空周期、含冒号记录 ID、非四位数字周期抛 `ValueError`，避免产生不可逆键。

- [ ] **Step 2.5：增加抽样保真测试**

每个周期至少抽取首条、中间条、末条和固定业务主键，逐字段对比源 JSON 与 bundle；重点检查岗位代码、招录人数、城市、考试类别、学历、专业、成绩字段和来源状态。

- [ ] **Step 2.6：运行聚焦测试**

```powershell
python -m unittest tests.test_single_file_cycle_workbench.TestCycleBundleLoader -v
```

期望：全部通过，且连续装载顺序 `2024→2025→2026` 与 `2026→2024→2025` 的哈希相同。

- [ ] **Step 2.7：运行现有构建测试**

```powershell
python -m unittest tests.test_anhui_web -v
```

期望：现有 55 项测试全部通过。若历史测试数量变化，报告实际数量和新增原因，不能沿用“55”作为口头结论。

### Task 3：把三个周期安全嵌入唯一 HTML

**目的：** 生成一个界面骨架、三份周期数据载荷，杜绝复制三整套页面造成的体积和维护问题。

**Files:**

- Modify: `tools/anhui_web/build_pages.py`
- Modify: `tools/anhui_web/templates/master.js`
- Test: `tests/test_single_file_cycle_workbench.py`

- [ ] **Step 3.1：先写 HTML 结构失败测试**

增加 `TestUnifiedHtmlBuild`：

```python
class TestUnifiedHtmlBuild(unittest.TestCase):
    def test_has_one_shell_and_three_cycle_payloads(self):
        html = build_master_html_for_test()
        self.assertEqual(html.count('id="app-shell"'), 1)
        for cycle in ("2024", "2025", "2026"):
            self.assertEqual(html.count(f'data-cycle-payload="{cycle}"'), 1)

    def test_payloads_round_trip(self):
        html = build_master_html_for_test()
        payloads = extract_cycle_payloads(html)
        self.assertEqual(tuple(payloads), ("2024", "2025", "2026"))
        self.assertEqual(len(payloads["2024"]["records"]), 10017)
        self.assertEqual(len(payloads["2025"]["records"]), 10150)
        self.assertEqual(len(payloads["2026"]["records"]), 8511)

    def test_data_cannot_terminate_script_block(self):
        encoded = encode_json_script_payload({"x": "</script><script>alert(1)</script>"})
        self.assertNotIn("</script>", encoded.lower())
```

- [ ] **Step 3.2：运行测试并确认缺少统一载荷**

```powershell
python -m unittest tests.test_single_file_cycle_workbench.TestUnifiedHtmlBuild -v
```

期望：现有页面只有当前周期载荷，断言失败。

- [ ] **Step 3.3：实现安全序列化函数**

在 `build_pages.py` 新增：

```python
def encode_json_script_payload(value: object) -> str: ...
def render_cycle_payload_scripts(bundles: Mapping[str, CycleBundle]) -> str: ...
def extract_embedded_payload_for_test(html: str, cycle: str) -> dict[str, object]: ...
```

序列化固定使用 UTF-8、紧凑分隔符和确定性键顺序；必须转义 `<`、`>`、`&`、U+2028、U+2029。

- [ ] **Step 3.4：重构 `_build_master_site` 输入**

目标签名：

```python
def _build_master_site(
    bundles: Mapping[str, CycleBundle],
    salary: dict[str, object],
    default_cycle: str = "2026",
) -> str: ...
```

页面元数据增加：

```json
{
  "release": "v12.0",
  "default_cycle": "2026",
  "available_cycles": ["2024", "2025", "2026"],
  "salary_snapshot_cycle": "2026"
}
```

- [ ] **Step 3.5：调整 `build_all()`**

正式构建默认只写一个主 HTML。兼容页面生成改成显式参数 `include_legacy=True`，且写入 `legacy_v11/`，不能继续污染正式入口目录。

- [ ] **Step 3.6：运行构建并检查体积**

```powershell
python tools/anhui_web/build_pages.py
Get-Item 'deliverables\皖域择岗总览.html' | Select-Object FullName,Length,LastWriteTime
```

期望：文件存在、三载荷可反解析、大小不超过 80 MiB。超过 75 MiB 时记录为性能警告，超过 80 MiB 立即失败。

- [ ] **Step 3.7：运行统一 HTML 测试与原页面测试**

```powershell
python -m unittest tests.test_single_file_cycle_workbench.TestUnifiedHtmlBuild tests.test_anhui_web -v
```

### Task 4：实现周期状态源、URL 恢复和惰性解析

**目的：** 建立唯一运行时状态，不让各脚本各自缓存一份旧年份数据。

**Files:**

- Create: `tools/anhui_web/templates/cycle-runtime.js`
- Modify: `tools/anhui_web/templates/master.js`
- Modify: `tools/anhui_web/templates/product-shell.js`
- Create: `tests/browser_smoke_v12.js`

- [ ] **Step 4.1：先写浏览器失败测试**

`browser_smoke_v12.js` 首批用例：

```javascript
test('cycle store lists and activates all cycles', async ({ page }) => {
  await openLocalMaster(page);
  expect(await page.evaluate(() => window.WanyuCycleStore.listCycles()))
    .toEqual(['2024', '2025', '2026']);
  await page.getByRole('tab', { name: '2025' }).click();
  await expect(page.locator('[data-active-cycle]')).toHaveAttribute('data-active-cycle', '2025');
  await expect(page).toHaveURL(/cycle=2025/);
});

test('reload and history restore cycle', async ({ page }) => {
  await openLocalMaster(page, '?cycle=2024#jobs_search');
  await expect(page.getByRole('tab', { name: '2024' })).toHaveAttribute('aria-selected', 'true');
  await page.getByRole('tab', { name: '2026' }).click();
  await page.goBack();
  await expect(page.getByRole('tab', { name: '2024' })).toHaveAttribute('aria-selected', 'true');
});
```

- [ ] **Step 4.2：运行并确认 `WanyuCycleStore` 不存在**

```powershell
$runtimeNode='C:\Users\24218\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
$env:NODE_PATH='C:\Users\24218\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
& $runtimeNode tests/browser_smoke_v12.js --grep "cycle store|history restore"
```

期望：因周期控件或状态源不存在而失败。

- [ ] **Step 4.3：实现 `WanyuCycleStore`**

公开接口：

```javascript
window.WanyuCycleStore = Object.freeze({
  listCycles,
  getCycle,
  getBundle,
  activate,
  subscribe,
  toGlobalId,
});
```

内部要求：

- 启动只解析默认周期；
- 三年总览摘要可从独立轻量元数据读取；
- `getBundle(cycle)` 首次调用解析对应 `<script>`，随后缓存；
- 重复 `activate` 当前周期不得重复重绘；
- 非法周期回退到 2026，并在控制台给出一次结构化警告；
- `subscribe` 返回取消订阅函数；
- `activate` 更新 `history.pushState`，`popstate` 使用 `replaceState` 语义恢复，避免历史死循环；
- 发出 `CustomEvent('wanyu:cyclechange', { detail })`。

- [ ] **Step 4.4：实现周期控件语义**

HTML 必须使用 `role="tablist"`，每个年份按钮包含：

- `role="tab"`
- `aria-selected`
- `aria-controls="cycle-context"`
- `data-cycle="2024|2025|2026"`

支持左右方向键移动、Home/End 跳转和 Enter/Space 激活。

- [ ] **Step 4.5：实现 URL 解析和视图保留**

统一 URL 参数：

- `cycle`：当前周期；
- `metric`：总览指标；
- hash：当前主视图；
- `record`：可选的全局岗位 ID。

非法参数必须被清理，不得导致白屏。

- [ ] **Step 4.6：运行浏览器聚焦测试**

```powershell
& $runtimeNode tests/browser_smoke_v12.js --grep "cycle store|history restore|keyboard cycle"
```

期望：全部通过；页面控制台没有未处理异常。

### Task 5：升级 UI 外壳、导航和三年总览

**目的：** 建立统一、稳重、非模板化的视觉层级，让“当前年份、数据状态、主要任务”始终清晰。

**Files:**

- Create: `tools/anhui_web/templates/cycle-unified.css`
- Modify: `tools/anhui_web/templates/master.css`
- Modify: `tools/anhui_web/templates/master.js`
- Modify: `tools/anhui_web/build_pages.py`
- Test: `tests/browser_smoke_v12.js`

- [ ] **Step 5.1：先写 UI 结构和可见性失败测试**

测试以下固定元素：

- 唯一 H1；
- 主导航九个入口；
- 三年周期分段器；
- 周期上下文栏；
- 已知缺口入口；
- “待遇基准（2026 快照）”文本；
- 390×844、768×1024、1440×900 三种视口无页面级横向溢出。

- [ ] **Step 5.2：运行 UI 测试并保留失败截图**

```powershell
& $runtimeNode tests/browser_smoke_v12.js --grep "shell|responsive|salary snapshot"
```

截图输出到 `build/reports/v12/screenshots/failing/`，文件名包含视口和测试名。

- [ ] **Step 5.3：定义 CSS 令牌**

`cycle-unified.css` 至少定义：

```css
:root {
  --wy-canvas: #f6f3ec;
  --wy-surface: #fffdf8;
  --wy-ink: #152538;
  --wy-ink-muted: #5e6a73;
  --wy-navy: #183b5b;
  --wy-teal: #0f746f;
  --wy-amber: #a66a12;
  --wy-danger: #9b3b35;
  --wy-border: #d8d4ca;
  --wy-focus: #0a66c2;
  --wy-radius-sm: 6px;
  --wy-radius-md: 12px;
  --wy-space-1: 4px;
  --wy-space-2: 8px;
  --wy-space-3: 12px;
  --wy-space-4: 16px;
  --wy-space-6: 24px;
  --wy-space-8: 32px;
}
```

不增加外部字体；不使用连续大面积渐变或发光阴影。

- [ ] **Step 5.4：重构页面骨架**

顺序固定为：跳转链接 → 页头与周期选择器 → 主导航 → 周期上下文栏 → 主内容 → 详情层 → 页脚与版本信息。

- [ ] **Step 5.5：重做三年总览**

显示三年岗位数、招录人数、考试类别拆分、同比变化和来源状态。切换 `jobs/recruits` 指标时只改变图表和排序，不改冻结数字。

百分比规则：

```javascript
function safePercentChange(current, previous) {
  return previous === 0 ? null : (current - previous) / previous;
}
```

`null` 展示“基数为 0，不计算”，不能展示 `Infinity%`。

- [ ] **Step 5.6：补齐响应式和打印样式**

- 1180px：主卡片从 4 列降为 2 列；
- 840px：筛选面板进入折叠模式；
- 720px：导航横向滚动但保留焦点可见，表格切卡片摘要；
- 打印：隐藏按钮，显示周期、筛选条件、来源状态和生成时间。

- [ ] **Step 5.7：运行 UI 测试并人工看图复核**

生成通过截图到 `build/reports/v12/screenshots/passing/`，逐张检查文本截断、重叠、空白、色彩对比、窄屏可操作性。浏览器断言通过但截图明显异常时仍判失败。

### Task 6：把所有数据功能改造成可重绘模块

**目的：** 消除脚本启动时捕获 `window.productData` 的单年份假设，保证每个功能都使用当前周期。

**Files:**

- Modify: `tools/anhui_web/templates/product-all.js`
- Modify: `tools/anhui_web/templates/product-jobs-search.js`
- Modify: `tools/anhui_web/templates/product-jobs-detail.js`
- Modify: `tools/anhui_web/templates/product-jobs-ranking.js`
- Modify: `tools/anhui_web/templates/product-score-sim.js`
- Modify: `tools/anhui_web/templates/master.js`
- Test: `tests/browser_smoke_v12.js`

- [ ] **Step 6.1：先写跨功能切年失败测试**

对每个周期执行：

1. 激活周期；
2. 进入全岗位库，断言总数；
3. 进入岗位检索，断言默认结果数；
4. 打开首条详情，断言周期标签和全局 ID；
5. 进入城市榜单，断言统计合计；
6. 进入分数模拟，断言样本周期；
7. 返回地图，断言上下文栏仍是同一周期。

核心断言：

```javascript
const expected = {
  '2024': { posts: 10017, recruits: 15331 },
  '2025': { posts: 10150, recruits: 14721 },
  '2026': { posts: 8511, recruits: 12006 },
};
```

- [ ] **Step 6.2：运行并确认当前脚本发生旧数据残留**

```powershell
& $runtimeNode tests/browser_smoke_v12.js --grep "all jobs|search cycle|detail cycle|ranking cycle|score cycle"
```

期望：至少一个模块仍显示初始 2026 数据，测试失败。

- [ ] **Step 6.3：为每个模块建立统一生命周期**

每个模块改为：

```javascript
function readCycleModel(bundle) { /* pure normalization */ }
function renderCycle(model, context) { /* idempotent DOM update */ }
function resetCycleState({ previous, cycle }) { /* clear invalid filters */ }

const unsubscribe = window.WanyuCycleStore.subscribe(({ bundle, ...context }) => {
  resetCycleState(context);
  renderCycle(readCycleModel(bundle), context);
});
```

禁止模块保存跨周期的 `recordById`、筛选选项和聚合缓存；需要缓存时键必须包含周期。

- [ ] **Step 6.4：岗位库改造**

- 当前周期记录才进入 `ROWS`；
- 分页回到第 1 页；
- 合法筛选保留，非法筛选清空并播报；
- DOM 行数设置上限；
- 空值按字段定义展示“未提供”，不统一替换为 0。

- [ ] **Step 6.5：检索与详情改造**

- 选项列表从当前 bundle 重建；
- 搜索索引缓存键为周期；
- 详情查询使用 `cycle:recordId`；
- 切年关闭旧详情并把焦点返回触发按钮；
- URL 带 `record` 时先激活对应周期再打开详情；
- 无匹配记录时显示可恢复错误，不白屏。

- [ ] **Step 6.6：榜单与洞察改造**

- 聚合函数只接收当前 records；
- 榜单合计必须回算到当前周期总量；
- 三年趋势单独读取轻量审计摘要，不能复用当前周期筛选结果；
- 样本不足的洞察使用中性说明，不下结论。

- [ ] **Step 6.7：分数模拟改造**

- 只读取当前周期 `score_lists`；
- 2026 的 116 条歧义样本排除；
- 页面显示样本量、排除量和口径；
- 切年清除上年计算结果；
- 无可用样本时禁用提交并显示原因。

- [ ] **Step 6.8：运行所有功能切年测试**

```powershell
& $runtimeNode tests/browser_smoke_v12.js --grep "all jobs|search cycle|detail cycle|ranking cycle|score cycle|map cycle"
```

- [ ] **Step 6.9：运行 JavaScript 语法和现有 Node 数据测试**

按当前仓库已有 Node 测试入口逐个执行，实际输出应保持 7/7 或高于现有数量；若测试清单已经变化，以命令枚举结果为准并写入报告。

### Task 7：实现跨年收藏、对比、备注与安全迁移

**目的：** 让用户资料能跨年共存，同时避免旧 v1 数据因 ID 冲突被误归到 2024/2025。

**Files:**

- Modify: `tools/anhui_web/templates/product-jobs-detail.js`
- Modify: `tools/anhui_web/templates/product-jobs-search.js`
- Modify: `tools/anhui_web/templates/product-shell.js`
- Modify: `tools/anhui_web/templates/master.js`
- Test: `tests/browser_smoke_v12.js`

- [ ] **Step 7.1：先写迁移失败测试**

浏览器启动前注入：

```javascript
localStorage.setItem('wanyu.jobSaved.v1', JSON.stringify(['001', '002']));
localStorage.setItem('wanyu.jobCompare.v1', JSON.stringify(['002']));
localStorage.setItem('wanyu.jobNotes.v1', JSON.stringify({ '001': '重点关注' }));
```

启动后断言：

- v2 保存为 `2026:001`、`2026:002`；
- v1 仍存在；
- 迁移标记只写一次；
- 重载不会重复；
- 2025 的同名原 ID 不会被误收藏。

- [ ] **Step 7.2：运行并确认 v2 键尚不存在**

```powershell
& $runtimeNode tests/browser_smoke_v12.js --grep "migrates v1|cross-cycle saved|cross-cycle compare"
```

- [ ] **Step 7.3：实现版本化存储层**

新增内部接口：

```javascript
const WanyuUserStore = {
  migrateV1ToV2(),
  loadSaved(),
  saveSaved(ids),
  loadCompare(),
  saveCompare(ids),
  loadNotes(),
  saveNotes(notes),
};
```

规则：

- v1 一律解释为 2026，原因写入迁移元数据；
- 迁移前验证 JSON 类型；
- 无效 v1 内容复制到 `wanyu.migrationErrors.v12`，不覆盖；
- 写 v2 成功后才写迁移完成标记；
- 不自动删除 v1；
- 所有 v2 ID 通过 `toGlobalId` 验证。

- [ ] **Step 7.4：实现跨年展示**

- 收藏列表按周期分组；
- 对比卡片必须显示周期；
- 不同周期可并排，但聚合区显示“跨周期对比，不等同于同年排名”；
- 已不存在的记录显示“来源版本中未找到”，保留用户备注和原 ID。

- [ ] **Step 7.5：测试存储损坏和配额失败**

模拟非法 JSON、数组中含非字符串、`QuotaExceededError`。页面必须提示保存失败但保持当前操作状态，不清空既有数据。

- [ ] **Step 7.6：运行完整存储测试**

```powershell
& $runtimeNode tests/browser_smoke_v12.js --grep "v1|saved|compare|notes|quota"
```

### Task 8：明确待遇、来源档案和已知缺口的真实性边界

**目的：** UI 和报告对数据证据等级使用一致、克制、可核查的表述。

**Files:**

- Modify: `tools/anhui_web/build_pages.py`
- Modify: `tools/anhui_web/templates/master.js`
- Modify: `tools/anhui_web/templates/master.css`
- Modify: `tools/anhui_web/audit_three_years.py`
- Test: `tests/test_single_file_cycle_workbench.py`
- Test: `tests/browser_smoke_v12.js`

- [ ] **Step 8.1：先写事实边界失败测试**

Python 断言每周期审计对象包含：

```python
{
    "evidence_level": "source_archive|structured_evidence|partial_evidence",
    "known_gaps": [...],
    "verified_scope": [...],
    "unverified_scope": [...],
}
```

浏览器断言：

- 2024/2025 不出现“完整 Word 原档”；
- 待遇页始终出现“2026 快照”；
- 2026 切换后仍显示 116 条歧义关联说明；
- 已知缺口数与机器数据一致；
- 页面不出现“所有数据 100% 官方核验完成”这类越界文案。

- [ ] **Step 8.2：运行事实边界测试并确认失败**

```powershell
python -m unittest tests.test_single_file_cycle_workbench.TestTruthBoundary -v
& $runtimeNode tests/browser_smoke_v12.js --grep "truth boundary|salary snapshot|known gaps"
```

- [ ] **Step 8.3：统一证据状态枚举**

只允许：

- `verified_source_archive`
- `verified_structured_evidence`
- `partial_evidence`
- `source_not_published`
- `ambiguous_unlinked`
- `user_flagged_review`

未知值必须在构建时失败，不在 UI 中默默回退为“已核验”。

- [ ] **Step 8.4：实现证据档案视图**

可按周期、证据状态、缺口类型筛选。每条显示周期、对象范围、证据类型、相对路径或说明、审计时间。绝对本机路径不得进入交付页面。

- [ ] **Step 8.5：实现待遇快照隔离**

待遇数据放在全局 `salary_snapshot`，不复制到各周期 bundle；周期切换不改变其标题、数据和口径。上下文栏在该视图显示“独立于当前招录周期”。

- [ ] **Step 8.6：运行事实边界测试**

所有断言通过后，人工搜索敏感越界词：

```powershell
rg -n "100%|全部官方|零缺失|完全无缺失|完整原档" deliverables\皖域择岗总览.html docs tools\anhui_web\templates
```

每个命中都要人工判定；不得机械删除合法的审计说明。

### Task 9：实现构建前、构建后、打包后的三次复核器

**目的：** 把“反复核验”固化为发布流水线，不依赖人工记忆。

**Files:**

- Create: `tools/anhui_web/verify_single_file_v12.py`
- Create: `tools/anhui_web/data/single_file_verification_v12.json`
- Create: `tools/anhui_web/data/single_file_diff_v12.json`
- Create: `docs/三年单文件数据复核报告_v12.md`
- Modify: `tools/anhui_web/release.py`
- Modify: `build.ps1`
- Modify: `test.ps1`
- Test: `tests/test_single_file_cycle_workbench.py`

- [ ] **Step 9.1：先写复核器失败测试**

覆盖八层：文件盘点、结构、总量、关联、bundle、HTML、DOM 报告、ZIP。最少包括：

```python
class TestSingleFileVerifier(unittest.TestCase):
    def test_rejects_unexpected_total_drift(self): ...
    def test_allows_only_named_known_gaps(self): ...
    def test_rejects_new_gap_even_when_totals_match(self): ...
    def test_round_trips_all_embedded_payloads(self): ...
    def test_rejects_html_over_hard_size_limit(self): ...
    def test_zip_contains_exactly_one_primary_html(self): ...
    def test_report_distinguishes_verified_and_unverified_scope(self): ...
```

- [ ] **Step 9.2：运行并确认复核器模块不存在**

```powershell
python -m unittest tests.test_single_file_cycle_workbench.TestSingleFileVerifier -v
```

- [ ] **Step 9.3：实现命令行接口**

```powershell
python tools/anhui_web/verify_single_file_v12.py prebuild
python tools/anhui_web/verify_single_file_v12.py postbuild --html 'deliverables\皖域择岗总览.html'
$releaseZip = Join-Path ([Environment]::GetFolderPath('Desktop')) ('皖域择岗档案_网页产品化升级版_{0}_v12.0.zip' -f (Get-Date -Format 'yyyyMMdd'))
python tools/anhui_web/verify_single_file_v12.py package --zip $releaseZip
```

退出码：

- `0`：全部硬门通过，可有已登记警告；
- `1`：数据、结构、体积、入口或缺口漂移；
- `2`：命令参数或输入文件缺失。

- [ ] **Step 9.4：实现机器报告模式**

`single_file_verification_v12.json` 顶层：

```json
{
  "release": "v12.0",
  "generated_at": "ISO-8601 with timezone",
  "phases": {
    "prebuild": {},
    "postbuild": {},
    "package": {}
  },
  "baselines": {},
  "known_gaps": [],
  "checks": [],
  "status": "pass|fail"
}
```

每个 check 包含 `id`、`layer`、`status`、`expected`、`actual`、`evidence_path`、`message`。

- [ ] **Step 9.5：实现差异账本**

即使无差异也生成：

```json
{
  "release": "v12.0",
  "unexpected": [],
  "allowed_known_gaps": [],
  "resolved_since_v11": [],
  "status": "clean"
}
```

旧缺口如果消失，必须注明是“证据已补齐”还是“数据被误删”；没有证据不能自动标为已解决。

- [ ] **Step 9.6：实现人读报告**

报告固定章节：输入盘点、冻结基线、结构检查、逐年逐考试总量、成绩关联、已知缺口、HTML 反解析、浏览器复核、ZIP 复核、性能、结论与不能声明的事项。

- [ ] **Step 9.7：接入构建脚本**

`build.ps1` 顺序固定：

1. `prebuild`；
2. 数据构建；
3. HTML 构建；
4. Python/Node 测试；
5. `postbuild`。

任一步非零立即停止。

- [ ] **Step 9.8：运行复核器测试和真实预构建复核**

```powershell
python -m unittest tests.test_single_file_cycle_workbench.TestSingleFileVerifier -v
python tools/anhui_web/verify_single_file_v12.py prebuild
```

### Task 10：性能、无障碍、窄屏和离线稳定性专项

**目的：** 确保单文件变大后仍能实际使用，而不是只在源码测试中通过。

**Files:**

- Modify: `tools/anhui_web/templates/cycle-runtime.js`
- Modify: `tools/anhui_web/templates/cycle-unified.css`
- Modify: `tools/anhui_web/templates/product-all.js`
- Modify: `tools/anhui_web/templates/product-jobs-search.js`
- Modify: `tests/browser_smoke_v12.js`

- [ ] **Step 10.1：增加性能仪表和失败断言**

浏览器记录：

- `navigationStart → app:ready`；
- 每个年份第一次 `activate`；
- 已缓存年份再次 `activate`；
- 关键词筛选；
- 城市 + 类别组合筛选；
- 详情打开和关闭。

每项测三次，报告中写中位数和最慢值。硬门使用最慢值。

- [ ] **Step 10.2：确认未优化版本的实际结果**

```powershell
& $runtimeNode tests/browser_smoke_v12.js --grep "performance budget"
```

如果已经通过，也保留基准输出；不为了制造失败而降低阈值。

- [ ] **Step 10.3：只解析当前周期的大载荷**

启动时不得执行三次全量 `JSON.parse`。浏览器测试通过注入解析计数器断言：默认启动仅解析 2026；切换 2024 后为 2；再次切回 2026 仍为 2。

- [ ] **Step 10.4：限制 DOM 和重计算**

- 列表只渲染当前页；
- 搜索输入使用 100–150ms 防抖；
- 聚合缓存包含周期和筛选签名；
- 周期切换主动释放旧大数组的模块引用；
- 隐藏视图不执行重绘。

- [ ] **Step 10.5：无障碍键盘测试**

只用键盘完成：跳到主内容、切年份、切导航、设置筛选、打开详情、关闭详情并返回原按钮。检查：

- 无焦点陷阱；
- 焦点可见；
- `aria-selected` 正确；
- `aria-live` 不重复播报；
- Escape 只关闭最上层浮层。

- [ ] **Step 10.6：窄屏和缩放测试**

视口：390×844、430×932、768×1024、1440×900；桌面 200% 缩放。断言页面主体无不可控横向滚动、按钮不重叠、表头或卡片保留关键字段。

- [ ] **Step 10.7：离线和外部请求测试**

监听所有请求，除当前 `file://` 文档外不得出现 `http://` 或 `https://`。断网环境重载三次，切换三个年份和核心视图均成功。

- [ ] **Step 10.8：运行专项测试**

```powershell
& $runtimeNode tests/browser_smoke_v12.js --grep "performance|keyboard|responsive|offline|external request"
```

### Task 11：发布流水线、唯一入口和旧版可恢复归档

**目的：** 正式交付目录让用户只需要判断一个入口，同时保留可回滚能力。

**Files:**

- Modify: `tools/anhui_web/release.py`
- Modify: `build.ps1`
- Modify: `test.ps1`
- Create: `deliverables/HANDOFF.md`
- Create: `deliverables/MANIFEST.txt`
- Move after acceptance: `deliverables/2024/皖域择岗总览.html` → `deliverables/legacy_v11/2024/皖域择岗总览.html`
- Move after acceptance: `deliverables/2025/皖域择岗总览.html` → `deliverables/legacy_v11/2025/皖域择岗总览.html`
- Move after acceptance: `deliverables/安徽十六市2026软件工程可报岗位.html` → `deliverables/legacy_v11/安徽十六市2026软件工程可报岗位.html`
- Move after acceptance: `deliverables/安徽全省16市本科普通岗全包分析.html` → `deliverables/legacy_v11/安徽全省16市本科普通岗全包分析.html`

- [ ] **Step 11.1：先写发布结构失败测试**

断言：

- 根目录唯一 `.html` 文件名为 `皖域择岗总览.html`；
- ZIP 正式交付区不存在并列的 `2024/皖域择岗总览.html`、`2025/皖域择岗总览.html` 或两个 2026 兼容页入口；
- `legacy_v11/` 若存在，`HANDOFF.md` 明确其非正式入口；
- `MANIFEST.txt` 每个文件有相对路径、字节数和 SHA-256；
- 不包含用户名绝对路径、临时浏览器 profile、缓存或密钥文件。

- [ ] **Step 11.2：运行并确认当前发布结构不满足唯一入口**

```powershell
python -m unittest tests.test_single_file_cycle_workbench.TestReleasePackageLayout -v
```

- [ ] **Step 11.3：重构 `release.py` 的阶段顺序**

固定顺序：

1. 预构建审计；
2. 三周期 bundle 构建；
3. 唯一 HTML 构建；
4. 单元和 Node 测试；
5. 浏览器 v12 冒烟；
6. 构建后审计；
7. 在新临时目录组装压缩包；
8. ZIP 解压复核；
9. 生成最终哈希和交接报告；
10. 所有步骤成功后再替换正式入口。

使用临时文件名生成主 HTML，校验成功后用同卷原子替换，避免失败时留下半写文件。

- [ ] **Step 11.4：更新交接说明**

`HANDOFF.md` 开头必须直接写：

```text
唯一入口：皖域择岗总览.html
打开方式：双击本地打开，不需要服务器或联网。
三年切换：页面顶部选择 2024、2025、2026。
待遇口径：待遇模块为 2026 快照，不代表历史待遇。
```

然后列出冻结总量、已知缺口、复核命令、版本号和 SHA-256。

- [ ] **Step 11.5：执行旧版归档前置检查**

只有以下条件全部为真才移动旧页面：

- v12 Python、Node、浏览器和复核器全部通过；
- v12 主 HTML 已在新的临时目录打开；
- 三年核心视图都已实际点击；
- v11 文件哈希已记录；
- `legacy_v11/` 目标路径已解析并确认在 `deliverables` 内。

不得递归删除旧目录；使用可恢复移动。

- [ ] **Step 11.6：运行发布布局测试**

```powershell
python -m unittest tests.test_single_file_cycle_workbench.TestReleasePackageLayout -v
```

### Task 12：全量验收、ZIP 解包复测和最终交接

**目的：** 用新鲜证据完成最后交付，不以“构建成功”代替真实使用验证。

**Files:**

- Verify: `deliverables/皖域择岗总览.html`
- Verify: `docs/三年单文件数据复核报告_v12.md`
- Verify: `tools/anhui_web/data/single_file_verification_v12.json`
- Verify: `tools/anhui_web/data/single_file_diff_v12.json`
- Verify: final ZIP created by `tools/anhui_web/release.py`

- [ ] **Step 12.1：运行所有 Python 测试**

```powershell
python -m unittest discover -s tests -p 'test*.py' -v
```

记录实际测试总数、通过数、失败数和耗时。任何失败都不得打包。

- [ ] **Step 12.2：运行全部 Node 数据测试**

```powershell
$runtimeNode='C:\Users\24218\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
$env:NODE_PATH='C:\Users\24218\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
Get-ChildItem tests -Filter '*.js' | Where-Object { $_.Name -match 'test|audit' } | ForEach-Object { & $runtimeNode $_.FullName; if ($LASTEXITCODE -ne 0) { throw "Node test failed: $($_.Name)" } }
```

若某脚本是浏览器脚本而非数据单测，应使用它规定的入口执行，不能因为枚举方式不兼容而跳过。

- [ ] **Step 12.3：运行 v12 浏览器全流程**

```powershell
& $runtimeNode tests/browser_smoke_v12.js
```

至少完成以下端到端路径：

1. 2026 → 岗位检索 → 筛选 → 详情 → 收藏；
2. 切 2025 → 同视图重绘 → 对比一条岗位；
3. 切 2024 → 分数模拟 → 查看样本口径；
4. 三年总览切指标；
5. 待遇页确认 2026 快照；
6. 证据档案查看已知缺口；
7. 刷新和浏览器后退恢复周期；
8. 重启新上下文后确认 v1→v2 迁移。

- [ ] **Step 12.4：运行构建后复核**

```powershell
python tools/anhui_web/verify_single_file_v12.py postbuild --html 'deliverables\皖域择岗总览.html'
```

必须从最终 HTML 反解析三个 payload，再计算三年岗位数、招录人数、考试分类和成绩关联；不得只读取源 JSON。

- [ ] **Step 12.5：生成正式压缩包**

```powershell
python tools/anhui_web/release.py --zip
```

压缩包文件名包含产品名和 `v12.0`，不包含本机用户名或临时路径。

- [ ] **Step 12.6：从 ZIP 解包到全新临时目录复测**

PowerShell 使用 `New-Item` 创建明确的临时子目录，解析并确认目录位于系统临时目录后解压。复测：

- 唯一入口存在；
- 相对资源不缺失；
- 三个年份可切换；
- 不发生外部网络请求；
- localStorage 核心功能可写；
- 三年总量和主目录版本一致。

- [ ] **Step 12.7：运行压缩包层复核**

```powershell
$releaseZip = Join-Path ([Environment]::GetFolderPath('Desktop')) ('皖域择岗档案_网页产品化升级版_{0}_v12.0.zip' -f (Get-Date -Format 'yyyyMMdd'))
if (-not (Test-Path -LiteralPath $releaseZip)) { throw "Release ZIP not found: $releaseZip" }
python tools/anhui_web/verify_single_file_v12.py package --zip $releaseZip
```

- [ ] **Step 12.8：生成最终 SHA-256**

```powershell
Get-FileHash 'deliverables\皖域择岗总览.html' -Algorithm SHA256
Get-FileHash -LiteralPath $releaseZip -Algorithm SHA256
```

将哈希写入 `HANDOFF.md`、`MANIFEST.txt` 和复核报告。三处不一致则失败。

- [ ] **Step 12.9：最终人工验收清单**

- [ ] 根目录只需打开一个 HTML；
- [ ] 2024、2025、2026 都在站内切换；
- [ ] 三年总览数字与冻结基线一致；
- [ ] 所有核心功能切年后没有旧数据残留；
- [ ] 待遇明确为 2026 快照；
- [ ] 116 条歧义关联、30 岗未发布等缺口可见；
- [ ] 空值没有被伪造为 0；
- [ ] 收藏和对比带周期，旧数据迁移可回退；
- [ ] 手机、平板、桌面无关键遮挡；
- [ ] 页面完全离线；
- [ ] ZIP 在全新目录可打开；
- [ ] 最终报告只声明已经由证据支持的范围。

- [ ] **Step 12.10：交付结论模板**

只有所有硬门通过后，最终交接使用：

```text
已完成 v12.0 三年单文件交付。唯一入口为“皖域择岗总览.html”，2024、2025、2026 均在站内切换。三年结构、总量、嵌入载荷、浏览器渲染和最终 ZIP 已逐层复核；已知来源缺口继续明确保留，没有用推断或 0 补齐。测试数量、性能结果、HTML/ZIP 哈希和仍未解决事项见“三年单文件数据复核报告_v12.md”。
```

如果任一硬门未通过，结论必须改为“未完成交付”，列出失败检查、实际值、预期值和下一步，不能用“基本完成”替代。

## 四、功能迭代优先级与里程碑

### P0：单文件和数据不串年

对应 Task 1–4。完成标志：三年载荷进入一个 HTML，周期状态源、URL 恢复和惰性解析通过。P0 未完成时不得开始旧页面归档。

### P1：核心决策功能可切年

对应 Task 5–8。完成标志：九个主视图、岗位检索、详情、榜单、分数模拟、收藏/对比和证据档案都通过跨年浏览器测试。

### P2：真实性和稳定性固化

对应 Task 9–10。完成标志：三次复核器接入、性能硬门通过、键盘和窄屏关键路径通过、零外部请求。

### P3：正式交付与回滚保障

对应 Task 11–12。完成标志：唯一入口、可恢复 v11 归档、ZIP 解包复测、哈希和交接报告全部一致。

## 五、预计执行顺序与检查点

1. **检查点 A——数据冻结：** Task 1 完成；任何基线漂移先停下解释。
2. **检查点 B——架构闭环：** Task 2–4 完成；能在同一 HTML 切年且无数据串扰。
3. **检查点 C——功能闭环：** Task 5–8 完成；所有核心功能和事实边界通过。
4. **检查点 D——质量闭环：** Task 9–10 完成；复核、性能、无障碍和离线通过。
5. **检查点 E——交付闭环：** Task 11–12 完成；新目录解包复测和哈希通过。

每个检查点输出一次简短状态：已完成项、测试命令、实际通过数、仍存在的已知缺口、是否允许进入下一阶段。状态不能只写“正常”或“已优化”。

## 六、明确不在本轮擅自扩展的范围

- 不新增在线账号、云同步、后端数据库或远程部署；
- 不凭网络搜索改写历史岗位原始事实；
- 不自动“修复”116 条歧义成绩关联；
- 不把 2026 待遇快照推算成 2024/2025 待遇；
- 不删除旧 v11 文件，只做可恢复归档；
- 不在未通过 ZIP 解包复测前宣布最终完成。
