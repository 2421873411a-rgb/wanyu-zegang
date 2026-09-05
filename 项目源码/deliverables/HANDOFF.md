# 皖域择岗档案 · v16.0 最终交接说明

## 两个正式入口

**无服务器离线入口：`皖域择岗总览.html`**  
**长期维护入口：`maintainable/index.html`**

单文件入口可直接双击，不需要服务器或联网；页面顶部选择 **2024、2025、2026**，三个周期在同一个 HTML 文件内切换。长期维护入口把界面和数据分离：通过 `python tools/anhui_web/serve_maintainable.py --port 8765` 服务后访问 `http://127.0.0.1:8765/index.html`，周期 JSON 按需加载。旧版分拆页面已移入 `legacy_v11/`，仅作可恢复归档。

## 交付范围

| 周期 | 全量岗位 | 招录人数 | 省考 | 事业编 | 国考 |
|---:|---:|---:|---:|---:|---:|
| 2024 | 10,017 | 15,331 | 4,243 / 7,235 | 5,215 / 6,911 | 559 / 1,185 |
| 2025 | 10,150 | 14,721 | 4,116 / 6,620 | 5,491 / 6,956 | 543 / 1,145 |
| 2026 | 8,511 | 12,006 | 3,784 / 5,791 | 4,176 / 5,065 | 551 / 1,150 |

表内考试列格式为“岗位数 / 招录人数”。岗位检索保留每个周期的全部岗位行，维护站默认按 60 行分页并可切换 30/120；筛选、详情、收藏、对比、键盘切换和导出均在本地完成。

## v16.0 离线缓存与数据工作台（2026-09-02）

- 维护站升级为可安装 PWA（F10）：`sw.js` 对数据 JSON 走 network-first、离线回退缓存，对壳层资产 cache-first 后台刷新；DataStore 的 manifest 字节数与 SHA-256 校验不变，缓存数据过旧会被拒载。离线时页头显示「离线缓存」徽标。
- 收藏与快照页新增工作台导出/导入：带版本的 JSON，导入逐字段校验清洗，坏文件报错不落盘。
- 使用说明页新增六步「数据更新清单」（勾选本机持久化 + 命令一键复制），明示不替代磁盘校验。
- 单文件 `皖域择岗总览.html` 按 D5 方案 A 定位为数据归档快照：顶部提示条指引导维护站入口，视觉冻结，数据仍随发布链更新。
- 磁盘校验 **217 passed / 0 failed**；发布链 20 模块全绿；浏览器实测 SW 接管、数据入缓存可解析、工作台往返一致、控制台 0 报错。

## v15.1 加载体验与清债（2026-09-02）

- 每周期新增 `jobs_lite.json` 轻索引（全量 43%）：检索/榜单/地图/收藏走轻索引，`jobs.json` 降级为详情抽屉按需加载；视图切换有骨架加载态与失败重试。
- `test_anhui_web.py` 8 个过期契约清偿并纳入发布门禁；页面构建沙箱化，不再触碰 `deliverables/`。
- 窄屏导航换行、跳到主内容 skip-link、状态节点 aria-live。

## v15.0 数据驾驶舱升级（2026-09-02）

- 维护站引入双主题设计令牌（Token v3）：亮色默认，右上角可切换暗色主题；选择持久化，未选择时跟随系统。全部组件颜色走 CSS 变量，JS 不再硬编码主色；WCAG AA 对比度由 `tests/test_ui_v15.py` 数学回归保障。
- 每周期新增派生模块 `derived.json`（vs_prev 增量、专业 mix、城市招录走势与未归并城市公开计数）和命令面板索引 `palette.json`；两者均由构建脚本从源岗位行派生，`jobs.json` 源原文不变。
- 新功能：`Ctrl/Cmd+K` 命令面板（跨岗位直达 + 视图/主题切换）、总览 bento 网格（delta 芯片、mixbar、sparkline、奖牌排行、覆盖度芯片）、三年对照斜率图、`#job/<ID>` 岗位分享链接、对比清单字段级差异高亮与 CSV 导出、榜单竞争观测列/数字条/奖牌标识、检索紧凑密度与打印样式。
- 磁盘校验扩展到 **185 passed / 0 failed**：新增 derived 数学交叉核对（deltas 与 manifest 差值一致、mix 合计=岗位数、city_trend+unmapped=岗位数）和 palette 索引核对（ID 唯一且 ⊆ 岗位行 ID）。
- 数据真实性与完整性边界不变：未知值不推断为 0，公开缺口继续按证据状态保留；派生模块全部可从源岗位行复算。
- 已知事项更新（v15.1）：`test_anhui_web.py` 的 8 个 v9/v10 过期契约已清债，页面构建改为沙箱目录不再触碰 `deliverables/`，模块已纳入发布门禁；F10（PWA 离线缓存）延后。

## v14.4 用户走查与维护升级（2026-09-01）

- 统一入口仍为 `maintainable/index.html`：顶部可切换 2024、2025、2026，地图、三年对照、岗位榜单、逐岗检索、收藏与快照、数据审计、使用说明和更新日志在同一页面切换。
- 岗位榜单和逐岗检索改用可读专业关键词目录：当前三周期目录模式为 `readable_keywords`，2024/2025/2026 分别生成 3,097 / 2,956 / 2,617 个关键词候选；岗位原始 `zy` 文本不改，纯数字/纯编码候选为 0，软件工程、法学等常用词可直接选择。
- 地图新入口会清理旧关键词、专业、城市和考试条件，保留明确的“地图汇总”筛选；检索页显示已生效条件并提供逐项清除、全部清空、排序和每页行数控制。
- 岗位详情将职位名称置于标题，来源定位默认收起，支持“加入对比”；源材料日期无值时显示“未提供”，不会使用 `2000-01-01` 占位日期。收藏页支持重新打开当前周期岗位，并显示对比清单。
- 审计状态、风险级别和匹配规则改为用户可读文本，长标签和源路径可折叠且不会溢出；帮助页和更新日志改为读取 manifest/审计数据，不再硬编码旧版本或旧统计。
- 颜色沿用参考图方向的 `#3A83F7` 淡蓝体系，近白画布、浅蓝边界、低对比阴影，不把青绿色作为主视觉。

本轮证据：`python tools/anhui_web/verify_maintainable_site.py deliverables/maintainable` 为 **142 passed / 0 failed**；`tests/maintainable_browser_smoke.js` 为 **PASS**；内置浏览器跨页面最终行为走查为 **22/22**、控制台 error/warn 为 **0**。完整页面截图和逐项分析见 `tests/artifacts/audit-20260901/REPORT.md`。

## 数据真实性与完整性边界

本交付已核验“当前源包内部结构与聚合完整”，并没有把无法取得的官方逐项资料伪称为已确认事实。待遇模块是 **2026 快照**，不代表 2024/2025 历史待遇。当前仍有 8 项公开资料边界，已核验调整另行列出；这些是资料可取得性边界，不是 UI 缺陷。

- 成绩安全关联：2024 **4,087**，无法唯一匹配 **0**；2025 **4,107 / 0**；2026 **6,521 / 116**。116 条因候选岗位不唯一而安全留空，不强行绑定。
- 2024 缺口：省考合格/缴费官方无逐岗表；拟聘用市级批次约 30+ 批未回收；事业编下半年官方原始 xlsx 未逐单位回收。133 条定向岗已改登记为“源包补充边界”，每行保留“（镜像源合成）”备注。
- 2025 缺口：省考合格/缴费官方无逐岗表；事业编逐岗报名官方未发布；阜阳拟聘官方附件仍未取得。事业编上半年单位名称列已修复，不再列为缺口；蚌埠、池州、铜陵、宣城 11 批官方拟聘附件已补采。
- 2026 缺口：成绩收割存在边界；116 条成绩无法唯一匹配。0801048 与 3 条国考岗位备注已通过本地官方原始文件复核并关闭。
- 已核验调整：2026 事业编页面相对已归档源组件增加 **54 岗 / 55 人**，页面将其作为已登记来源调整展示；2024 的 133 条源包补充行与 2025 的 11 批官方拟聘附件均在“三年对照”中单列，不计入未核验缺口。

详情页和“三年对照”页均保留证据层、来源文件与缺口，不以 0 代替未知。完整性结论限定为“当前交接包内部可复现、可对账”，不能扩展为“所有外部官方逐岗资料均已取得”。

## 已完成的 UI / 功能升级

- 顶部周期标签、URL 周期/视图恢复、浏览器历史回退、键盘方向键与 Enter/Space 切换。
- 岗位检索统一接入三年全量数据，支持关键词、城市、考试类别、性质、资格标签、排序、批量代码、分页和适配度。
- 岗位详情、收藏、对比、备注使用周期级 ID；旧版 v1 收藏/对比/备注自动迁移到 v2，不覆盖旧数据。
- 分数模拟、成绩明细、审计范围和待遇口径集中在同一文件；历史周期不再显示没有证据的伪造模拟结果。
- 离线单文件，无远程脚本、样式、图片或字体；桌面、768px 和 390px 视口均通过无横向溢出检查。
- 长期维护站使用 `maintainable/index.html` + `maintainable/assets/` + `maintainable/data/cycles/<cycle>/{overview.json,jobs.json,audit.json}`；HTML 壳不内嵌三年岗位行，manifest 为每份模块 JSON 固定记录数量、来源边界和 SHA-256。
- 全局审计索引为 `maintainable/data/audit/three-year.json`；它集中记录三年证据等级、公开缺口和无法唯一匹配成绩，不改变源数据，也不把未知值推断为零。

## v13.1 冷白雾蓝视觉校准（2026-09-01）

- 总网站恢复“浅蓝卡片台 / 研究工作台”视觉：冷白雾蓝画布、深蓝标题、蓝色主操作、青色与琥珀色作为少量数据标记；移除米黄纸纹、深绿控制台和过重的朱砂强调。
- 首屏保留 SOURCE → METRIC → DECISION 证据索引与 `2024—26` 状态牌，但改为轻量蓝色证据 rail 和白色状态卡，三年范围、16 座城市、离线可复核及公开边界仍清晰可见。
- 全局筛选恢复白色轻面板，KPI 恢复独立信息卡，城市矩阵、城市画像、短名单和三年审计统一使用浅蓝边界、低对比阴影和可读的蓝色层级；缺口/不可比仍保留语义色，不伪装成成功值。
- 2024、2025、2026 继续在同一 HTML 内切换；`ui-v13.css` 仍作为独立注入层，构建时先清除旧样式块，避免反复构建导致 CSS 累积，并补齐 768px / 390px 媒体级联。
- `tests/test_ui_v13.py` 视觉与导航契约新增冷白雾蓝校准断言、浅色工作台和专业候选展示契约，共 **8/8**。

## v13.2 榜单专业筛选与长期维护站（2026-09-01）

- 岗位榜单新增“专业”输入/候选选择：按当前榜单岗位行的专业原文筛选城市，筛选后重新排名；支持 URL `major` 状态恢复，清空后恢复全量城市。
- 顶部由深色方案调为轻量层级，周期上下文改为浅蓝灰，保留品牌、周期、审计入口和数据状态，不牺牲对比度。
- 新增 `maintainable/` 外置 JSON 站：总览、三年对照、岗位榜单、岗位检索、数据边界五个核心视图，三年数据按周期懒加载；输入控件重绘时保留光标位置。
- 维护站与单文件共用 `unified_cycle_bundle.py`、三年审计和同一批稳定 ID；不新增第二套人工数据源。
- 维护站构建说明见 `docs/长期维护网站架构方案_v1.md`；构建入口为 `tools/anhui_web/build_maintainable_site.py`，发布脚本会自动同步生成。

## v13.3 专业候选清洗与浅色 AI 工作台（2026-09-01）

- “我的专业”、岗位地图、岗位榜单和长期维护站的候选控件统一过滤纯数字/纯符号编码，清理前置代码残片并去重排序；岗位原始 `zy` 字段不改，数据证据仍完整保留。

## v13.4 审计中心、数据分层与组合筛选（2026-09-01）

- 维护站增加“数据审计”工作区：三年审计汇总、周期状态、证据等级、公开缺口和成绩待复核量集中展示。
- 每个周期拆为 `overview.json`、`jobs.json`、`audit.json`；岗位行只在 `jobs.json`，可单独替换岗位数据、审计数据或总览摘要。
- 岗位榜单增加专业、城市、考试类别、岗位类型和排序指标组合筛选；所有条件均作用于当前周期原始岗位行，清空后恢复全量。
- 单文件每个周期重新生成岗位地图与全岗位库视图，防止旧 HTML 骨架恢复脏候选；维护站由同一数据 bundle 生成，保持两种入口一致。
- 顶部改为白底、浅灰上下文带、细边框和轻阴影，蓝色只用于选中态、关键操作和数据标记；借鉴现代 AI 工作台的克制层级与输入反馈，不复制 DeepSeek 品牌素材。

## 本轮数据设计与交互优化

- 每个岗位行新增周期级稳定 `job_id`：由考试类别、城市、职位代码、单位和源表职位身份生成，不把招录人数放入 ID，避免人数修订导致收藏、对比和备注漂移；`row_id` 保留兼容，旧 ID 仅作迁移追溯。
- 每行新增 `score_observation`：明确区分可比、未取得、疑似 0 哨兵、量纲不兼容和不适用；分数模拟只接受同一 `scale_id` 的可比成绩。
- 每行新增 `competition_observations`：报名人数、有效笔试/达线人数、国考进面名单分开保存；聚合层新增 `ratio_status` / `ratio_comparable`，混合分母、缺失分母或覆盖不完整时显示“不可比”，不参与排名、平替和推荐。
- 职位名称新增 `title_status` / `display_title`：源表未单列时展示“源表未单列披露”，不以单位名称代替职位名称。
- 周期切换改为单文件内重新挂载对应 payload，不再因切换周期强制整页刷新；三年收藏、对比和备注继续按周期隔离。
- 成绩索引嵌入采用精简字段，仅保留 `by_key` 与关联元数据；最终 HTML 当前大小约 61.1 MB，仍低于 80 MiB 硬门槛。
- 完整字段状态分布和口径说明见 `docs/数据字典.md`；本轮审计设计门禁见 `docs/三年数据真实性与完整性审计_v12.md`。

## 本次新增官方归档

2025 省考拟聘用原始附件已新增并纳入基线清单：蚌埠 5 批 283 人、池州 3 批 335 人、铜陵 1 批 76 人、宣城 2 批 326 人，共 11 批 1020 人。附件按岗位代码、准考证号、空值和 master 代码逐项检查；原始文件与 SHA-256 见 `tools/anhui_web/data/single_file_baseline_v12.json`，公告入口见 2025 周期 `cycle.json` 的 `source_urls`。

## 验收证据（2026-09-01，本轮执行）

- 构建前源清单与 bundle：**94/94 PASS**（其中 11 个新增官方拟聘附件纳入 SHA-256 清单）。
- 最终 HTML 独立反解析：**51/51 PASS**，包括三年岗位行数/招录人数、稳定 ID、成绩状态、竞争分母分离、职位名称披露状态、缺口载荷、无远程资源、无绝对用户路径和 <80 MiB。
- 三年源审计：**54/54 PASS**；本次发布链 Python 单测：**60/60 PASS**；Node 核心逻辑：**7/7 PASS**；单文件视觉与导航契约：**8/8 PASS**。
- 最终 HTML 独立反解析：**51/51 PASS**；构建前源清单：**94/94 PASS**；正式单文件浏览器 fresh smoke：**13/13 PASS**，覆盖三周期加载、专业候选清洗、榜单筛选/清空、URL/历史恢复、详情/收藏/对比、键盘周期切换，以及 390 / 768 / 1440 视口无横向溢出。
- 维护站 HTTP 浏览器闭环 **PASS**，覆盖三周期切换、外置 JSON、专业候选/榜单筛选、检索、边界、无远程资源和响应式；ZIP 内部校验：**50/50 PASS**。
- 维护站磁盘级模块校验：**63/63 PASS**，重新读取并核对 manifest、三类模块哈希、岗位行数、招录合计、稳定 ID、审计汇总和本地资源。
- 详细报告：`docs/三年单文件数据复核报告_v12.md`。
- 机器校验记录：`tools/anhui_web/data/single_file_verification_v12.json`、`single_file_diff_v12.json`。

## 重建与复核

```powershell
python tools/anhui_web/audit_three_years.py --root . --output-json tools/anhui_web/data/three_year_audit.json --report docs/三年数据真实性与完整性审计_v12.md
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
python tools/anhui_web/verify_single_file_v12.py prebuild
python tools/anhui_web/verify_single_file_v12.py postbuild --html deliverables/皖域择岗总览.html
python tools/anhui_web/build_maintainable_site.py --root . --output-dir deliverables/maintainable
python tools/anhui_web/serve_maintainable.py --port 8765
python tools/anhui_web/gen_data_dict.py
node --test tests/test_wanyu_core.cjs
$env:NODE_PATH = 'C:\Users\<用户名>\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
node tests/browser_smoke_v12.js
python tools/anhui_web/release.py --skip-tests --zip
```

其中 `NODE_PATH` 只是在当前机器找不到全局 Playwright 时使用；成品本身不依赖 Node 或联网。

## 交接结论

正式交付包含本目录的 `皖域择岗总览.html`（离线快照）和 `maintainable/index.html`（长期维护站）。两者均包含三年数据入口并共用审计后的周期载荷；当前无法取得或无法安全匹配的资料边界继续公开保留。不能声明所有官方材料均已发布、所有字段均有逐岗官方原文，或数据达到“100% 无缺失”。

## v14.0 全量升级交接

### 推荐入口

长期维护主入口：`deliverables/maintainable/index.html`。先运行 `python tools/anhui_web/serve_maintainable.py --port 8765`，再打开 `http://127.0.0.1:8765/index.html`。网页内可切换 2024、2025、2026，不需要在多个 HTML 间跳转。

离线回退入口：`deliverables/皖域择岗总览.html`，可直接双击；它是归档快照。维护站 `index.html` 不建议直接双击，因为浏览器会阻止 `file://` 读取外置 JSON。

### v14.0 外置模块

每个周期均有 `overview.json`、`jobs.json`、`catalog.json`、`positions.json`、`scores.json`、`changes.json`、`audit.json`；全局有 `data/audit/three-year.json` 和 `data/audit/review-queue.json`。`jobs.json` 保存岗位原文，`scores.json` 保存全部成绩索引和未唯一匹配项，`changes.json` 保存相邻周期变化与匹配策略，manifest 保存每个文件的 SHA-256。

### 当前可复现数据锚点

2024：10,017 岗 / 15,331 人 / 成绩待复核 0；2025：10,150 岗 / 14,721 人 / 0；2026：8,511 岗 / 12,006 人 / 116。三年合计 28,678 岗 / 42,058 人，公开审计边界 8 项。116 条因成绩附件缺少城市且岗位代码对应多个候选而安全留空，不能强行关联。

### 更新与回滚

更新顺序、来源登记、模块替换、校验命令和模块级回滚规则见 `docs/数据更新操作手册.md` 与 `docs/长期维护网站架构方案_v2.md`。回滚必须使用同周期同模块的上一版文件和 manifest 哈希，先备份当前文件，再恢复、重建 manifest、运行磁盘校验；不得跨周期替换或跳过审计。当前工作区没有 Git 仓库，发布目录、ZIP、manifest 和 SHA-256 是交接证据。

### v14.0 验收命令

```powershell
python tools/anhui_web/verify_maintainable_site.py deliverables/maintainable
python -m unittest tests.test_v14_upgrade_baseline tests.test_data_contract tests.test_source_registry tests.test_catalog_and_changes tests.test_position_detail_contract tests.test_changes_and_comparability tests.test_review_queue tests.test_scores_contract tests.test_datastore_contract tests.test_accessibility_and_export tests.test_ui_v14 tests.test_maintainable_site tests.test_release_v14 -v
node tests/test_datastore_contract.cjs
node --test tests/test_user_store_contract.cjs
node tests/maintainable_browser_smoke.js
python tools/anhui_web/release.py --zip
```

真实性边界不变：交接包内部数据可复现、可对账，不等于所有外部官方逐岗材料均已发布或取得；未发布、未取得、无法唯一关联的值继续展示为状态和空值。

## v14.0 岗位地图恢复补丁（2026-09-01）

之前旧版地图在迁移到长期维护站时漏接。本补丁已恢复到统一入口 `http://127.0.0.1:8765/index.html#jobs_map`，不再要求打开另一个网页文件。

- 地图几何源：`tools/anhui_web/data/anhui_340000_full.json`，构建为 `maintainable/data/map/anhui.json`，包含真实安徽十六市投影路径和标签坐标。
- 地图数值源：当前周期 `data/cycles/<cycle>/jobs.json`；可切换岗位数/招录人数，数值按岗位行实时汇总。
- 交互：点击区域、城市标签或城市卡打开检查器；检查器可进入岗位检索的地图城市组筛选；支持 Enter/Space 键盘选择和移动端响应式布局。
- 口径：`省直`不属于十六市地图边界，单独作为直属口径展示，绝不拼接成“省直市”；2024 区县、市直、宿松、广德只做导航归并，岗位详情仍展示原始城市值。
- 当前生成站磁盘校验为 **142 项通过 / 0 项失败**；维护站浏览器烟测覆盖地图加载、16 区域、指标切换、城市检查器、岗位检索联动、三周期、专业筛选、审计和响应式。

地图数据若要更新，只替换源 GeoJSON 后重新执行 `python tools/anhui_web/build_maintainable_site.py --root . --output-dir deliverables/maintainable`，再执行 `python tools/anhui_web/verify_maintainable_site.py deliverables/maintainable` 和 `node tests/maintainable_browser_smoke.js`；不能直接改生成 JSON 并跳过 manifest 哈希校验。

## v14.0 淡蓝色视觉校准（2026-09-01）

当前维护站已按反馈撤掉青绿色主导的视觉，统一为冷白画布、雾蓝边界、淡蓝操作色和蓝色地图热力。地图区域、顶部周期选择器、品牌标记、说明卡、检查器、城市卡和按钮均已同步；不改变任何岗位数据、城市归属或审计结论。

配色源在 `tools/anhui_web/templates/maintainable-tokens.css`、`maintainable-site.css` 和 `maintainable-site.js`，构建后由 `deliverables/maintainable/assets/` 提供。验证命令：`python -m unittest tests.test_ui_v14 -v`、`node tests/maintainable_browser_smoke.js`。

## v14.1 参考图纯蓝校准（2026-09-01）

按用户提供的参考图，将维护站主色精确收敛到明亮纯蓝 `#3A83F7`。周期选择、品牌标记、地图热力、指标数字、按钮和城市卡选中态均使用该蓝色体系；页面背景与边界使用近白和极浅蓝，去除青绿色主视觉。数据、三年周期、岗位地图几何和公开缺口口径均未改变。

源模板：`tools/anhui_web/templates/maintainable-tokens.css`、`maintainable-site.css`、`maintainable-site.js`。发布前需重建 `deliverables/maintainable/`，并执行 `python -m unittest tests.test_ui_v14 -v`、`python tools/anhui_web/verify_maintainable_site.py deliverables/maintainable` 和 `node tests/maintainable_browser_smoke.js`。
