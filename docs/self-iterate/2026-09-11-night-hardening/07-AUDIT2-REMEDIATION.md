# 07 · 第二轮独立审计处置台账（2026-09-11）

两路无上下文注入的只读子代理分别审计（A：前端+构建+CI；B：后端+数据链路+部署）。
合计 28 条发现（0 P0、3 P1、8 P2、17 P3）。本表记录处置；**本轮在交接打包前主动收口**。

## 已修复

### 批 1（commit d548687）

| ID | 级别 | 修复 |
| --- | --- | --- |
| FE-001 | P1 | unit 作业改与 canonical-ci 同源：unittest discovery + 同一 EXCLUDED 清单（原 pytest 不在 requirements 且 10 个模块依赖 git 外产物，hosted 必红） |
| FE-002 | P1 | 构建输入 major_catalog.json(100K)/anhui_340000_full.json(128K) 显式入库；重建比对改用 compare_rebuilt_site.py（归一 .gz 与 supplement 链） |
| FE-003 | P2 | deriveSource 键名 `locator`→`source_locator` 对齐渲染端；烟测新增"源定位必须呈现"断言 |
| FE-008 | P3 | 各作业 timeout-minutes；重建证据 upload-artifact；main 分支 run 永不取消 |
| API-001 | P1 | create_admin 对已存在启用管理员幂等放行（exit 0）；子进程回归测试连跑两次全 0；RUNBOOK 注明 |
| API-004 | P2 | readiness_check 静态数据路径对齐真实布局 `cycles/<cycle>/jobs.json` |
| API-005 | P3 | ready 判定抽 compute_ready 纯函数修优先级；补 alembic head 对比；单测覆盖 |

### 批 2（commit 见 git log；打包前收口）

| ID | 级别 | 修复 |
| --- | --- | --- |
| API-002 | P2 | rollback_to_previous 增加迁移 head 守卫：DB revision 已前移（≠迁移前 sidecar）时拒绝自动回切，打印两条人工路径（新 venv downgrade 后回切 / 直接修复重部） |
| API-003 | P2 | 部署期快照权限与 backup_database.sh 统一为 750/640 root:postgres；restore_drill 与 RUNBOOK 恢复改 stdin 管道（postgres 不再依赖文件遍历权限）；快照测试补 chown 桩 |

## 刻意延后（交接后按批处理，理由在案）

| ID | 级别 | 事项 | 理由 |
| --- | --- | --- | --- |
| API-006 | P2 | 生产导入缺 canonical 指纹闭环 | 需构建器把 provenance 写入静态 jobs.json + 校验器强制，动数据链，须单独立项 |
| API-008 | P2 | login_ip 30/h 含成功登录、锁 1h | 产品取舍（防爆破强度 vs NAT 用户），需站长拍板参数 |
| API-010 | P3 | 收藏无上限/无分页 | 配额参数需产品确认（建议 500），模式可复制 snapshot 的 advisory lock |
| API-011 | P3 | /api/docs 生产公开 | 一行改（ENV=production 置 None），随下个 API 版本走 |
| API-013 | P3 | readiness 证据文件不在部署载荷 | 改 --evidence 参数或 /etc/wanyu 路径，小改 |
| API-015/016 | P3 | 数据基线四处硬编码 / STATIC_DATA_PATH 首署后不刷新 | 小改，随下个工程窗 |
| API-007/009/012/014 | P3 | sources.lock CI 实比对 / refresh_tokens 清理 / 导入列宽校验 / refresh 重用零容忍 | 均已定位，见审计原文 |
| FE-004 | P2 | v17-tools 不过滤排除行+混合分母竞争比 | 需与主站口径函数复用，涉三年趋势页回归，单独成包 |
| FE-005/006 | P3 | SW 预缓存 supplement 永不命中 / verifier 死代码门禁 | SW 缓存分层重设计一并处理 |
| FE-007 | P3 | verifier 漏 calendar/supplement 磁盘校验；parity 漏 icon/webmanifest | 补覆盖清单已写明，小改 |
| FE-009/010 | P3 | IntegrityError 静默降级 / a11y 与硬编码批次 | UI 批次处理 |
| FE-011/012 | P3 | major_city 溯源弱耦合 / 烟测 WANYU_SITE_DIR 静默回退 | 小改，随下个工程窗 |
