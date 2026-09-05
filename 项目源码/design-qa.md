# 皖域择岗档案 · v6 设计 QA

## v6 综合总览对照输入与截图

- 参考输入：design_refs/jobs-workbench-desktop.png、design_refs/jobs-mobile.png；它们作为原有浅色数据工作台的结构基线。
- v6 实现输入：tests/artifacts/master-v6-desktop-overview.png、master-v6-desktop-profile.png、master-v6-mobile-overview.png、master-v6-mobile-profile.png。
- 合并对照图：tests/artifacts/master-v6-reference-comparison.png，将参考输入与 v6 桌面 / 移动画像截图放在同一比较输入中。
- 同一 comparison input 的并排判断：桌面参考对应桌面总览 / 城市画像，移动参考对应移动总览 / 城市画像；重点检查留白、层级、信息密度、控件可触达性与地图标签拥挤。
- 当前状态：`全部类别 · 公务员 · 3年 · 合肥`；另复核了 `省考 · 事业编 · 5年 · 芜湖` 和 `六安` 城市短名单闭环。
- 桌面 CSS 视口：1280 × 720；普通页面截图栅格为 1265 × 712，差异来自垂直滚动条；城市画像裁剪图为 1280 × 720。
- 移动 CSS 视口：390 × 844；完整长图栅格为 375px 宽，城市画像裁剪图为 390 × 844。

| 参考输入 | v6 当前实现 |
| --- | --- |
| design_refs/jobs-workbench-desktop.png | tests/artifacts/master-v6-desktop-overview.png + master-v6-desktop-profile.png |
| design_refs/jobs-mobile.png | tests/artifacts/master-v6-mobile-overview.png + master-v6-mobile-profile.png |

v6 通过上述同一组桌面 / 移动对照输入完成视觉复核：保留真实地图与证据表格的产品属性，重排为浅色“数据编辑室”，并把城市选择、待遇阶段和岗位类别放进同一决策闭环。

## v5 历史基线与回归输入

- 岗位设计基线：design_refs/jobs-workbench-desktop.png、jobs-ranking-compare.png、jobs-search-compare.png、jobs-mobile.png、jobs-motion-board.png。
- v4 基线截图：tests/artifacts/jobs-v4-desktop-hero.png、jobs-v4-desktop-workbench.png、jobs-v4-ranking-desktop.png、jobs-v4-archive-desktop.png、jobs-v4-mobile-hero.png、jobs-v4-mobile-workbench.png；待遇对应截图也保留作回归基线。
- v5 历史实现截图：tests/artifacts/jobs-v5-desktop-dashboard.png、jobs-v5-desktop-decision.png、jobs-v5-mobile-drawer.png、salary-v5-desktop-dashboard.png、salary-v5-mobile-drawer.png。
- 对照状态：岗位默认“岗位数 / 全部 / 合肥”；待遇默认“公务员 / 3年 / 合肥”。另复核了岗位“事业单位 + 自定义权重”和待遇点击“芜湖”后的移动详情抽屉。
- 桌面 CSS 视口：1280 × 720；Codex in-app Browser 截图栅格为 1265 × 720，差异来自页面垂直滚动条占用的内容宽度。
- 移动 CSS 视口：390 × 844；截图栅格为 375 × 812，差异来自浏览器视觉视口和滚动条占用。

下面的表格就是本轮用于并排判断的同一份 comparison input：左侧为源参考，右侧为当前实现。

| 参考输入 | 当前实现 |
| --- | --- |
| design_refs/jobs-workbench-desktop.png | tests/artifacts/jobs-v5-desktop-dashboard.png + jobs-v5-desktop-decision.png |
| design_refs/jobs-mobile.png | tests/artifacts/jobs-v5-mobile-hero.png + jobs-v5-mobile-drawer.png |
| design_refs/jobs-ranking-compare.png | tests/artifacts/jobs-v4-ranking-desktop.png |
| design_refs/jobs-search-compare.png | 岗位检索视图与 544 条源记录的运行态检查 |
| 既有待遇桌面基线 | tests/artifacts/salary-v5-desktop-dashboard.png |
| 既有待遇移动基线 | tests/artifacts/salary-v5-mobile-drawer.png |

## 本轮视觉与交互结果

- 全站改为浅色纸张 / 雾蓝研究台方向：深靛标题、蓝色主操作、青色和琥珀色数据标记，保留研究档案感但不再使用压迫性的深色满屏背景。
- 顶部壳层加入品牌标记、当前视图、离线数据状态、纸张底色开关、打印入口和阅读进度线；移动端导航可横向滑动但隐藏原生滚动条。
- 首屏采用“叙事标题 → 数据更新卡 → 指标摘要 → 控制台 / 地图 / 城市检查器”的节奏，地图工作台成为视觉主角，卡片边界、网格和标签层级统一。
- 地图使用项目内真实安徽 16 市 GeoJSON 路径；指标切换使用平滑色彩过渡，城市点击同步地图高亮、检查器、LIVE FACTS 和 URL 状态，城市悬浮 / 聚焦会显示轻量事实提示。
- 岗位排名、待遇排名、岗位检索、岗位对比、我的岗位和档案章节均沿用同一壳层；排名区增加事实摘要和对比台，档案区改为目录索引 + 原表折叠，避免一进入页面就被长表淹没。
- 移动端指标与考试 / 工龄控件压缩为可触控的紧凑横向组，地图外层取消默认 figure 外边距；390px 视口下页面无横向溢出，地图工作台提前进入阅读路径。
- 入场、地图描边、数字与检查器状态切换均为克制动效，并保留 prefers-reduced-motion 分支；不新增远程图片、字体或脚本资源。

## v5 决策体验复核

- 岗位观测台新增“决策驾驶舱”：三档策略（稳妥 / 平衡 / 机会优先）和岗位规模、招录人数、低竞争三个可调权重，均在浏览器本地计算。
- 推荐结果使用当前考试类别下的 16 城聚合值，给出前三城市、综合得分、关键事实与“为什么在前面”的解释，不伪装成录用预测。
- 点击推荐卡会反选地图、同步城市检查器、LIVE FACTS 和 URL；切换“事业单位”等考试类别后，推荐列表与解释文案重算。
- 岗位与待遇移动端均将城市检查器改为按需弹出的底部抽屉；支持关闭按钮与 Escape 关闭，避免小屏首屏被侧栏占满。

## 交互验收

- 岗位：选择“事业单位”后决策上下文变为“事业单位 · 16 座城市”；切换“稳妥”会写入 20 / 25 / 55 权重，拖动任一滑杆后显示“自定义参考”，点击推荐卡会打开当前城市检查器。
- 待遇：点击地图命中区“芜湖”后检查器为“芜湖市”，值为 14.4，移动端出现 is-mobile-open 抽屉；城市下拉、地图命中区和 Escape / 关闭按钮均可进入或退出城市状态。
- 排名：16 城表格、城市对比台、指标 / 身份 / 工龄切换均存在且可操作；无选择时显示引导态，有选择后显示事实对比。
- 检索与收藏：544 条记录可检索；收藏和岗位对比使用稳定 ID 与本地存储，刷新后可恢复，导出使用固定字段顺序和 UTF-8 BOM。
- 档案：岗位 106 张源表、待遇 31 张源表均保留；目录跳转、关键词过滤、折叠 / 全部展开可用，关闭 JavaScript 后仍可阅读源内容。

## 比较历史与修复记录

- P2：移动端地图 figure 默认左右外边距使地图实际宽度只有约 241px；已修复为 map-panel margin 0，390px 视口下地图面板 351px、地图舞台 321px。
- P2：移动端顶部导航曾露出浏览器原生横向滚动条；已加入 Chromium WebKit 与 Firefox 的隐藏滚动条规则，同时保留横向触控滑动。
- P3：移动端控制台纵向过高，地图被推得太远；已将指标、考试类别和工龄控件改为紧凑横向布局。
- P2：移动端检查器常驻侧栏会压缩地图阅读宽度；v5 改为点击城市后弹出的底部抽屉，并保留关闭与键盘 Escape 退出。
- P3：推荐状态如果只给分数会缺乏判断依据；v5 在前三城市卡片与 TOP MATCH 区域同时展示岗位、招录、竞争比和权重解释。
- 当前复核：无 P0 / P1 / P2 未解决问题。极窄屏下 16 市轮廓和标签会自然缩小，这是全局地图可读性与完整性的必要取舍，详细数值仍在检查器、排名和源表中可访问。

## 逐面视觉检查

- Typography：中文标题、英文小标签、数字指标和表格正文形成稳定的四级层次；数字使用等宽数字，避免跳动。
- Spacing / layout：桌面为 12 栏研究台骨架，移动为单列节奏；面板内边距、分割线、标题与控件间距一致。
- Color / tokens：纸白卡面、雾蓝背景、深靛文字和蓝 / 青 / 琥珀数据色均由共享 token 控制，纸张模式可切换。
- Asset fidelity：地图使用项目内真实边界数据；没有用 CSS 图形、占位图片或外部素材伪造可见内容。
- Copy / content：保留源文档事实、年份和估算口径，新增说明明确“源文档”“岗位数 / 招录人数”“招录 / 考生”，不把估算改写成政策承诺。

## 自动化与浏览器证据

- python -m unittest tests.test_anhui_web -v：16 / 16 通过，覆盖源文档计数、544 条岗位、825 条招录、16 城、106 / 31 张表、档案索引、URL 白名单、CSV 安全和离线约束；v6 额外核对 3 个 HTML 输出、综合入口视图清单和 137 张合并档案表。
- Codex in-app Browser：桌面 1280 × 720、移动 390 × 844 均无页面级横向溢出；v6 综合矩阵渲染 16 个城市点位，岗位 / 待遇各有 16 条真实地图路径；统一筛选、城市画像、短名单、岗位 / 待遇跨视图跳转和档案页签通过，干净会话读取的 console error / warning 均为空。
- 系统 node tests/browser_smoke.js 已尝试；系统 Node 无 playwright，工作区 bundled Playwright 包可解析但 Chromium headless 可执行文件未安装，因此 CLI 烟测无法启动。未擅自下载或安装浏览器；本轮以 in-app Browser 的真实页面验收作为浏览器证据。
- 静态检查：最终 HTML 不加载远程 JS / CSS / 字体；地图数据来自 tools/anhui_web/data/anhui_340000_full.json。

## v6 视觉判断与修复

- 视觉从 v5 的单产品观测台扩展为“浅色数据编辑室”：综合总览使用叙事标题、全局筛选、四项 KPI、双轴矩阵和右侧城市画像，第一屏不再把岗位和待遇拆成两个互不相干的世界。
- 矩阵第一次视觉复核发现 16 个城市标签在低机会区域聚集；已改为默认显示活跃城市 / 前三相对位置城市标签，其余点位仍保留按钮、标题和 `aria-label`，悬停或聚焦时显示标签。
- 跨视图第一次交互复核发现 SVG 节点没有原生 `.click()` 方法；已使用兼容 SVG 的事件触发方式，随后干净会话复测岗位 / 待遇状态同步和日志均通过。
- 移动端遵循单列阅读路径，矩阵与画像上下衔接，短名单和操作按钮保持可触控尺寸；390px 页面级 `scrollWidth - clientWidth = 0`。

## 结论

本轮完成的是全站 v6 综合决策入口升级：岗位与待遇合并到一张可交互的城市决策桌，旧岗位 / 待遇页面保留为兼容入口，源数据、真实地图路径、档案全文和离线交付边界均未改动。

final result: passed

## 2026-08-28 v7 定向岗核除验收

- 输入：本轮重建后的三个交付 HTML（deliverables/），Chrome 无头截图，视口 1440×900 与 390×844，prefers-reduced-motion。
- 截图：tests/artifacts/v7-master-overview-desktop.png、v7-jobs-observatory-desktop.png、v7-jobs-search-desktop.png、v7-jobs-search-mobile.png、v7-jobs-archive-note.png、v7-jobs-archive-badge.png、v7-jobs-exammix-desktop.png。
- 结论（评审代理逐图判定）：总览 KPI 500 岗 / 779 人达成；观测台考试类别卡 省考 406/678 · 事业单位 91/98 · 国考 3/3 与 KPI 自洽；检索页计数 500；档案"定向岗核除说明"折叠框含分市代码与 0801048 待复核提示；滁州表 0801031 / 0801046 / 0801048 行带红色"定向·不可报"徽标并置灰；移动端 390×844 页面 scrollWidth=390，无页面级横向溢出，宽表新增"左右滑动查看全部数据列"提示条。全部验收项通过，无遗留问题。

## 2026-08-28 v8 增强层验收

- 截图：tests/artifacts/v8-sim-desktop.png、v8-profile-panel.png、v8-search-mobile.png、v8-growth-scatter.png。
- 评审代理判定：分数模拟视图、我的条件浮层、移动端检索（scrollWidth=390）三项通过；散点图首轮不通过（标签重叠/点色未编码/参考线未绘制/标题被导航裁切），修复（13px 防重叠下移、增速中位数分色、虚线内联绘制、scroll-margin-top:96px）后复验。
- 程序化验证：命令面板搜索 0801 返回岗位匹配并可跳转；画像勾选退役士兵后 15 条退役定向岗恢复并标绿（500→515）；标签筛选"仅应届"112 条可逆；分数模拟 事业编215→稳35/达线15/贴线16，240→稳105；省考切换默认分重置 70。
- 散点图第二轮（碰撞检测贪心布局，720×380，放不下的标签省略并以悬停 title 兜底）经评审代理复验通过。v8 全部验收项闭环。
- v8.1 全视图审计：3 文件 × 11 视图 × 桌面/移动共 40 项检查（标记元素/横向溢出/console 错误）全部通过；分数模拟“范围”控件上移至顶部控制区（全省（16 市）/分城市），移动端直方图改容器内滑动，sim-row 网格允许收缩，城市以蓝色徽标标注在岗位名前。
