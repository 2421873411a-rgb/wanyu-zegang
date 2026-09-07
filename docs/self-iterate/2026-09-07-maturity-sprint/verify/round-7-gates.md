# Round 7 终审门禁输出（干净轮×2 判定）

审计判定：**双终门放行，收敛达成**。
- 部署/数据终审：零可复现 P0/P1。deploy.sh 字节级（25 个反斜杠直方图，唯一 backslash+n 为合法 printf 格式）+ tar dry-run（含诱饵 n/探针/db 全排除）+ main() 顺序推演 + pg_dump 保留实测（12 份删至恰好 10）+ OS 矩阵 case 实测 + RUNBOOK 逐命令 + 迁移链往返。
- 安全/API 终审：119/119 对抗探针 PASS。认证全链路（轮换/重用 family 撤销/登出）、SECRET_KEY 12/12 门禁、限流 20 并发=5×401+15×429、哑 bcrypt 时序对齐（354ms vs 354ms）、授权矩阵（未认证 14 端点 401/普通用户 admin 403/跨用户隔离）、导入 18 向量全 4xx 零写入、搜索转义正反、暴露面（bind 127.0.0.1/pip-audit/无栈泄露）。

九门：pytest 77+5skip（+1 per-IP 撞库门禁）、alembic 零漂移、bash -n、ruff clean、pip-audit clean、canonical core PASS、verify manifest PASS、e2e PASS、YAML OK。
本轮 P2×3 当场修复：postgres job timeout-minutes、OS 矩阵文案、per-IP 限流桶（login_ip 30/h + register_ip 10/h）。
