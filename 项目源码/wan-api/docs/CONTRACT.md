# wan-api 与 canonical 数据链的接口契约（v17.9.11 · Round-1 收口）

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
   `num/bm` 必须整数（浮点拒绝，不静默截断）；排除行必须携带
   `exclusion_reason/exclusion_evidence/excluded_at` 三件套；
3. `record_status` 词表与 `docs/data-contract/record-status.md` 对齐：`active`（含缺失）+
   `duplicate/invalid_source/withdrawn/superseded/needs_review`（+DB 派生态 `excluded`）；
   **DB 层一律折叠为二值 active/excluded**，排除态的判定细节以 `record_status` 源值折进证据字段；
4. 大小上限 `ADMIN_IMPORT_MAX_BYTES`（默认 64MB），超限 413；
5. 快照替换语义：行内字段 exact overwrite（源清空 → DB 清空）；重新出现在 active 快照的行
   强制恢复 active；DB 有但快照没有 → `record_status='excluded'` +
   `exclusion_reason='snapshot_removed_in_later_snapshot'` + 证据=新快照 source_sha256；
   被下线岗位的收藏/对比引用级联清理（不留"列表可见、详情 404"幽灵）；
6. 写入单事务；`imported + updated == rows_total` 对账不符 → 500 整体回滚（`skipped` 已废除——
   任何行都不允许静默跳过）；
7. 响应携带 `source_sha256`、分项计数（含 `deactivated`）、`job_id_set_sha256` 与全周期
   `mirror_states` 摘要（跨周期版本错位当场可见）；
8. 生产引导 `import_all_data`：三周期 + 待遇 + 复核事件，全部文件先校验后单事务写入；
   任一文件缺失或校验失败 → 整体拒绝零写入；复核事件按 `(kind, cycle, title)` 幂等 upsert
   （重跑翻倍已修复）；未来任何"动态化"改动都从 canonical 派生并携带版本号，禁止手工改镜像表数据。

## 3. 认证契约

- access token：Bearer header，30 分钟；
- refresh token：JSON body 提交（**永不进 query/URL**），服务器端 `refresh_tokens` 表存 sha256，
  轮换即撤销旧 token，检测到已撤销 token 重用 → 撤销整个 family；
- 生产环境 `ENV=production` + 默认 SECRET_KEY = 拒绝启动（fail-closed）；
- 登录/注册限流：同 IP+账号 5 次失败 / 5 分钟（进程内实现，多 worker 部署前接 Redis）。

## 4. 版本与部署契约

- 版本单一真源 = `项目源码/release.json` 的 `release`；`config.APP_VERSION` 启动时读它，
  部署布局由 deploy.sh 注入 .env；`/health` 返回 `version`，deploy smoke 断言其等于部署版本；
- deploy.sh：`set -Eeuo pipefail`、无 `|| true` 吞错、`systemctl restart`、
  换血前自动备份旧版本（`/opt/wanyu/backup/`，回滚见 `docs/ops/RUNBOOK.md`）；
- nginx `/maintainable/` 用 `root`（alias+try_files 是 nginx trac#97 缺陷）；certbot `--redirect`。

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
- [ ] S8：staging 压测 + 安全回归 + fresh-host 部署演练
- [ ] 多 worker 前接入 Redis 限流与会话级指标
- [ ] 线上部署后密钥轮换（SSH 私钥已随交接包分发过）
