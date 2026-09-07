# Round 1 审计报告 · 镜头：部署链完整性（子代理产出，主控已抽查证伪）

状态：已收到；主控抽查 F1/F2/F3/F7/F10/F11 全部在源码对应行证实。
- F1 P0 日志目录权限：deploy.sh:110 mkdir（root）+ :139 chown 仅 $APP_DIR → LOG_DIR/PID_DIR root:root，www-data gunicorn 写日志 PermissionError，首次部署必死于 start_service。**证实**
- F2 P1 pg_get_userby：deploy.sh:90 调用不存在的函数（正确为 pg_get_userbyid），二次部署（DB 已存在分支）必炸。**证实**（v17.9.8 老 deploy.sh:83 同样错误，历史遗留）
- F3 P1 nginx alias+try_files（trac#97）双前缀 404：deploy.sh:212-214；根路径 :221 302 后同样 404；smoke 对静态站零覆盖。**证实**（线上现配置来自更早部署，未被本模板覆盖过，fresh-host 演练会踩中）
- F4 P2 lock 缺 uvloop（Windows 生成的平台盲区）。**证实**
- F5 P2 零回滚机制。**证实**
- F6 P2 certbot 无 --redirect（HTTP 明文不跳 HTTPS）。**证实**
- F7 P2 `cp -r .` 载荷污染（.venv/__pycache__/=0.4.0 全进生产）。**证实**
- F8 P2 linkage 未锁 gunicorn worker_class 字符串/lock 二进制存在性/unit+nginx 模板。**证实**
- F9 P2 部署链不产出管理员（create_admin.py 游离在链外）。**证实**
- F10 P2 apt 清单缺 curl/sudo（minimal 镜像中途炸）。**证实**
- F11 P2 deploy.sh:142 `|| true` + STATIC_DATA_PATH env/生成 .env 漂移点。**证实**

子代理同时确认无问题的项（证据在案）：
- heredoc 三个 import 符号全部真实存在且被 linkage 测试逐个锁定
- Type=notify 与 gunicorn 23.0.0 兼容（arbiter.py:160 原生 sd_notify）
- set -Eeuo pipefail + ERR trap 真实生效（除 :142 外无吞错）
- systemctl restart 正确；post_deploy_smoke 三段 fail-closed；DB 密码 hex 白名单防注入
- init_db 生产门 fail-closed 且 CI 有专门 job
