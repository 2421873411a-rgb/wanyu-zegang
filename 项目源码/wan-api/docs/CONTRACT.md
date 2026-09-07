# wan-api 与 canonical 数据链的接口契约（v17.9.4 · S6）

> 一句话：**canonical/cycles/*.json 仍是唯一正式数据真源；wan-api 是用户状态层与读取服务层，永远不产生第二数据真源。**

## 1. 数据边界

| 层 | 真源 | wan-api 的角色 |
|---|---|---|
| 岗位/周期/待遇/复核事件 | `项目源码/canonical/cycles/*.json`（构建期锁定，sources.lock 校验） | 只读展示（jobs/cycles/salary/audit 路由）；导入仅限管理员重建镜像表，且必须能逐行回溯到 canonical 行 |
| 用户态（收藏/快照/对比） | wan-api 数据库 | 唯一写入口；只引用 `job_id`，不复制岗位正文 |
| 认证 | wan-api 数据库 | 注册永远产生普通用户；管理员唯一路径 = `scripts/create_admin.py` |

## 2. 导入纪律（admin/import）

1. 请求体必须与 canonical 产物同构（`allMajors.rows`，行含 `job_id/row_id`）；
2. 大小上限 `ADMIN_IMPORT_MAX_BYTES`（默认 64MB），超限 413；
3. 写入在单事务内完成；`imported + updated + skipped == rows_total` 对账不符 → 整体回滚；
4. 响应必须携带 `source_sha256` + 分项计数（假成功在 v17.9.4 已删除，见 admin.py）；
5. 未来任何"动态化"改动（预计算、缓存表、搜索索引）都从 canonical 派生并携带版本号，禁止手工改镜像表数据。

## 3. 认证契约

- access token：Bearer header，30 分钟；
- refresh token：JSON body 提交（**永不进 query/URL**），服务器端 `refresh_tokens` 表存 sha256，
  轮换即撤销旧 token，检测到已撤销 token 重用 → 撤销整个 family；
- 生产环境 `ENV=production` + 默认 SECRET_KEY = 拒绝启动（fail-closed）；
- 登录/注册限流：同 IP+账号 5 次失败 / 5 分钟（进程内实现，多 worker 部署前接 Redis）。

## 4. 门禁场景（tests/ 锁死，任何改动不得削弱）

1. ADMIN_EMAIL 注册 → 必须普通用户
2. `ENV=production` + 默认 SECRET_KEY → 拒绝启动
3. refresh query 形态 → 拒绝
4. 重复收藏/对比 → 数据库 UNIQUE 拒绝
5. 对比列表第 5 个 → 400
6. 导入结构不符/非法周期 → 400；成功必须真实写库 + 行数对账
7. 最后管理员不可降权/禁用
8. 超大上传 → 413
9. 轮换/重用检测/登出 family 撤销

## 5. 上线前置（未满足前保持 EXPERIMENTAL / NOT FOR PRODUCTION）

- [x] S0-S6（本分支）
- [ ] S8：staging 压测 + 安全回归
- [ ] 多 worker 前接入 Redis 限流与会话级指标
- [ ] 线上部署后密钥轮换（SSH 私钥已随交接包分发过）
