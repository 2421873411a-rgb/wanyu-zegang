# wan-api 与 canonical 数据链的接口契约（随版本滚动更新；当前 v17.10.1 · 审查修复轮）

> 一句话：**canonical/cycles/*.json 仍是唯一正式数据真源；wan-api 是用户状态层与读取服务层，永远不产生第二数据真源。**

## 1. 数据边界

| 层 | 真源 | wan-api 的角色 |
|---|---|---|
| 岗位/周期/待遇/复核事件 | `项目源码/canonical/cycles/*.json`（构建期锁定，sources.lock 校验） | 只读展示（jobs/cycles/salary/audit 路由）；导入仅限管理员重建镜像表，且必须能逐行回溯到 canonical 行 |
| 用户态（收藏/快照/对比） | wan-api 数据库 | 唯一写入口；只引用 `job_id`，不复制岗位正文；引用目标必须是当前 active 岗位 |
| 认证 | wan-api 数据库 | 注册永远产生普通用户；管理员唯一路径 = `scripts/create_admin.py`（deploy.sh 可 env 传参自动引导） |

## 2. 导入纪律（admin/import 与 import_all_data 共用）

1. 请求体接受 canonical 键 `all_majors`（**权威口径**）与静态派生键 `allMajors`（部署存量兼容）；
   canonical bundle（`all_majors` 键或 `schema=wanyu-cycle-bundle/v1`）**必须携带**
   `provenance.job_id_set_sha256` 且与行集一致——指纹不可缺席（缺席=删指纹绕过校验）；
2. fail-closed 校验（任一违规 → 400 整包零写入）：meta 必填且守恒
   （`raw_total`==行数、`excluded`==排除行数；`total/recruits` 必须成对同口径——
   canonical `total=raw,recruits=raw` 或静态 `total=active,recruits=active`，混搭拒绝）；
   `job_id` 强格式 `^job-(\d{4})-[0-9a-f]{20}$` 且年份==周期、全局唯一；
   `num/bm` 提供时必须整数（浮点拒绝，不静默截断）；排除行必须携带
   `exclusion_reason/exclusion_evidence/excluded_at` 三件套；
3. `record_status` 词表与 仓库根 `docs/data-contract/record-status.md` 对齐：`active`（含缺失）+
   `duplicate/invalid_source/withdrawn/superseded/needs_review`（+DB 派生态 `excluded`）；
   **DB 层一律折叠为二值 active/excluded**，排除态的判定细节以 `record_status` 源值折进证据字段；
4. 大小上限 `ADMIN_IMPORT_MAX_BYTES`（默认 64MB），超限 413；
5. 快照替换语义：行内字段 exact overwrite（源清空 → DB 清空）；重新出现在 active 快照的行
   强制恢复 active；DB 有但快照没有 → `record_status='excluded'` +
   `exclusion_reason='snapshot_removed_in_later_snapshot'` + 证据=新快照 source_sha256；
   被下线岗位（快照移除或快照内在场被标记排除态）的收藏/对比引用级联清理
  （不留"列表可见、详情 404"幽灵）；
6. 写入单事务；`imported + updated == rows_total` 对账不符 → 500 整体回滚（`skipped` 已废除——
   任何行都不允许静默跳过）；
7. 响应携带 `source_sha256`、分项计数（含 `deactivated`）、`job_id_set_sha256` 与全周期
   `mirror_states` 摘要（跨周期版本错位当场可见）；
8. 生产引导 `import_all_data`：三周期 jobs.json **缺一不可**（任一缺失即整体拒绝），
   待遇与复核事件文件存在才导入（缺失跳过，不视为失败）；全部文件先校验后单事务写入；
   复核事件按 `(kind, cycle, title)` 幂等 upsert；未来任何"动态化"改动都从 canonical
   派生并携带版本号，禁止手工改镜像表数据。

## 3. 认证契约

- access token：Bearer header，30 分钟；
- refresh token：JSON body 提交（**永不进 query/URL**），服务器端 `refresh_tokens` 表存 sha256，
  轮换即撤销旧 token，检测到已撤销 token 重用 → 撤销整个 family；
- 生产环境 `ENV=production` + 默认 SECRET_KEY = 拒绝启动（fail-closed）；
- 限流（v17.9.12 双后端）：login 5 失败/5 分钟、register 5 次/5 分钟（IP+账号）、
  refresh 30 次/分、logout 10 次/分（IP）；`RATE_LIMIT_BACKEND=memory|redis`，
  memory 为原子单步判定，redis 为 Lua 原子滑动窗（多 worker 安全，生产默认），
  Redis 不可达时 fail-open 降级到按 worker 数收紧的进程内兜底。

## 4. 版本与部署契约

- API 版本单一真源 = `wan-api/release.json`（wanyu-api-release/v1）的 `release`；
  `config.APP_VERSION` 启动时读它（项目级 `项目源码/release.json` 是网站产品版本，互不捆绑），
  deploy.sh 必须在任何 secret 写入前先解析版本，再注入独立 EnvironmentFile；`/health` 返回
  `version`，deploy smoke 断言其等于部署版本；
- deploy.sh：`set -Eeuo pipefail`、除 read_existing_db_password 显式允许为空的 grep 外
  无 `|| true` 吞错、`systemctl restart`、
  迁移前/导入后生成原子 PostgreSQL dump + checksum（`/opt/wanyu/backup/`，回滚见
  `docs/ops/RUNBOOK.md`）；
- 生产部署和 `--build-only` 必须复用同一个 `build_release()`，不得复制 tar/venv 实现；
- nginx `/maintainable/` 用 `root`（alias+try_files 是 nginx trac#97 缺陷）；HTTPS `/` 可 302 到
  `/maintainable/index.html`，smoke 必须跟随跳转并以最终 200 为准；certbot `--redirect`；
- `wanyu-backup.timer` 默认仅产生**本机恢复点**。只有 COS 异地上传、桶版本化/保留策略和
  异机 restore drill 都有证据后，才可称“灾难恢复”。daily/weekly/monthly 每份 dump 必须有
  同目录可独立校验的 `.sha256`。

## 5. 门禁场景（tests/ 锁死，任何改动不得削弱）

1. ADMIN_EMAIL 注册 → 必须普通用户
2. `ENV=production` + 默认 SECRET_KEY → 拒绝启动
3. refresh query 形态 → 拒绝
4. 重复收藏/对比 → 数据库 UNIQUE 拒绝；引用不存在的岗位 → add 时 400
5. 对比列表第 5 个 → 400（并发下仍 ≤4，PG job 实证）
6. 导入：结构不符/非法周期/meta 缺失/口径混搭/job_id 格式/浮点 num/指纹错/缺席 → 400；
   成功必须真实写库 + 对账 + 证据留存；重跑幂等
7. 最后管理员不可降权/禁用
8. 超大上传 → 413
9. 轮换/重用检测/登出 family 撤销
10. 部署面 linkage：deploy.sh/heredoc/gunicorn/lock/unit/nginx/版本一致性全部进 pytest

## 6. 已知豁免（书面记录）

- xl（学历）等展示字段的归一属静态站表现层约定；DB 镜像 canonical 原始口径，
  生产导入走静态派生路径时口径稳定。
- `/api/v1/audit/review-queue` 为公开数据：同一内容已由静态站
  `data/audit/review-queue.json` 公开，API 仅作镜像，收紧不改变暴露面。
- PR 审批人数为 0：单人仓库，三 required check + enforce_admins 为实际门禁。

## 7. 上线前置（未满足前保持 EXPERIMENTAL / NOT FOR PRODUCTION）

- [x] S0-S6（v17.9.x 系列）
- [x] Round-1 深度收口（v17.9.11：部署链 P0/P1、数据完整性 P1×3、CI 门禁覆盖面、版本单一真源）
- [x] Round-2 深度收口（v17.9.12：快照 P0、限流原子化+Redis 后端、SECRET_KEY 门禁、可观测性、性能索引）
- [x] Round-3 复审收口（v17.9.13/v17.9.14：转义缺陷实现修复+正向门禁、首署 mkdir、限流时钟/内存、文档真源统一、停服窗口前移）
- [x] Round-4 盲区终扫（v17.9.14：反斜杠转义真落地、release 列宽、CI timeout/permissions、载荷排除 *.db、/health 限流）
- [x] Round-5 复审收口（v17.9.15：deploy 载荷行续行符 P0、redis-server 单元名、RUNBOOK 回滚核验/前置一节、备份权限、stats 缓存上限）
- [x] Round-9 代码级修复（v17.9.19：版本初始化、redirect-aware smoke、restore 建库/venv 路径/失败清理、checksum 配对、唯一构建实现）
- [x] 真机部署与演练闭环（2026-09-09，v17.9.21/v17.9.22）：deploy.sh 全流程部署 ×2（幂等导入/
      迁移前后双快照/smoke 全过/公网验证）；upgrade_drill 四不变量 ALL PASS（含 P1-006 前置路径
      修复）；restore_drill PASS（checksum→pg_restore→revision f3a91c2d7e04→行数对账
      10017/10150/8511+salary160+review7，P1-007 权限断链修复后）；自动回滚 rollback_to_previous
      实弹验证（真机切回 N-1、APP_VERSION 回写、健康，随即重部署）。注：未使用新机器，
      "fresh-host 模板"语义由同机全新 release 目录+全新 venv 等价覆盖。
- [ ] 多 worker 前接入 Redis 限流与会话级指标
- [ ] 线上部署后密钥轮换（SSH 私钥已轮换至 ed25519 并验证；SECRET_KEY 轮换待窗口）
- [ ] COS 异地副本启用桶版本化/保留策略，并在异机完成下载+checksum+restore drill
      （服务器 coscli 未安装、凭据未配置——需站长腾讯云控制台操作，当前备份仅本机恢复点）
