# 皖域择岗交付更新日志

## v17.9.13 · Round-3 复审收口（回归对抗抓出转义缺陷实现 + 运维窗口）· 2026-09-08

### P1
- **LIKE 转义缺陷实现修复**：v17.9.12 的 _escape_like 替换模板经多层转写损坏为"反斜杠+SOH 控制字符"——含 %/_ 字面量的关键词/专业搜索恒为空且向 SQL 参数注入控制字节；三个独立审计镜头交叉确认。改为 lambda 构造替换（chr(92)），转义集补反斜杠，新增"字面量仍可命中"正向门禁（旧门禁只测 total==0 挡不住此类回归）。
- **deploy.sh 首次部署必失败修复**：强制的 pg_dump 重定向到从未创建的 /opt/wanyu/backup（首装分支不建目录）——无条件 mkdir。

### P2
- SECRET_KEY：公开测试密钥入 denylist（正式环境拒启）；ENV 精确匹配 test（' TEST '/'Test' 不再享受豁免）
- LIKE：反斜杠纳入转义类（生产 PG invalid escape 500 面）
- 限流：Redis Lua 改用 Redis TIME（实例时钟漂移曾整体绕过窗口）；内存 limiter 容量上限+清扫（20 万 key≈150MB 内存 DoS 面）；reset() 非 test 环境拒绝执行（防误扫共享 Redis）
- 部署：停服窗口（旧 worker 滚动重生撞新代码曾致崩溃循环）；OS 支持矩阵前置断言（python3.12 仅 24.04+ 官方源）
- 数据：快照"在场排除行"也级联清理幽灵引用；MirrorState.release 空 label 守卫（与 Cycle.label 一致）；bm 浮点校验（契约对齐）；stats 缓存查询移入命中路径+导入失效钩子（原实现零收益纯脏读）
- 文档：版本真源路径统一（CONTRACT/RUNBOOK/.env.example→wan-api/release.json）；README 快速开始补 SECRET_KEY 步骤+端点表按 OpenAPI 重生成+定位语改为"为未来动态站预建"；RUNBOOK pg_restore 补提权；交接包 txt 加时点声明；CONTRACT 措辞精度（|| true 豁免、bm/级联表述）


## v17.9.12 · Round-2 深度收口（认证安全 + API 行为 + 运维可观测）· 2026-09-08

### P0
- 用户筛选快照端点（/api/v1/user/snapshots）修复：filters JSON 序列化成对处理——此前 POST/GET 双向 100% 500 且前端静默吞错；新增 ≤32KB/50 份防滥用上限与 CRUD 门禁测试。

### P1 ×8
- 登录限流原子化（check-then-hit 竞态封死：修复前 20 并发错密码 20/20 穿透，现 ≤5 过其余 429）
- 限流 Redis 后端（Lua 原子滑动窗 + 锁定键，多 worker 安全；不可达时 fail-open 到收紧的进程内兜底；CI postgres job 挂 redis:7 实测）
- SECRET_KEY 全面收紧（无默认值：正式环境缺失/公开默认值/<32 字符一律拒启）
- pg_dump 强制化（迁移前自动快照+非空校验+保留 10 份）
- .env APP_VERSION 每次部署强制刷新（旧值曾使二次部署 smoke 必败）
- app 级审计日志落地（logging 显式配置 + gunicorn capture_output；admin 导入/登录失败/限流命中进日志）
- /health readiness 语义（含 DB SELECT 1，宕机 503）
- 搜索性能：GIN trgm 索引（unit/zw/zy/code，pg_trgm 终于用上；此前 keyword 全表扫 168-294ms 实测）+ (record_status,num DESC) 复合索引（sort=recruits 深翻页 371ms→索引化）+ page 上限

### P2/P3 簇
- refresh 轮换乐观锁（UPDATE rowcount 判定，SQLite 不再双花，任何后端语义一致）
- LIKE 通配符转义（%%/_ 语义漏洞）+ 控制字符/NUL 422
- 迁移 0004：record_status 回填+server_default（0002 无回填窗口封死）
- init_db alembic_version 多行拒启（曾 fail-open 且结果取决于物理行序）
- 最后管理员保护加 advisory lock 串行化（并发互降清零窗口）
- salary 零值不再被 falsy 吞成 null（回归"零不冒充未知"数据原则）
- schema 长度上限对齐列宽（SQLite 测不出、PG 会 500 的方言漂移类）
- RecursionError/UnicodeDecodeError 统一 400；CompareListCreate 移除误导性 position 字段
- email 注册/登录统一小写归一
- stats 端点 60s TTL 缓存（~90ms/次的无效全表聚合）
- deploy.sh：nginx client_max_body_size 64m（默认 1MB 曾挡死 12MB 真实快照导入）、
  logrotate、redis Requires→Wants、forwarded_allow_ips 显式化
- RUNBOOK 回滚顺序修正（先 downgrade 后回滚代码——原顺序在迁移不兼容时必然失败）
- dev lock 补 uvloop（CI/生产事件循环一致）；runtime lock uvloop marker 对齐上游
- api-data-store.js 幻端点标注 DEPRECATED（真实消费面=静态 JSON）


## v17.9.11 · Round-1 深度收口（部署链 + 数据完整性 + CI 门禁 + 版本真源）· 2026-09-07

### 部署链（Round-1 审计 P0×1 / P1×2 全部关闭）

- **P0**：`/var/log/wanyu` 从未 chown 给 www-data，全新机器首次部署必死于 gunicorn 启动——现部署即 `chown www-data:750`；权限扫除改为 venv 创建前执行，废除 `|| true` 兜底。
- **P1**：DB owner 校验调用了不存在的 `pg_get_userby`（正确为 `pg_get_userbyid`），任何二次部署必炸——已修复并进 linkage 回归锁。
- **P1**：nginx `alias+try_files`（trac#97 双前缀缺陷）改为 `root /opt/wanyu/static`；smoke 新增静态站 200 与 HTTP→HTTPS 301 断言；certbot 加 `--redirect`。
- 部署载荷改确定性打包（定位脚本目录 + tar 排除清单）；换血前自动备份旧版本（`/opt/wanyu/backup/`）+ alembic 版本戳 + `docs/ops/RUNBOOK.md` 回滚手册；`create_admin` 可经 `ADMIN_BOOTSTRAP_PASSWORD` 入链；apt 补 curl/sudo + 前置断言。

### 数据完整性（P1×3 关闭 + 一批 P2）

- canonical bundle 必须携带 `provenance.job_id_set_sha256`（删除指纹段绕过校验的 fail-open 已封死）。
- 复核事件导入幂等化（`kind+cycle+title` upsert）：此前每次重部署 review 队列翻倍（7→14→…）。
- 收藏/对比 add 时校验引用目标为当前 active 岗位；快照下线行级联清理幽灵引用并留下"为何/何证/何时"三件套（新增 jobs 三列，迁移 0003）。
- meta 口径必须成对匹配（raw 对 raw、active 对 active，混搭拒绝）；浮点 `num` 拒绝；契约排除词表（withdrawn/superseded/invalid_source/needs_review）与 API 白名单对齐（DB 折叠二值）；`Cycle.snapshot_date` 结构化回填；dashboard active/excluded 双口径；导入响应携带全周期 mirror 摘要。

### CI 门禁与版本真源

- canonical required check 从 5 个白名单模块扩为 discovery 全量（产物依赖 10 模块显式豁免并注明理由）+ 4 个 .cjs 纯函数模块 node --test；真数据端到端（6 快照校验→临时库导入→幂等对账）与 dev-lock pip-audit 进 CI；concurrency 对 main 免取消。
- API 版本单一真源 `wan-api/release.json`（wanyu-api-release/v1）：config 启动读取、deploy 注入、`/health` 暴露、smoke 断言——v17.9.1~v17.9.10 十个版本"线上到底是哪个版本"不可回答的问题闭环。
- 契约/README/record-status 文档与实现对齐；僵尸文件清除；`.gitignore` 正式收编 deliverables/。


## v16.2.1 增量 · 岗位地图专业筛选 + 地图交互即时化 · 2026-09-03

### 岗位地图可按专业看分布

- 「岗位地图」新增**专业关键词筛选**：输入框 + 常用专业快捷标签（按岗位命中数排序），输入即实时重绘十六市热力与标签、城市检查器、十六市卡片与「已定位 X / Y 行」——命中口径复用岗位表专业原文 + 可读专业词（`majorHit`），不改任何岗位原文。
- 专业筛选生效时，**「待遇」按钮自动禁用并说明原因**（待遇是地市级估算口径，无法按专业拆分，避免用错分母误读）；从地图「在岗位检索中查看该市」会把当前专业带入检索。
- 地图指标/身份/工龄/城市/专业等**交互全部改为就地即时渲染**（不重播入场动画），消除点击后的整页闪白与动画重放造成的“卡一下”。
- SW 缓存 `wanyu-shell-v11`。
- 新增 `tests/test_v17_salary_and_motion.test_jobs_map_major_filter` 钉住上述不变量；磁盘校验仍 **223 passed / 0 失败**，性能预算 34 项 0 超（合计 ≈15.1MB gzip）。
- 实测：本地输入“法学”命中 1,504 / 8,511 行、焦点与输入值保持、零控制台报错、清除后回全量 610 岗（合肥）。

> 关于“是否改用 SQL”：不建议。维护站的硬约束是**离线可用、无远程资源、每个数字可回到本地源包按 SHA-256 复核**；SQL 需要常驻后端与在线查询，会破坏离线单文件形态与可复核契约。地图“卡”的主因是**整周期 jobs_lite 首次加载**（≈540KB gzip）与**整页动画重放**，前者已由 QW Pages 边缘节点与 SW 缓存缓解、后者本次已消除。若要进一步把地图首屏做到亚百 KB，可加一层构建期预计算的「专业×城市」聚合索引（仍为静态 JSON），无需引入数据库。

## v16.2.1 增量 · 待遇地图回归 + v17 首波 · 2026-09-03

### 待遇地图回归维护站（原本只在离线单文件线）

- 新增**顶层全局数据模块** `data/salary/anhui.json`（`build_maintainable_site._salary_payload`，读 `source_docs` 全包分析 Word，16 市 × 公务员/事业编 × 5 档工龄，单位万元/年；作为全局模块不进 per-cycle，避免破坏模块集合等值门禁）。
- 新增**独立「待遇地图」视图 `salary_map`**：十六市热力（复用真实 GeoJSON 几何与 `--map-stop-*` 色阶）、身份/工龄子切换、城市检查器、十六市待遇排行、**工龄梯度曲线**（真实值，缺值不补 0）。
- 「岗位地图」同步支持「待遇」作为第三指标切换（岗位数/招录人数/待遇）。
- SW 缓存 `wanyu-shell-v7`（强制换壳，规避旧缓存导致新视图不加载）。

### 数据红线

- 待遇为 **2026 快照全包估算中位数**，页面明示非官方逐岗工资、不代表 2024/2025、省直不纳入；缺失显示“未取得/—”，绝不以 0 冒充。岗位原文与三年审计口径零改动。

### 质量门禁与运维（v17 计划首波）

- 新增 `tools/anhui_web/perf_budget.py`（各模块 gzip 体积棘轮门禁，当前 34 项 0 超，合计 ≈15.1MB）并接入 `release.py` 构建链。
- 新增 `tests/test_v17_salary_and_motion.py`（待遇视图/曲线/动效降级/无远程资源/门禁接线契约），并入 `release.py` 测试列表。
- 磁盘校验由 217 → **223 passed / 0 failed**。
- 部署工具（未自动执行）：`tools/anhui_web/deploy_wan.sh`（默认 dry-run、缺私钥安全中止、可选 APPLY_NGINX）+ `docs/ops/wan-kaogong-perf.conf`（brotli/HTTP2/分类型 Cache-Control）+ `docs/ops/README.md`。
- QW Pages 预览已发布：https://nu9ub6tc.qwenwork.host （完整三年版）。

## v16.2 · 动效深化 · 2026-09-03

### 显现系统（对齐参考站节奏，手法而非配色）

- 新动效令牌：`--dur-reveal 780ms` / `--dur-reveal-x 920ms`（opacity/transform 双时长，参考站同款节奏）、`--ease-pop cubic-bezier(.16,1,.3,1)`。
- 区块显现升级为位移+微缩放（translateY(16px)+scale(.985)→原位）；双列网格方向变体（左列 left / 右列 right，±12px 保证任何宽度不扩展横向滚动区）；hero 子元素交错入场（eyebrow→h1→lede→stamp，0/70/140/200ms）。
- 结构化交错（纯 CSS nth 阶梯）：bento 4 格、审计 KPI 4 卡、变化卡、指南 3 步、CTA 内层 3 行；60 行检索表格不做逐行动画。

### 数据生长动效（终值=真实数据）

- 占比条 scaleX(0→1) 生长（城市分布 8 行阶梯、榜单数字条、mixbar 分段依次）；sparkline 描线进场（`pathLength="1"` + dashoffset 1→0）。
- 地图区域入场：激活既有 `--map-delay`（22ms/区交错淡入），指标切换重渲染自然重放；榜单前三奖牌 pop、delta 徽标滑入。

### 浮层入场与微交互

- 详情抽屉 backdrop 淡入 + 抽屉滑入 .38s pop（≤600px 底部抽屉改 translateY 上滑）；命令面板 slideUp .35s。
- CTA 带：同心圆 20s 慢速呼吸环，`(pointer:fine)` 指针跟随辉光（--pointer-x/y），主按钮箭头 hover 右移。
- 页头新增 2px 滚动进度线（渐变蓝紫，rAF 节流）；bento 格与变化卡 hover 上浮+阴影抬升。

### 版本与门禁

- 维护站 `RELEASE = v16.2`；`sw.js` 缓存版本 `wanyu-shell-v3`；`release.py BUILD_VERSION = v16.2`；钉死串测试同步。
- `test_ui_v15` 新增动效契约：显现初始态必须 scoped 在 `.reveal-ready` 下（逐规则解析校验，reduced-motion/无 JS 直出终态）、新令牌、`--map-delay` 被消费、sparkline `pathLength`、进度线三件套。
- 磁盘校验 **217 passed / 0 failed**；`ui_v14+ui_v15+release_v14` 18/18；`maintainable_site+release_v14` 11/11；Node 契约全绿。
- 走查（系统 Chrome，本机无 bundled Chromium 沿用惯例）：hero 中间帧交错可见（150ms 时 h1/stamp 部分透明度）、条/线/图终值=真实数据、抽屉动画 `drawer-in`、reduced-motion 直出终态、390px 无溢出、控制台 0 报错；截图 `tests/artifacts/v16.2/`。
- 数据、岗位原文、审计口径零改动；单文件快照线维持 v16.1 视觉冻结。

## v16.1 · 视觉节奏升级 · 2026-09-02

### 排印与标签体系（学参考站手法，主色保持 #3a83f7 不变）

- 首屏大标题紧排：字距 -.045em → -.05em，字号上限 54px → 58px（430px 以下维持 32px 断点）；hero 副文案限宽 36em。
- 全站 9 个视图的 eyebrow 标签升级为编号格式（`01 / CYCLE OVERVIEW` … `09 / RELEASE NOTES`），编号走 `--text-muted`，与主色标签文字形成层级；岗位详情抽屉与面板内小标签保持原样。

### 页尾行动带

- footer 前新增满幅深色 CTA 带（`.maint-cta`）：eyebrow、两行大字、「打开岗位检索 / 查看数据审计」双本地按钮（`data-maintain-view`，无任何外链）、同心圆 CSS 装饰；打印自动隐藏。
- 三年合计（岗位行/招录人数）由构建脚本从三年审计汇总**现算注入** index.html，不手工写死；`_index_html()` 无参调用（测试路径）自动回退为无数字文案。
- 新增成对设计令牌 `--band-bg/--band-fg/--band-muted/--band-accent/--band-on-accent`（两主题 6 位 hex）；深底文字对比度 ≥4.5 进 `test_ui_v15` 数学回归。

### 动效层（全部尊重 prefers-reduced-motion）

- 滚动渐显：仅当 IntersectionObserver 可用且未开启 reduced-motion 时由 JS 给 `html` 加 `.reveal-ready`；不加类即内容直接可见，打印强制可见。
- 数字 count-up：总览 bento 大数字与审计 KPI 首次入视口 620ms 计数，终值字节级等于真实数据（`data-countup` 显式标记）；reduced-motion 直接显示终值。
- 总览证据卡指针跟随 3D 倾斜（`--tilt-x/--tilt-y`），仅 `(pointer: fine)` 且非 reduced-motion 生效，移出复位。

### 版本与门禁

- 维护站 `RELEASE = v16.1`；`sw.js` 缓存版本升为 `wanyu-shell-v2`（老访客 cache-first 才能拿到新壳）；`release.py BUILD_VERSION = v16.1`。
- 磁盘校验 **217 passed / 0 failed**；`test_ui_v14 + test_ui_v15` 14/14（含新增行动带对比度回归）；`test_maintainable_site + test_release_v14 + test_ui_v13` 19/19；Node 契约（core 7 / datastore / user-store 5）全绿。
- 数据、岗位原文、审计口径零改动；单文件快照线不动（D5 方案 A 视觉冻结维持）。

## v16.0 · 离线缓存与数据工作台 · 2026-09-02

### 离线能力（F10 落地）

- 维护站升级为可安装 PWA：新增 `sw.js` 与 `manifest.webmanifest` + SVG 图标，断网后已访问视图可用。
- 缓存策略：数据 JSON 一律 network-first（在线永远取新，成功后更新缓存），离线回退缓存；壳层与资产 cache-first 并后台刷新。DataStore 的 manifest 字节数与 SHA-256 校验保持不变——缓存不伪装新数据，旧哈希数据会被拒载并触发重试。
- 离线时页头显示「离线缓存」徽标，状态栏播报"离线模式 · 正在显示缓存数据"，恢复在线自动解除。

### 数据工作台

- 收藏与快照页新增「导出工作台 / 导入工作台」：快照、收藏、对比一键导出为带版本号的 JSON；导入逐字段校验清洗（版本、类型、长度、容量上限），坏文件显式报错不落盘。
- 使用说明页新增「数据更新清单」：登记来源 → 重建 → 构建 → 磁盘校验 → 回归走查 → 发布六步勾选清单（本机持久化），关键命令一键复制；清单明示只是进度提示，磁盘校验与审计门禁仍是唯一结论来源。

### 单文件定位（D5 决策：方案 A）

- 离线单文件 `皖域择岗总览.html` 正式定位为**数据归档快照**：页面顶部新增提示条，指引用户使用长期维护入口；单文件视觉冻结在当前版本，不再同步 v15+ 视觉层，数据仍可随发布链更新。

### 版本与门禁

- 维护站版本提升为 `v16.0`；磁盘校验 **217 passed / 0 failed**（+PWA 八项、+工作台三项检查）；发布链 20 模块全绿。
- 浏览器实测：SW 接管页面、预缓存 8 项、数据 JSON 入缓存且可解析（8,511 行）、工作台导出导入往返一致、控制台 error/warn 0。

## v15.0.1 · 岗位地图全省视图 · 2026-09-02

- 岗位地图未选择城市时，检查器直接显示全省汇总：岗位行、招录人数、十六市+省直定位覆盖度；随地图指标（岗位数/招录人数）联动。
- 再次点击已选城市即返回全省汇总；选中态新增「← 返回全省汇总」按钮，键盘 Enter/Space 等效。
- 空态大数字改为当前指标全省合计（如 2026 招录 12,006 人），不引入任何新的数据口径。

## v15.0 · 数据驾驶舱：双主题、派生数据与命令面板 · 2026-09-02

### 设计系统（Token v3）

- 维护站升级为「数据驾驶舱」视觉：亮色为默认主题，新增完整暗色主题，右上角一键切换；主题选择持久化（localStorage），未选择时跟随系统偏好，内联脚本先于样式表注入避免首帧闪烁。
- 全部组件颜色收敛到 CSS 设计令牌，JS 中不再硬编码主色；新增显示级蓝紫渐变 `--grad-display`、数据可视化四色阶 `--viz-1..4`、地图六档热力 `--map-stop-0..5`、动效时长/缓动、玻璃头部、bento 网格与调色板浮层等令牌；旧变量名（`--ink/--muted/--line/--canvas/--card/--blue/--teal/--gold`）保留为主题别名，v14 系列视觉门禁全部兼容。
- WCAG AA 对比度改为数学回归测试（`tests/test_ui_v15.py` 按亮度比公式逐对校验），亮/暗两套画布、正文、边界与状态色全部达标；暗色画布使用 `#0d1524`，并保留 v14.3 参考蓝校准标记。

### 新功能

- 命令面板：`Ctrl/Cmd+K` 或 `/` 唤起，支持按岗位代码/单位/职位/城市检索并直达岗位详情、视图切换与主题切换；岗位索引按周期懒加载（`palette.json`），面板关闭即释放。
- 总览页重构为 bento 网格：核心指标卡、相邻周期增量 delta 芯片、专业结构 mixbar、三年招录走势 sparkline、区域热度排行（前三名奖牌标识 + 数字条）、覆盖度芯片；所有派生数值可从源岗位行复算。
- 三年对照页新增斜率图（slope graph）：展示相邻周期城市招录走势；宿松→安庆、广德→宣城仅在图表层按导航口径归并，源数据原值不变。
- 岗位详情支持分享链接（`#job/<稳定ID>`），直接打开详情抽屉，关闭后恢复原视图；收藏与对比清单新增字段级差异高亮和对比 CSV 导出。
- 岗位榜单新增「竞争观测」列：仅展示有官方观测值的行，分母缺失或覆盖不完整时显示「不可比」，不参与排名；增加数字条与前后三名奖牌标识。
- 检索支持紧凑密度切换；新增打印样式（打印时仅保留主内容区）。

### 数据模块（新增，均由构建脚本派生）

- 每周期新增 `derived.json`（schema `wanyu-maintainable-derived/v1`）：`vs_prev` 相邻周期增量（首周期 base 为 null）、专业结构 `mix`、城市招录走势 `city_trend` 与未归并城市公开计数 `unmapped_cities`。
- 每周期新增 `palette.json`（schema `wanyu-maintainable-palette/v1`）：命令面板轻量索引（id/代码/单位[:60]/职位[:60]/城市/考试），不含源岗位行全文。
- `site-manifest.json` 记录两份新模块的字节数与 SHA-256；磁盘校验从 142 项扩展到 **185 项**，新增派生数学交叉核对（deltas 与 manifest 差值一致、mix 合计=岗位数、city_trend+unmapped=岗位数）与面板索引核对（ID 唯一且 ⊆ 岗位行 ID）。

### 交付与维护

- 维护站版本提升为 `v15.0`；发布脚本 `release.py` 同步 v15.0 门禁链，ZIP 根文件清单更新为 archive/ 下的交接文档与计划任务归档。
- 离线单文件快照 `皖域择岗总览.html` 数据基线不变；维护站为唯一持续演进入口。
- F10（PWA 离线缓存）按决策点 D4 延后至后续版本。

### 验收证据

- 维护站磁盘校验：**185 passed / 0 failed**。
- 发布链 Python 单测（含 test_ui_v15 双主题/对比度/令牌契约）：全部通过。
- Node 核心逻辑、DataStore 与 UserStore 契约测试：全部通过。
- 内置浏览器双主题走查：亮/暗切换、命令面板、bento 总览、斜率图、`#job/` 分享链接、榜单竞争观测；控制台 error/warn：0。
- 已知事项（v15.1 更新）：`test_anhui_web.py` 的 8 个 v9/v10 过期契约已清债并对齐现行结构，页面构建改为沙箱目录、不再向 `deliverables/` 写入，该模块已纳入发布门禁链。

## v14.4 · 用户走查与长期维护升级 · 2026-09-01

### 真实用户路径

- 完成总览、三年对照、岗位地图、岗位榜单、逐岗检索、岗位详情、收藏与快照、数据审计、使用说明、更新日志的内置浏览器走查；覆盖 2024、2025、2026 和法学/计算机类/软件工程等专业筛选。
- 地图跳转到检索时清除残留关键词、专业、城市和考试条件，只保留明确的地图汇总条件；检索页显示已生效筛选并支持逐项清除、全部清空、排序和每页行数。
- 岗位详情增加加入/移出对比；收藏与对比清单支持重新打开当前周期岗位。来源定位、审计证据和模块路径默认折叠，减少用户被技术细节淹没。

### 专业与数据语义

- 三周期 catalog 改为 `readable_keywords`：2024/2025/2026 候选数为 3,097 / 2,956 / 2,617；候选从专业目录和源 `zy` 派生，源岗位原文保持不变。
- 三周期专业候选均无纯数字/纯编码值，软件工程、法学、计算机类等可读关键词可直接选择；详情页明确提示资格判断仍以当年官方公告、职位表和目录为准。
- `observed_at` 无源材料日期时写入 `null` 并显示“未提供”；移除 `2000-01-01` 占位日期。2026 源包真实日期仍原样展示。
- 审计状态、风险级别、匹配策略改为用户可读中文，公开缺口仍按证据状态保留，不把未发布、未取得或无法唯一匹配推断为 0。

### 视觉与维护

- 延续参考图方向的淡蓝 `#3A83F7`：近白画布、浅蓝边界、低对比阴影，避免青绿色主视觉；长标签在桌面和移动端可换行，不再溢出。
- 维护站继续采用单网页壳 + 周期外置 JSON；本轮为目录关键词匹配增加缓存，三周期重建耗时由约 7 分钟降至约 88 秒（本机一次构建实测）。
- 维护站版本提升为 `v14.4`，更新日志从 manifest/审计数据读取，不再硬编码旧统计。

### 验收证据

- 维护站磁盘校验：**142 passed / 0 failed**。
- 维护站自动浏览器烟测：**PASS**，覆盖三周期切换、地图 16 区域、地图→检索、专业筛选、详情、收藏、审计和 390/768/1440 响应式。
- 内置浏览器最终走查：**22/22 通过**，控制台 error/warn：**0**。
- 页面截图与逐页问题分析：`tests/artifacts/audit-20260901/REPORT.md`。

### 仍然公开的外部资料边界

当前交接包仍有 **8 个审计事件**（不是 UI 缺陷）：2024 三项、2025 三项、2026 两项；另有 2026 成绩附件 **116 个无法唯一匹配项**。取得官方新公告或可唯一匹配的成绩附件后，按数据更新手册登记、重建、校验和回归，不能在页面层补造。

## v14.1 · 参考图纯蓝校准 · 2026-09-01

- 依据用户提供的参考色 `#3A83F7`，将主操作色、周期切换、地图高值区、指标数字和品牌标记统一到明亮纯蓝。
- 背景、边界和辅助状态改用近白与极浅蓝；兼容变量 `--accent-teal` 也改为蓝阶，不再产生青绿色主视觉。
- 地图热力改为 `#EDF4FF → #3A83F7` 同色阶，保留三年周期、岗位/招录人数切换和城市联动功能。

## v14.0 · 淡蓝色视觉校准 · 2026-09-01

- 统一维护站改为冷白、雾蓝、淡蓝主色；顶部、品牌标记、卡片、按钮、提示和地图热力全部收敛到同一蓝色层级。
- 青绿色不再承担主界面视觉；仅保留必要的语义状态色和省直提示色，避免地图与工作台出现发青、发脏的综合色感。
- 新增淡蓝配色回归测试，并通过实际浏览器截图确认桌面页面的地图、导航、检查器和城市卡视觉一致。

## v14.0 · 岗位地图恢复补丁 · 2026-09-01

- 恢复统一维护站“岗位地图”视图；真实几何由 `tools/anhui_web/data/anhui_340000_full.json` 投影生成，外置为 `maintainable/data/map/anhui.json`，不把岗位行和地图路径塞回 HTML。
- 地图支持 2024、2025、2026 周期切换、岗位数/招录人数切换、十六市区域/标签/城市卡点击、城市检查器和岗位检索联动。
- 2024 的区县、市直、宿松、广德原始城市值只做行政区级导航归并并保留原值；`省直`作为省级直属独立口径展示，禁止显示为“省直市”；无法归类的城市值公开计数，不静默丢失。
- `site-manifest.json` 新增 `map` 全局模块，磁盘校验新增 schema、字节数、SHA-256、16 feature、16 城市、路径和标签坐标检查；浏览器烟测新增地图交互与外置请求检查。

## v14.0 · 2026-09-01

### 维护站架构

- 统一入口 `maintainable/index.html` 在一个网页内切换 2024、2025、2026 及总览、三年对照、岗位榜单、岗位检索、收藏快照、数据审计。
- 岗位源事实从 HTML 拆到每周期 `jobs.json`；新增 `overview.json`、`catalog.json`、`positions.json`、`scores.json`、`changes.json`、`audit.json`。
- `site-manifest.json` 记录 v14.0、模块路径、字节数、SHA-256 与 schema；`DataStore` 按 manifest 懒加载、缓存、重试和结构校验；全局复核事件输出为 `review-queue.json`。
- 保留 `皖域择岗总览.html` 作为可双击离线快照和回退入口。

### 功能与 UI

- 岗位榜单支持专业、城市、考试类别、岗位类型和指标组合筛选；专业候选过滤纯数字与符号编码，原始 `zy` 不改。
- 岗位检索支持关键词、城市、考试、分页、保存筛选和安全 CSV 导出；首屏最多渲染 120 行。
- 岗位详情抽屉展示源字段、稳定 ID、证据状态、来源路径、源定位、日期和处理方式；Escape 关闭后焦点返回。
- 三年对照页加载相邻周期变化模块，区分新增、撤回、字段变更和待复核，并展示可比性。
- 收藏与筛选快照只保存稳定 ID/条件/版本，不复制整行；本地数据带版本和容量上限。
- 数据审计页分开显示 8 项公开边界与 116 条无法唯一匹配成绩，支持高风险/未发布/歧义/待复核过滤。
- 新增浅色冷白雾蓝设计令牌、证据抽屉、审计队列、变化卡片、响应式布局、可见焦点与 reduced-motion。

### 数据边界

- 2024：10,017 岗 / 15,331 人 / 成绩待复核 0。
- 2025：10,150 岗 / 14,721 人 / 成绩待复核 0。
- 2026：8,511 岗 / 12,006 人 / 成绩待复核 116。
- 三年合计：28,678 岗 / 42,058 人 / 公开审计边界 8 项。
- 未发布、未取得、无法唯一关联的值继续保持空值和状态标记；本日志不宣称所有外部官方逐岗资料已取得。

### 验收入口

- 构建：`python tools/anhui_web/build_maintainable_site.py --root . --output-dir deliverables/maintainable`
- 磁盘校验：`python tools/anhui_web/verify_maintainable_site.py deliverables/maintainable`
- 维护站浏览器烟测：`node tests/maintainable_browser_smoke.js`
- 一键正式发布：`python tools/anhui_web/release.py --zip`

## v13.4 · 2026-09-01

- 增加数据审计中心、周期模块拆分、组合筛选与公开缺口展示，作为 v14.0 的冻结基线。
