# 皖域择岗档案 · v16.0 离线缓存与数据工作台交接入口

最终交接包以 `deliverables/HANDOFF.md`、`deliverables/皖域择岗总览.html` 和 `deliverables/maintainable/` 为准。

## v16.2 升级摘要(2026-09-03,动效深化)

- **显现系统对齐参考站节奏**:新令牌 `--dur-reveal 780ms/--dur-reveal-x 920ms/--ease-pop`;区块位移+微缩放进场,双列网格左右对开(±12px 不扩展横向滚动区),hero 子元素交错(0/70/140/200ms),bento/KPI/变化卡/指南/CTA 阶梯交错。
- **数据生长动效(终值=真实数据)**:占比条 scaleX 生长、mixbar 分段依次、sparkline 描线(pathLength)、地图区域按既有 `--map-delay` 交错淡入、奖牌 pop、delta 滑入。
- **浮层与微交互**:抽屉/命令面板入场动画(0.38s pop)、CTA 圆环呼吸+指针辉光+箭头位移、页头滚动进度线、卡片 hover 抬升。
- 全部初始态 scoped `.reveal-ready`,reduced-motion 直出终态;计划文档见 `docs/plans/2026-09-03-v16.2-motion-upgrade.md`,并已随交接包分发。
- 验收:磁盘校验 217/0;ui 门禁 18/18;全量发布链 0 失败;Chrome 走查(中间帧/终值/reduced-motion/390px/控制台 0)见 `tests/artifacts/v16.2/`;已上线 wan.kaogong.art(sw `wanyu-shell-v3`)。

## v16.1 升级摘要(2026-09-02,视觉节奏)

- **学参考站手法、主色不变**:首屏标题紧排(-.05em、上限 58px);9 视图 eyebrow 编号化(`01 / CYCLE OVERVIEW`…`09 / RELEASE NOTES`);页尾新增满幅深色 CTA 带(三年合计由构建现算注入,无外链,打印隐藏)。
- **动效层(尊重 reduced-motion)**:滚动渐显(html.reveal-ready 由 JS 按能力添加,不加类即全可见)、bento/审计 KPI count-up(`data-countup`,终值字节级等于真实数据)、总览证据卡指针 3D 倾斜(pointer:fine 限定)。
- **令牌与门禁**:新增 `--band-*` 成对令牌(两主题 6 位 hex),band 对比度 ≥4.5 进 `test_ui_v15` 数学回归;版本 v16.1,sw 缓存升 `wanyu-shell-v2`,release.py BUILD_VERSION 同步。
- 验收:磁盘校验 217/0;ui_v14+ui_v15 14/14;maintainable_site+release_v14+ui_v13 19/19;Node 契约全绿;本机无 bundled Chromium(下载 CDN 不通),按 v14.4 惯例以系统 Chrome 走查补偿:总览/榜单/地图(16 区域)/检索(60 行)/审计(3+8)全视图断言 + 双主题与 390px 无溢出截图,控制台 0 报错,证据在 `tests/artifacts/v16.1/`(脚本 `tests/artifacts/v16_1_walkthrough.cjs`)。

## v16.0 升级摘要(2026-09-02,M1–M3)

- **PWA 离线缓存(F10)**:`sw.js` 数据 network-first/离线回退、资产 cache-first 后台刷新;DataStore SHA-256 校验不变,缓存不伪装新数据;离线时页头「离线缓存」徽标;manifest.webmanifest + SVG 图标可安装。
- **工作台**:收藏/快照/对比一键导出导入(带版本校验与容量上限,坏文件报错不落盘);帮助页六步「数据更新清单」(勾选持久化 + 命令复制)。
- **单文件定位(D5 方案 A)**:`皖域择岗总览.html` 定位为数据归档快照,顶部提示条引导维护站入口,视觉冻结、数据仍随发布链更新。
- 验收:磁盘校验 217/0;发布链 20 模块 170/170;浏览器实测 SW 接管+缓存可解析+工作台往返一致,控制台 0 报错。

## v15.1 升级摘要(2026-09-02)

- jobs_lite 轻索引(43%):检索/榜单/地图/收藏走轻索引,jobs.json 按需;骨架加载态;test_anhui_web 清债入门禁(20 模块 170 用例);导航换行/skip-link/aria-live。

## v15.0 升级摘要(2026-09-02,M0–M5)

- **双主题**:浅色工作台(默认)/ 深色观测台(`?theme=dark`、header 切换按钮、localStorage `wanyu.v15.theme`、跟随系统);Design Token v3 全量成对变量,组件禁硬编码主题色(契约测试断言 + WCAG AA 对比度计算)。
- **数据模块新增**:`derived.json`(环比/考试构成/三年城市趋势/未归并城市/复核进度)与 `palette.json`(命令面板索引);磁盘校验从 142 扩至 **185 项**,含派生数学交叉门禁(vs_prev==manifest 差、mix/趋势合计==岗位数、palette ID 可对回 jobs)。
- **视图升级**:总览 bento(渐变大数字+环比徽标+构成条+证据卡,城市行三年 sparkline);地图暗色热力(`--map-stop-0..5`)+ 城市卡均值分层;榜单前3徽标+招录占比条+竞争观测覆盖率列(未观测显示"— 未观测"不推断);三年对照坡度图;对比差异表(≠ 标记+琥珀高亮+导出)。
- **效率**:Ctrl+K / `/` 命令面板(视图/主题/周期/岗位本地匹配,↑↓ Enter Esc);`#job/<稳定ID>` 分享链接;检索密度切换;打印样式。
- **红线未动**:岗位原文不改、未知不以 0 代替、离线单文件无远程资源、<80MiB。
- 验收证据:`verify_maintainable_site.py` 185/185;`test_ui_v14+test_ui_v15` 11/11;`test_maintainable_site` 8/8;内置浏览器双主题走查 0 console 报错(截图 `tests/artifacts/v15-m*.png`);浏览器证据采用内置浏览器(bundled Chromium 未安装,沿用 v14.4 惯例)。
- 已知问题（v15.1 M-B 已解决）:`tests/test_anhui_web.py` 的 8 个 v9/v10 过期契约已对齐或删除,页面构建全部改为沙箱目录,不再触碰 `deliverables/`;该模块已纳入发布门禁链(48 用例)。
- 计划与决策:`docs/plans/2026-09-02-v15-design-and-feature-upgrade.md`。

- 离线快照入口：`deliverables/皖域择岗总览.html`
- 长期维护入口：`deliverables/maintainable/index.html`（先运行 `python tools/anhui_web/serve_maintainable.py --port 8765`）
- 维护数据模块：`deliverables/maintainable/data/cycles/<cycle>/{overview.json,jobs.json,audit.json}`；三年审计索引：`deliverables/maintainable/data/audit/three-year.json`
- 维护站“数据审计”集中展示三年证据等级、公开缺口和成绩待复核量；岗位榜单支持可读专业关键词、城市、考试、岗位类型组合筛选。
- 三年切换：网页顶部选择 2024、2025、2026
- 离线打开：双击 HTML，不需要服务器或联网
- 详细数据边界、验收命令和已知缺口：见 `deliverables/HANDOFF.md`
- 数据字典：`docs/数据字典.md`；三年审计：`docs/三年数据真实性与完整性审计_v12.md`
- 交接压缩包：运行 `python tools/anhui_web/release.py --skip-tests --zip`，输出到当前用户 Desktop
- 旧分拆页：`deliverables/legacy_v11/`，仅作可恢复归档
- 历史交接物归档：`archive/`（v10 计划任务、v12.1 总包交接文档、v14.4 交接包副本）；正式入口仍以下述 deliverables 为准
- 本轮视觉层：`tools/anhui_web/templates/maintainable-site.css` 与 `maintainable-tokens.css`；当前为参考图方向的冷白淡蓝工作台，专业候选不再展示纯数字/纯编码值
- 长期维护架构：`docs/长期维护网站架构方案_v1.md`；外置数据构建器：`tools/anhui_web/build_maintainable_site.py`
- v14.4 走查报告：`tests/artifacts/audit-20260901/REPORT.md`；内置浏览器最终走查 22/22，维护站自动烟测通过，磁盘校验 142/142。
