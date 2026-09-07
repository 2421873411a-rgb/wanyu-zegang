# Round 2 审计报告 · 镜头：供应链 + 性能 + 运维可观测（子代理产出，含实测；主控已抽查证伪 F3/F13）

- S1 P1 RUNBOOK 回滚顺序错误：先 rsync 旧代码再 alembic downgrade → "Can't locate revision"（新 revision 不在旧 migrations 里）。修法：先 downgrade 再回滚代码。
- S2 P1 pg_dump 未被 deploy.sh 强制（仅 RUNBOOK 文字）。修法：alembic upgrade 前 pg_dump -Fc + 非空校验。
- S3 P1 .env APP_VERSION 只在首次部署写入，pydantic-settings 下 .env 覆盖派生默认（实测 v9.9.9-from-env 生效）→ 二次部署 smoke 必败。**主控实证成立（Round 1 设计缺陷）**。修法：每次部署 sed 强制更新 .env 的 APP_VERSION。
- S4 P1 唯一 app 级审计日志（admin 导入 INFO）无 logging 配置被丢弃。修法：显式 logging 配置 + 登录失败/限流命中补日志。
- S5 P1 /health 不含 DB 探活（DB 挂仍 200）。修法：SELECT 1 + 503 区分 readiness。
- S6 P1 keyword/major ilike 全表扫实测 168-294ms/28.5k 行；pg_trgm 装了但零 GIN 索引。修法：GIN trgm 索引（unit/zw/zy/code）。
- S7 P2 sort=recruits 深翻页 371ms（TEMP B-TREE，num 无索引，page 无上限）。修法：(record_status,num DESC) 复合索引 + page 上限。
- S8 P2 stats/by-city|exam 每次全聚合 90ms 无缓存。修法：TTL 缓存（导入失效）。
- S9 P2 两 lock 漂移：dev lock 无 uvloop（CI/生产事件循环不一致）。修法：dev lock 补 uvloop（完整上游 marker）。
- S10 P2 本机 .venv 含 11 个 lock 外包。处置：清理删除 .venv（改用全局 lock 安装环境）。
- S11 P2 redis[hiredis] 死依赖但 systemd Requires= 硬依赖。处置：本批实现 Redis 限流后依赖变活；unit 仍改 Wants=（限流有降级，redis 挂不应阻断启动）。
- S12 P2 无 logrotate。修法：deploy.sh 落 /etc/logrotate.d/wanyu-api（daily+14+compress+copytruncate）。
- S13 P2 nginx 无 client_max_body_size（默认 1MB）挡死 12MB 真实快照的 HTTPS 管理导入（app 的 64MB 永远够不到）。**主控实证成立（0 命中 + 2024 jobs.json=12,055,607B）**。修法：/api/ 加 client_max_body_size 64m。
- S14 P2 uvloop marker 与上游条件不完全一致（PyPy/cygwin 理论偏差）。修法：补全上游条件。
- 已验证无问题（实测）：runtime lock=精确传递闭包（45 包零漂移）；extras 展开完备；两 lock 共享包零漂移；max_requests 已配；单 worker+进程内限流自洽；access log 含 %(D)s 慢请求可见。
