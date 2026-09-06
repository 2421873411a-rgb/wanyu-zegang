# 皖域择岗 · 全站深度审计与升级报告（2026-09-07 · v17.9 前夜）

> 执行者：ZCode 自主审计（50 人画像 × 全视图 × 数据闭环 × 安全 × UI 五维）。
> 全部结论附证据路径（`docs/self-iterate/2026-09-07-master-audit/`）；凡"我以为"无实证者不录入。

## 〇、背景：交接包恢复（本日完成）

- 本机工作区曾被清空（仅剩 `网站/` 152MB 与 `.mimosa/`）。`皖域择岗交接包_v17.8.6+b2_含密钥_20260907.zip`（380MB/4650 文件）经 CRC 全量校验后恢复至 `E:\zcode\择岗`，4650/4650 成功。
- 恢复后基线：main=`5e1b5e8`（P1/P2 升级第一批），批次3（`774c7d5` A2收口）、批次4（`a22aa2b` A4-B1 详情瘦身）**已在历史中**（此前"挂起待 Mimosa 裁决"已落定）；工作区留有 10 处未提交修改（b2 会话的 lite 详情/校验器/测试演化）+ `_密钥_勿入git/`、a4-b1 工作目录等未跟踪文件。
- 恢复验收：verify_sources **14/14** ✓；validate_canonical **PASS**（2026 回归锁定 8511/8401/110/12006/11883 逐数吻合）✓；正式套件 222 用例 **3 失败**（见下文 D 类）。

## 一、功能审计（50 用户画像 × 全功能）

**方法**：构建 50 人画像矩阵（`personas.json`：专业×城市×学历×考试×捡漏×性别/应届/党员/法考/年龄三档×边界值 17/30/45 岁），Python 独立期望值引擎（`expect.py`，按模板语义复算）对照真实浏览器 UI 逐人实测（`actual.json`，真实 DOM 事件流注入 + 预算制批量器）。

**结论：50/50 人全部零差异**（总数 + 三级匹配 t1/t2/t3 + 竞争三档，共 350+ 数字全等）。检索/匹配引擎判定为**功能正确且确定性**。
- 审计过程自身两次误报被证伪：① req_fields"死功能"疑点→实为 harness 时序与渲染循环相撞，真实交互链路正常；② JS `??`（null 回退 bm 报名数）被我镜像成 Python `.get()+or`，修正后全绿——**站点正确，检查器错**。
- 全视图真点击走查 12 视图（总览/检索/匹配/地图/待遇/排行/趋势/日历/收藏/说明/日志/数据边界）：**零控制台错误**；详情抽屉（来源/字段/竞争/跨年走势）、收藏落库（user-store）、收藏页"我的岗位动态"跨视图联动（变更通报关联）全部正常。
- 匹配视图 h1 首屏即显示"法学 · 你的可报榜"（携带上次专业），行为符合预期。

**已实锤功能缺陷（按严重度）**：

| 编号 | 级别 | 缺陷 | 证据 |
|---|---|---|---|
| F-LOOP | **P0** | 检索页永动渲染循环：任意 change/focusout 提交后，`renderPreservingInput` 无条件 refocus 新输入框 → 旧节点卸载时 Chromium 对其派发 focusout → 150ms 定时器再渲染 → 再抢焦点，**~340ms/轮永续**（实测 432+ 次变异不停）。后果：滚动跳位、悬停丢失、输入法打断、持续 CPU/电池消耗、全页截图撕裂 | 定时器套桩栈：资产 2044 行=模板 1901 行 focusout 定时器；statlog 432 条 |
| F1 | P1 | 检索"首次输入专业+回车"降级首帧：major_index 未加载时同步渲染 substring 回退帧（法学→1,493 无三级徽标），429ms 后自愈（2,672=441/1037/1194）。本机 429ms，弱网=数秒错误结果 | f1 时序 statlog（change 后第1帧 vs 第2帧） |
| F-MAJOR-1 | P2 | 目录外专业静默降级：检索未收录专业（LAW/卫生事业管理）时 tier 走 unlimit-only 路径，显示"0 明确含/0 类内 + 不限专业 1,249"但**不出现"专业目录未收录"提示**（提示条件 `!tier && majorQuery` 写错——unlimited 恒非空致 tier 恒激活） | expect P36/P40 + 模板 hint 行 |
| F-EDU-1 | P2 | 「仅限X」学历语义倒挂：`educationAllows` 把"仅限本科"当"≤本科"，硕士/博士用户会看到 68 行仅限本科岗（另：仅限硕士研究生 9 行、仅限研究生 1 行） | expect.py 量化 78 行 |
| F-SHADOW | P2 | 渐进显现动画（is-in/REVEAL）在整页长图/慢设备上可整段空白（desktop-overview 全页截图空白实拍）；对打印/截图/SEO 不友好 | shots/desktop-overview.png |

## 二、数据完整度/科学性/闭环

- **哈希链**：site-manifest 31 模块 sha256 vs 磁盘 **31/31 全符**；`.gz` 与 `.json` 内容 **31/31 同步**。
- **canonical↔site 闭环**：canonical 2026 = 8511 raw（8401 active + 110 审计层排除）；jobs_lite 恰好 8401 行且 **job_id 集合与 canonical active 完全相等**（lite 独有 0、漂移 0）；overview meta raw_total=8511/excluded=110/recruits=11883 与 canonical metrics 全等。**数据闭环成立**。
- **科学性抽检**：req_fields 覆盖 8511 条（high 8487 / low 23 / medium 1——"待核对"徽标口径与 24 条低置信度一致）；竞争比口径 = 官方报名÷招录，边界 5:1/2:1 分类与文案一致；110 条跨市重复行仅存审计层不进用户口径 ✓；日历 5 事件（1 过期 4 未来）正常。
- **产物一致性（b2 遗留，套件 3 失败根因）**：
  - 模板≠资产：`templates/maintainable-site.js`（1a3d6b21）≠ `网站/assets/maintainable-site.js`（43255916）——b2 改了模板没重建；
  - **major_city 溯源哈希三周期全部陈旧**（2024/2025/2026 的 source_sha256 均≠当前 jobs_lite 哈希；套件只测出 2024，实际三周期同病）；
  - 磁盘校验器对账 fail 与上同源。
  - **判定：同一类病根 = b2 未完成的重建态。修复 = 一次 canonical 全链重建（不手补哈希）**。

## 三、代码安全

- **XSS**：模板+v17-tools 全部插值经 escapeHtml/number 过滤，逐点核查 5 处可疑插值均为数字坐标（SVG viewBox），**无注入矢量**；无 eval/new Function/document.write/outerHTML。
- **密钥**：`_密钥_勿入git/wanyu111_fixed.pem` 已被 .gitignore 正确覆盖（git check-ignore ✓）；git 跟踪文件无敏感项。
- **供应链**：index.html 无第三方外链（仅自身域名）；无 CDN 依赖。
- **加固空间**：无 Content-Security-Policy（静态站纵深防御建议加 meta CSP）；service worker 为唯一大权限面（版本 wanyu-shell-v49，随发布同步升级）。
- **环境限制**：Mimosa 深扫 worker 未构建（"请重新运行 build:mcp / sync:zcode"），本轮以人工审计替代；提交门禁如拦截按既有经验走扫描裁决。

## 四、UI/排版/动效

- 结构层（a11y 树逐视图走查）：语义地标完整（banner/nav/main/complementary/status）、跳转链接、aria-label 齐备；暗色主题切换正常（data-theme）。
- 视觉层（22 张截图存证 shots/，桌面 1440 亮/暗 + 移动 390 + 抽屉）：亮色视觉层级清晰、数字信息密度合理；上述 F-LOOP 引发的页面抖动是最大体验杀手；F-SHADOW 长页空白风险次之。
- 既有 b857bec4（UI审计修复：触摸目标/暗色/CSS 变量）已覆盖上轮问题，本轮无新增重大视觉缺陷。

## 五、前景判断（v17.9~v18 展望）

1. **信任资产是核心壁垒**：canonical 真源+锁校验+发布 manifest 的可复核链在同类产品中稀缺，应持续加厚（自动化 CI 复核、公开审计页）。
2. **数据运营 rhythms**：2026 岗位表官方补录/更正会再来，需要"fetch_sources 自动拉源 + diff 审计"管线（升级规划已列）降低人工成本。
3. **匹配引擎护城河**：三级专业匹配已是全站正确性基石，下一步可做"专业→课程→岗位能力"语义层（目录外专业的模糊兜底）。
4. **FastAPI 动态化**（动态网站改造方案已立项）：仅做只读 API + 缓存，静态产物仍为真源，避免双真源。
5. **部署是站长动作**：wan.kaogong.art 仍未上线 v17.8.6+，nginx 开 gzip_static；本 v17.9 发布后应一并部署。

## 六、修复计划（P7，自主执行中）

| 项 | 修复 | 验证 |
|---|---|---|
| F-LOOP | `renderPreservingInput` 仅当原输入框本持焦点才 refocus；focusout 对已断连节点跳过 | 复测 statlog 静置零增长 |
| F1 | jobs_search 分支：searchMajor 非空时 `await loadModule(major_index)` 再渲染（保留 catch 回退） | change 首帧即含三级徽标 |
| F-MAJOR-1 | 提示条件改为 `majorQuery && !(tier && (explicit\|byClass 命中))` | LAW/卫生事业管理 出现"未收录"提示 |
| F-EDU-1 | `educationAllows`：xl 含「仅限」→ 要求学历档位相等 | 博士+法学 不再出现仅限本科岗；期望器同步更新后 50 人复测 |
| CSP | index.html 模板加 meta CSP（default-src 'self'; img 'self' data:; style 'self' 'unsafe-inline'） | 页面功能回归 + 烟测 |
| 产物 | 全链重建（clean_rebuild 门禁）→ 资产一致 + major_city 三周期重绑 | 套件 222/0/0 |
| 发布 | release.json → v17.9.0 / wanyu-shell-v50；npm i playwright-core + chromium；release.py 正式发布 | RELEASE-EXIT=0 + 三烟测 |
| 提交 | 分层：fix(检索渲染)/fix(学历语义)/chore(CSP)/build(重建产物)/release | git log 分层可溯 |

—— 本报告与全部证据（personas/expected/actual/对比脚本/截图/探针日志）存档于 `docs/self-iterate/2026-09-07-master-audit/`。
