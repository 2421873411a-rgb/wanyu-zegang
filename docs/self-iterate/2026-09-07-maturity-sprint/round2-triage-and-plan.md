# Round 2 Triage 与修复计划（v17.9.12）

三镜头审计（认证安全 / API行为+迁移漂移 / 供应链+性能+运维）共产出：P0×1、P1×8、P2×约20、P3×6。
去重后（跨镜头重复项合并）：**确认修复 P0×1、P1×8、P2×16、P3×4；豁免 3；并入相关项处理若干。**

## 修复批次（分支 fix/v17.9.12-round2-audit，基线 origin/main=ab5d63d）

### R1 P0：用户筛选快照端点（A1=T同项）
- filters JSON 序列化成对处理（写 dumps/读 loads）；filters ≤32KB、每用户快照 ≤50；
- 补 POST/GET/DELETE 门禁测试（Unicode 键/空 dict/超限 400）。

### R2 认证 P1 双项 + 限流体系重建（T1/T2 + 限流 P2/P3 集合）
- **T2 SECRET_KEY**：取消默认值——ENV!=test 缺失即拒启；黑名单改为长度+熵下限（<32 字符生产拒启）。
- **T1 限流原子化 + Redis 后端**（采纳审计设计）：
  - MemoryLimiter：check-then-hit 合并为单步原子（先记后判，宁可错杀）——进程内也封死竞态；
  - RedisLimiter：Lua 原子滑动窗（ZSET+lock key），scope ∈ login/register/refresh/logout；
  - `RATE_LIMIT_BACKEND=memory|redis`（默认 memory 行为兼容），相关 Settings 阈值项；
  - 降级：Redis 不可达 fail-open + 进程内收紧兜底 + ERROR 日志；
  - refresh 30/60s、logout 10/60s 新增限流；登录未知用户走哑 bcrypt（时序侧信道）；
  - key 无界增长由 Redis TTL / 内存清扫解决；register 加每 IP 上限；
  - CI postgres job 挂 redis:7 service，Redis 模式测试以 REDIS_URL 门控（不引入 fakeredis）。
- 登录失败/限流命中补日志（配合 R7）。

### R3 API/安全 P2/P3 簇
- refresh 轮换乐观锁（UPDATE ... WHERE revoked_at IS NULL，rowcount==1 才签发）——后端无关防双花；
- ilike 通配符转义（%/_) + 控制字符（含 NUL）入参 422；
- page 上限 le=10000（int64 溢出与深翻页一起封）；
- salary value_wan 零值 `is not None`（零不冒充未知）；
- schema max_length 对齐列宽（display_name≤128、note≤500、view≤32 等）；
- RecursionError/UnicodeDecodeError 并入 400；
- CompareListCreate 删除 position 字段；
- email 注册/登录统一 lower()；最后管理员保护改条件 UPDATE rowcount 判定。

### R4 迁移与启动防呆
- init_db：alembic_version fetchall，行数≠1 → RuntimeError；
- 迁移 0004：性能索引（GIN trgm：unit/zw/zy/code；复合 (record_status,num DESC)）
  + jobs.record_status server_default='active' + NULL 回填 UPDATE（A4 窗口封死）。

### R5 运维簇（S1-S6/S11-S13）
- deploy.sh：alembic upgrade 前 pg_dump -Fc + 非空校验；每次部署 sed 强制刷新 .env 的 APP_VERSION；
  落 /etc/logrotate.d/wanyu-api；nginx /api/ 加 client_max_body_size 64m；
  systemd redis Requires→Wants；gunicorn 显式 forwarded_allow_ips=127.0.0.1 + capture_output=True；
- RUNBOOK：回滚顺序改为"先 downgrade 后回滚代码"；
- /health 加 DB SELECT 1（失败 503）；app 显式 logging 配置（INFO 落 stderr→gunicorn 收集）。

### R6 性能
- stats/by-city|by-exam 进程内 TTL 缓存（60s）；page 上限已入 R3；索引已入 R4。

### R7 依赖/环境
- dev lock 补 uvloop（完整上游 marker）；runtime lock marker 补全；删除陈旧 .venv（本地卫生，不进 git）；
- api-data-store.js 三个幻端点：文档化真实消费面 + 代码头 DEPRECATED 注释（不补端点——静态站是既定消费形态）。

## 豁免（书面）
- 弱口令策略现状（"aaaaaaaaa1"可过）→ 既定取舍，注释已声明；
- /api/docs 生产开放 → 部署文档明示设计；
- username 大小写变体展示风险 → 无信任决策基于用户名，豁免（email 已修）。

## 验证
新增回归：快照 CRUD 门禁、20 并发错密码 ≤5 过（红绿对照 T1 的 20/20）、未知用户哑 bcrypt 计数、
SECRET_KEY 门禁矩阵、SQLite 乐观锁轮换、LIKE 转义、page 溢出 400、salary 零值、
alembic 多行拒启、schema 422 边界、Redis 模式（REDIS_URL 门控）。
九门 + CI 模拟全绿后 PR；版本 v17.9.12；CHANGELOG 追加。
