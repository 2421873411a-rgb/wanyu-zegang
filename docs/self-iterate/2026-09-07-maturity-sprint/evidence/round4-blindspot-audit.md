# Round 4 审计 · 盲区终扫（子代理产出，含实机复现）

- B1 P1 FilterSnapshotCreate.release max_length=64 vs DB String(32)——v17.9.12 方言漂移修复漏网（cycle/view/metric 都改了，唯 release 漏）。实机复现 SQLite 静默入库。修：收 32 + schemas/ORM 列宽对齐守卫测试。
- B2 P2 JobSearchResponse.facets 声明但从不赋值（恒 null）；JobSearchRequest/JobStatsResponse 零引用死 schema（前者无 ge/le 约束，误用会绕过分页上限）。修：删除三者。
- B3 P2 /audit/review-queue 无分页无上限；cycles/salary/audit 三路由 70 用例中合计仅 1 条覆盖。修：limit(默认 100) + 冒烟用例入门禁。
- B4 P2 CI workflow 无 timeout-minutes（挂死占 360 分钟）、无 permissions 块、push 无分支过滤（每提交双跑）。修：job 级 timeout、顶层 permissions contents:read、push 限 main。
- B5 P2 deploy tar 排除清单漏 *.db——开发 wanyu.db（含 users 数据）会随载荷上生产。修：排除 *.db + ./tests + ./docs（载荷最小化）。
- B6 P2 systemd TimeoutStopSec=30 == gunicorn graceful_timeout=30——停服预算被整段吃满，在途请求 SIGKILL 截断。修：TimeoutStopSec=45。
- B7 P2 /health 无限流 + 每请求 DB 探活——公网刷可制造连接 churn。修：nginx /health 加宽松 limit_req（5r/s burst=10）。

零发现（实测）：EXCLUDED 清单与 git 现状一致；dev lock 闭包零漂移（干净 venv 实测）；Type=notify/KillMode 语义正确；/maintainable/ root 布局假设与网站实际结构吻合；cycles/salary/audit 无 N+1 与 None 崩溃路径；git 工作树零未跟踪残留。
