#!/bin/bash
# 皖域择岗 API 部署脚本 v2 —— Immutable Release 架构（v17.9.18）
#
# 架构（终审 P1：覆盖式部署的幽灵文件/依赖漂移/运行时可写 三连修复）：
#
#   /opt/wanyu/
#   ├── releases/<version>-<sha>/     每次部署全新目录：app/ + venv/（root 属主，www-data 只读）
#   ├── current -> releases/<...>     原子符号链接（ln -sfn + mv -T），回滚=切回上一链接
#   ├── backup/                       700 root：数据库快照 + 历史锚点
#   └── /var/log/wanyu                唯一运行时可写面
#
#   /etc/wanyu/wanyu.env              生产 secret（root:www-data 0640，与代码目录彻底分离）
#
# 不变量：
#   - 服务器文件系统 == Git release（每次全新目录，无覆盖残留/幽灵文件）
#   - venv 每 release 全新建（lock 说没有的包 venv 里就没有）
#   - 运行用户对代码/venv/secret 均无写权限（Persistence 面收窄）
#
set -Eeuo pipefail

BASE_DIR="/opt/wanyu"
RELEASES_DIR="${BASE_DIR}/releases"
BACKUP_ROOT="${BASE_DIR}/backup"
SHARED_LOG="/var/log/wanyu"
SECRET_ENV="/etc/wanyu/wanyu.env"
CURRENT_LINK="${BASE_DIR}/current"
SERVICE_NAME="wanyu-api"
STATIC_DATA_PATH="${STATIC_DATA_PATH:-/var/www/wan.kaogong.art/maintainable/data}"
DB_PASSWORD="${DB_PASSWORD:-}"
# 部署载荷 = 本脚本所在目录（wan-api/）；API 版本真源 = 载荷内 release.json
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
RELEASE_JSON="${SCRIPT_DIR}/release.json"
APP_VERSION=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

on_error() {
    local exit_code=$?
    log_error "部署失败：line=${BASH_LINENO[0]:-unknown} command=${BASH_COMMAND:-unknown} exit=${exit_code}"
    log_error "回滚：sudo ln -sfn <上一release目录> ${CURRENT_LINK} && sudo systemctl restart ${SERVICE_NAME}（见 docs/ops/RUNBOOK.md）"
    exit "$exit_code"
}
trap on_error ERR

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "请使用 root 用户或 sudo 运行此脚本"
        exit 1
    fi
}

check_prerequisites() {
    # 支持矩阵：python3.12 apt 包名钉死在 Ubuntu 24.04–25.x 官方源
    if [ -r /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        case "${ID:-}:${VERSION_ID:-}" in
            ubuntu:24.04|ubuntu:24.10|ubuntu:25.*) ;;
            *)
                log_error "support matrix: Ubuntu 24.04-25.x only (current: ${PRETTY_NAME:-unknown}); python3.12 apt package is pinned"
                exit 1
                ;;
        esac
    fi
    # 静态数据前置：缺失在预检阶段就中止（不在装完全部依赖后）
    if [ ! -d "${STATIC_DATA_PATH}/cycles" ]; then
        log_error "部署前置缺失：静态数据目录 ${STATIC_DATA_PATH}/cycles 不存在。请先放置 canonical 派生数据（cycles/ salary/ audit/），见 docs/ops/RUNBOOK.md"
        exit 1
    fi
    local cmd
    for cmd in curl sudo openssl python3 tar; do
        command -v "$cmd" >/dev/null || {
            log_error "缺少前置命令：$cmd"
            exit 1
        }
    done
}

install_dependencies() {
    log_info "安装系统依赖..."
    apt update
    apt install -y python3.12 python3.12-venv python3-pip \
        postgresql postgresql-contrib redis-server nginx certbot python3-certbot-nginx \
        curl sudo
    systemctl enable postgresql redis-server nginx
    systemctl start postgresql redis-server nginx
}

read_existing_db_password() {
    local env_file="${SECRET_ENV}"
    [ -f "$env_file" ] || return 0
    local line
    line="$(grep -m1 '^DATABASE_URL=' "$env_file" || true)"
    if [[ "$line" =~ postgresql\+asyncpg://wanyu_user:([^@]+)@ ]]; then
        DB_PASSWORD="${BASH_REMATCH[1]}"
    fi
}

setup_database() {
    log_info "配置 PostgreSQL 数据库..."
    local role_exists db_exists db_owner

    role_exists="$(sudo -u postgres psql -v ON_ERROR_STOP=1 -tAc \
        "SELECT 1 FROM pg_roles WHERE rolname='wanyu_user'")"
    if [ "$role_exists" = "1" ]; then
        log_info "wanyu_user 已存在，保留既有凭据"
        if [ -z "$DB_PASSWORD" ]; then
            read_existing_db_password
        fi
        if [ -z "$DB_PASSWORD" ]; then
            log_error "wanyu_user 已存在，但既未传 DB_PASSWORD，也无法从 ${SECRET_ENV} 读取旧密码"
            exit 1
        fi
    else
        if [ -f "${SECRET_ENV}" ]; then
            log_error "数据库角色不存在但旧 secret 文件仍存在；拒绝自动制造凭据漂移，请先核实恢复状态"
            exit 1
        fi
        DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -hex 16)}"
        if [[ ! "$DB_PASSWORD" =~ ^[0-9A-Fa-f]{16,128}$ ]]; then
            log_error "新建数据库角色时 DB_PASSWORD 必须为 16-128 位十六进制字符"
            exit 1
        fi
        sudo -u postgres psql -v ON_ERROR_STOP=1 -c \
            "CREATE USER wanyu_user WITH PASSWORD '${DB_PASSWORD}';"
    fi

    db_exists="$(sudo -u postgres psql -v ON_ERROR_STOP=1 -tAc \
        "SELECT 1 FROM pg_database WHERE datname='wanyu_db'")"
    if [ "$db_exists" = "1" ]; then
        db_owner="$(sudo -u postgres psql -v ON_ERROR_STOP=1 -tAc \
            "SELECT pg_catalog.pg_get_userbyid(datdba) FROM pg_database WHERE datname='wanyu_db'")"
        if [ "$db_owner" != "wanyu_user" ]; then
            log_error "wanyu_db owner=${db_owner}，期望 wanyu_user；拒绝继续部署"
            exit 1
        fi
    else
        sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE DATABASE wanyu_db OWNER wanyu_user;"
    fi

    sudo -u postgres psql -v ON_ERROR_STOP=1 -c \
        "GRANT ALL PRIVILEGES ON DATABASE wanyu_db TO wanyu_user;" >/dev/null
    sudo -u postgres psql -v ON_ERROR_STOP=1 -d wanyu_db -c \
        "CREATE EXTENSION IF NOT EXISTS pgcrypto;" >/dev/null
    sudo -u postgres psql -v ON_ERROR_STOP=1 -d wanyu_db -c \
        "CREATE EXTENSION IF NOT EXISTS pg_trgm;" >/dev/null
}

setup_secret_env() {
    # 生产 secret 与代码目录彻底分离：/etc/wanyu/wanyu.env（root:www-data 0640）
    sudo mkdir -p /etc/wanyu
    if [ ! -f "${SECRET_ENV}" ]; then
        if [ -z "$DB_PASSWORD" ]; then
            log_error "缺少 DB_PASSWORD，不能生成生产 secret"
            exit 1
        fi
        sudo tee "${SECRET_ENV}" > /dev/null <<EOF
DATABASE_URL=postgresql+asyncpg://wanyu_user:${DB_PASSWORD}@localhost:5432/wanyu_db
REDIS_URL=redis://localhost:6379/0
ENV=production
SECRET_KEY=$(openssl rand -hex 32)
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
CORS_ORIGINS=["https://wan.kaogong.art"]
STATIC_DATA_PATH=${STATIC_DATA_PATH}
RATE_LIMIT_BACKEND=redis
ALLOW_REGISTRATION=true
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@kaogong.art}
EOF
        log_info "生产 secret 已生成：${SECRET_ENV}"
    fi
    # APP_VERSION 每次部署强制刷新（.env 优先级高于派生默认，旧值会让 smoke 误判）
    if sudo grep -q '^APP_VERSION=' "${SECRET_ENV}"; then
        sudo sed -i "s/^APP_VERSION=.*/APP_VERSION=${APP_VERSION}/" "${SECRET_ENV}"
    else
        printf '%s\n' "APP_VERSION=${APP_VERSION}" | sudo tee -a "${SECRET_ENV}" > /dev/null
    fi
    sudo chown root:www-data "${SECRET_ENV}"
    sudo chmod 640 "${SECRET_ENV}"
}

build_release() {
    # Immutable release：全新目录 + 全新 venv，root 属主（www-data 只读）
    log_info "构建 release ${APP_VERSION}..."
    [ -f "$RELEASE_JSON" ] || { log_error "版本真源缺失：${RELEASE_JSON}"; exit 1; }
    APP_VERSION="$(python3 -c "import json; print(json.load(open('$RELEASE_JSON'))['release'])")"
    local git_sha
    git_sha="$(git -C "$SCRIPT_DIR" rev-parse --short HEAD 2>/dev/null || echo nodata)"
    RELEASE_DIR="${RELEASES_DIR}/${APP_VERSION}-${git_sha}"

    if [ -d "$RELEASE_DIR" ]; then
        log_warn "release 目录已存在（幂等重建）：${RELEASE_DIR}"
        sudo rm -rf "$RELEASE_DIR"
    fi
    sudo mkdir -p "$RELEASE_DIR/app" "$RELEASES_DIR"

    # 确定性载荷：脚本所在目录，排除开发垃圾
    cd "$SCRIPT_DIR"
    sudo tar --exclude='./.git' --exclude='./.venv' --exclude='./venv' \
        --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ruff_cache' \
        --exclude='*.pyc' --exclude='./*.db' --exclude='./_ci_migrate.db' \
        --exclude='_audit_probe*' --exclude='./tests' --exclude='./docs' \
        -cf - . | sudo tar -C "$RELEASE_DIR/app" -xf -

    # 权限：root 属主，全局可读不可写（运行用户无持久化写面）
    sudo find "$RELEASE_DIR/app" -type d -exec chmod 755 {} +
    sudo find "$RELEASE_DIR/app" -type f -exec chmod 644 {} +
    sudo chown -R root:root "$RELEASE_DIR"

    # 全新 venv：lock 说没有的包这里就没有（杜绝跨版本依赖漂移）
    sudo python3.12 -m venv "$RELEASE_DIR/venv"
    sudo "$RELEASE_DIR/venv/bin/pip" install --upgrade pip --quiet
    sudo "$RELEASE_DIR/venv/bin/pip" install -r "${RELEASE_DIR}/app/requirements.lock.txt" --quiet
    sudo "$RELEASE_DIR/venv/bin/pip" check
    sudo chown -R root:root "$RELEASE_DIR/venv"
    log_info "✓ release 构建完成（全新目录/全新 venv，root:root 只读）"
}

setup_service() {
    log_info "配置 systemd 服务..."
    sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" > /dev/null <<EOF
[Unit]
Description=WanYu Job API (FastAPI + Gunicorn, immutable release)
After=network.target postgresql.service redis-server.service
Requires=postgresql.service
Wants=redis-server.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=${CURRENT_LINK}/app
EnvironmentFile=${SECRET_ENV}
ExecStart=${CURRENT_LINK}/venv/bin/gunicorn app.main:app -c gunicorn.conf.py
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=on-failure
RestartSec=5
KillMode=mixed
TimeoutStopSec=45
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=${SHARED_LOG}

[Install]
WantedBy=multi-user.target
EOF
    sudo mkdir -p "$SHARED_LOG"
    sudo chown www-data:www-data "$SHARED_LOG"
    sudo chmod 750 "$SHARED_LOG"
    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_NAME"
}

atomic_switch() {
    # 原子切换 current 符号链接（ln -sfn + mv -T，绝无中间态）
    sudo ln -sfn "$RELEASE_DIR" "${CURRENT_LINK}.tmp"
    sudo mv -T "${CURRENT_LINK}.tmp" "${CURRENT_LINK}"
    [ "$(readlink "$CURRENT_LINK" 2>/dev/null)" = "$RELEASE_DIR" ] || {
        log_error "current 符号链接切换失败"
        exit 1
    }
    log_info "✓ current -> ${RELEASE_DIR}"
}

stop_service_window() {
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        sudo systemctl stop "$SERVICE_NAME"
        log_info "已停止 ${SERVICE_NAME}（部署窗口开始）"
    fi
}

prune_old_releases() {
    # 保留最近 3 个 release（当前 + 2 个回滚代际）
    sudo ls -1t "$RELEASES_DIR" 2>/dev/null | tail -n +4 | while read -r old; do
        [ "$(readlink "$CURRENT_LINK" 2>/dev/null)" = "${RELEASES_DIR}/$old" ] && continue
        sudo rm -rf "${RELEASES_DIR:?}/$old"
        log_info "已清理旧 release：$old"
    done
}

setup_backup_automation() {
    # PG 自动灾备：daily pg_dump + sha256 + 7daily/4weekly/3monthly 保留（终审 P1）
    sudo tee /etc/wanyu/wanyu-backup.sh > /dev/null <<'BKEOF'
#!/bin/bash
# 皖域 DB 自动备份：daily 全量 + sha256 + 保留 7 daily / 4 weekly / 3 monthly
set -Eeuo pipefail
BASE=/opt/wanyu/backup
STAMP=$(date +%Y%m%d-%H%M%S)
DOW=$(date +%u)
DOM=$(date +%d)
mkdir -p "$BASE/daily" "$BASE/weekly" "$BASE/monthly"
OUT="$BASE/daily/wanyu_db-$STAMP.dump"
sudo -u postgres pg_dump -Fc wanyu_db > "$OUT"
[ -s "$OUT" ] || { echo "EMPTY BACKUP: $OUT"; exit 1; }
chmod 600 "$OUT"
sha256sum "$OUT" > "$OUT.sha256"
if [ "$DOW" = "7" ]; then cp "$OUT" "$BASE/weekly/"; fi
if [ "$DOM" = "01" ]; then cp "$OUT" "$BASE/monthly/"; fi
ls -1t "$BASE/daily"  | grep -v '.sha256' | tail -n +8 | while read -r f; do rm -f "$BASE/daily/$f"  "$BASE/daily/$f.sha256";  done
ls -1t "$BASE/weekly" | grep -v '.sha256' | tail -n +5 | while read -r f; do rm -f "$BASE/weekly/$f" "$BASE/weekly/$f.sha256"; done
ls -1t "$BASE/monthly"| grep -v '.sha256' | tail -n +4 | while read -r f; do rm -f "$BASE/monthly/$f" "$BASE/monthly/$f.sha256"; done
echo "backup ok: $OUT"
BKEOF
    sudo chmod 750 /etc/wanyu/wanyu-backup.sh
    sudo tee /etc/systemd/system/wanyu-backup.service > /dev/null <<'BSEOF'
[Unit]
Description=WanYu DB daily backup

[Service]
Type=oneshot
ExecStart=/etc/wanyu/wanyu-backup.sh
BSEOF
    sudo tee /etc/systemd/system/wanyu-backup.timer > /dev/null <<'BTEOF'
[Unit]
Description=Daily WanYu DB backup at 03:00

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
BTEOF
    sudo systemctl daemon-reload
    sudo systemctl enable --now wanyu-backup.timer
    log_info "✓ DB 备份定时器已启用（daily 03:00，7daily/4weekly/3monthly）"
}

setup_logrotate() {
    log_info "配置日志轮转..."
    sudo tee /etc/logrotate.d/wanyu-api > /dev/null <<'LROTEOF'
/var/log/wanyu/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
LROTEOF
}

setup_nginx() {
    log_info "配置 Nginx（全新机模板；多站点现网服务器请按 RUNBOOK 分步适配）..."
    sudo tee /etc/nginx/sites-available/wan.kaogong.art > /dev/null <<'NGXEOF'
upstream wanyu_api {
    server 127.0.0.1:8000;
    keepalive 32;
}
limit_req_zone $binary_remote_addr zone=wanapi:10m rate=30r/s;
server {
    listen 80;
    listen [::]:80;
    server_name wan.kaogong.art;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location /api/ {
        limit_req zone=wanapi burst=60 nodelay;
        client_max_body_size 64m;
        proxy_pass http://wanyu_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_http_version 1.1;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
        add_header Cache-Control "no-store, no-cache, must-revalidate";
    }
    location = /health {
        limit_req zone=wanapi burst=10 nodelay;
        proxy_pass http://wanyu_api/health;
        proxy_set_header Host $host;
        access_log off;
    }
    location /maintainable/ {
        alias /var/www/wan.kaogong.art/maintainable/;
        try_files $uri $uri/ =404;
        gzip on;
        gzip_vary on;
        gzip_comp_level 6;
        gzip_min_length 1024;
        gzip_types text/plain text/css application/javascript application/json image/svg+xml;
    }
    location = / { return 302 /maintainable/index.html; }
}
NGXEOF
    sudo ln -sf /etc/nginx/sites-available/wan.kaogong.art /etc/nginx/sites-enabled/
    nginx -t
    sudo systemctl reload nginx
}

setup_ssl() {
    log_info "配置 SSL 证书..."
    sudo mkdir -p /var/www/certbot
    certbot --nginx -d wan.kaogong.art --non-interactive --agree-tos --redirect \
        --email admin@kaogong.art
    nginx -t
    sudo systemctl reload nginx
    sudo systemctl enable certbot.timer
}

import_data() {
    log_info "导入数据（使用新 release venv）..."
    # 迁移前数据库快照（数据级还原点）
    sudo mkdir -p "$BACKUP_ROOT"
    sudo chmod 700 "$BACKUP_ROOT"
    local dump_file
    dump_file="${BACKUP_ROOT}/wanyu_db-$(date +%Y%m%d-%H%M%S).dump"
    sudo -u postgres pg_dump -Fc wanyu_db > /tmp/.wanyu_predump
    sudo mv /tmp/.wanyu_predump "$dump_file"
    sudo chmod 600 "$dump_file"
    if [ ! -s "$dump_file" ]; then
        log_error "pg_dump 产物为空，拒绝在无数据级还原点的情况下执行迁移"
        exit 1
    fi
    log_info "✓ 数据库快照：${dump_file}"

    # 迁移锚点：重部署时记录 alembic 当前版本
    if sudo [ -f "${BACKUP_ROOT}/LATEST" ]; then
        sudo "${RELEASE_DIR}/venv/bin/alembic" current > "${BACKUP_ROOT}/$(sudo cat "${BACKUP_ROOT}/LATEST")/alembic-before.txt"
    fi

    sudo -u www-data "${RELEASE_DIR}/venv/bin/alembic" upgrade head
    sudo -u www-data "${RELEASE_DIR}/venv/bin/python" - <<'PY'
import asyncio
from app.database import init_db, async_session_factory
from app.services.import_service import import_all_data

async def main():
    await init_db()
    async with async_session_factory() as db:
        results = await import_all_data(db, data_path=None)
        cycles = [results.get(f"cycle_{year}") for year in ("2024", "2025", "2026")]
        if not any(cycles):
            raise RuntimeError("三个周期均未导入，拒绝启动空镜像")
        print("导入结果:", {k: v for k, v in results.items()})

asyncio.run(main())
PY
    local post_dump
    post_dump="${BACKUP_ROOT}/wanyu_db-post-import-$(date +%Y%m%d-%H%M%S).dump"
    sudo -u postgres pg_dump -Fc wanyu_db > /tmp/.wanyu_postdump
    sudo mv /tmp/.wanyu_postdump "$post_dump"
    sudo chmod 600 "$post_dump"
    log_info "✓ 导入后快照：${post_dump}"
}

start_service() {
    log_info "启动服务..."
    sudo systemctl restart "$SERVICE_NAME"
    sudo systemctl is-active --quiet "$SERVICE_NAME"
    systemctl status "$SERVICE_NAME" --no-pager | head -3
}

post_deploy_smoke() {
    log_info "部署后 smoke 测试..."
    local i actual_version jobs_count code

    for i in {1..15}; do
        if curl -sf http://127.0.0.1:8000/health >/dev/null; then
            break
        fi
        sleep 1
    done
    curl -sf http://127.0.0.1:8000/health >/dev/null || {
        log_error "API /health 失败"; exit 1;
    }

    actual_version="$(curl -sf http://127.0.0.1:8000/health | \
        python3 -c "import sys,json; print(json.load(sys.stdin).get('version',''))")"
    if [ "$actual_version" != "${APP_VERSION}" ]; then
        log_error "版本不一致：/health=${actual_version}，部署版本=${APP_VERSION}——部署未真正生效"
        exit 1
    fi

    if [ -f /etc/nginx/sites-enabled/wan.kaogong.art ]; then
        curl -sf https://wan.kaogong.art/health >/dev/null || {
            log_error "公网 HTTPS /health 失败"; exit 1;
        }
        code="$(curl -s -o /dev/null -w '%{http_code}' https://wan.kaogong.art/)"
        if [ "$code" != "200" ]; then
            log_error "静态站返回 ${code}（期望 200）"; exit 1;
        fi
        code="$(curl -s -o /dev/null -w '%{http_code}' http://wan.kaogong.art/)"
        if [ "$code" != "301" ]; then
            log_error "HTTP 未强制跳转 HTTPS（返回 ${code}，期望 301）"; exit 1;
        fi
    else
        log_warn "未检测到 nginx 站点配置，跳过公网断言（分步适配模式）"
    fi

    jobs_count="$(curl -sf "http://127.0.0.1:8000/api/v1/jobs/search?cycle=2026&page_size=1" | \
        python3 -c "import sys,json; print(json.load(sys.stdin).get('total',0))")"
    if ! [[ "$jobs_count" =~ ^[0-9]+$ ]] || [ "$jobs_count" -le 0 ]; then
        log_error "岗位数据为空或响应非法：${jobs_count}"
        exit 1
    fi
    log_info "✓ 健康/版本(${actual_version})/岗位(${jobs_count}) smoke 全通过"
}

bootstrap_admin() {
    cd "${CURRENT_LINK}/app"
    if [ -n "${ADMIN_BOOTSTRAP_PASSWORD:-}" ]; then
        sudo -u www-data "${CURRENT_LINK}/venv/bin/python" scripts/create_admin.py \
            --email "${ADMIN_EMAIL:-admin@kaogong.art}" \
            --username admin \
            --password "$ADMIN_BOOTSTRAP_PASSWORD"
        log_info "✓ 管理员引导完成（${ADMIN_EMAIL:-admin@kaogong.art}）"
    else
        log_warn "未设置 ADMIN_BOOTSTRAP_PASSWORD，跳过管理员引导。生产管理员必须补做："
        log_warn "  cd ${CURRENT_LINK}/app && sudo -u www-data ${CURRENT_LINK}/venv/bin/python scripts/create_admin.py --email ${ADMIN_EMAIL:-admin@kaogong.art} --username admin"
    fi
}

main() {
    log_info "开始部署皖域择岗 API（Immutable Release）..."
    check_root
    check_prerequisites
    install_dependencies
    setup_database
    setup_secret_env
    build_release
    setup_service
    setup_logrotate
    setup_backup_automation
    # 全新机才配 nginx/ssl（现网多站点服务器的 nginx 由 RUNBOOK 分步适配）
    if [ ! -f /etc/nginx/sites-available/wan.kaogong.art ]; then
        setup_nginx
        setup_ssl
    fi
    stop_service_window
    atomic_switch
    import_data
    start_service
    post_deploy_smoke
    bootstrap_admin
    prune_old_releases
    log_info "部署完成：current -> ${RELEASE_DIR}"
    log_info "API https://wan.kaogong.art/api/docs · health https://wan.kaogong.art/health"
}

# --build-only：仅构建 release 目录（Upgrade Drift 演练复用真实构建逻辑；
# WANYU_RELEASES_DIR 可重定向演练输出，绝不触碰生产 current/service）
if [ "${1:-}" = "--build-only" ]; then
    check_root
    [ -f "$RELEASE_JSON" ] || { log_error "版本真源缺失：${RELEASE_JSON}"; exit 1; }
    APP_VERSION="$(python3 -c "import json; print(json.load(open('$RELEASE_JSON'))['release'])")"
    git_sha="$(git -C "$SCRIPT_DIR" rev-parse --short HEAD 2>/dev/null || echo nodata)"
    RELEASES_DIR="${WANYU_RELEASES_DIR:-${RELEASES_DIR}}"
    RELEASE_DIR="${RELEASES_DIR}/${APP_VERSION}-${git_sha}-drill"
    if [ -d "$RELEASE_DIR" ]; then
        sudo rm -rf "$RELEASE_DIR"
    fi
    sudo mkdir -p "$RELEASE_DIR/app"
    cd "$SCRIPT_DIR"
    sudo tar --exclude='./.git' --exclude='./.venv' --exclude='./venv'         --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ruff_cache'         --exclude='*.pyc' --exclude='./*.db'         -cf - . | sudo tar -C "$RELEASE_DIR/app" -xf -
    sudo find "$RELEASE_DIR/app" -type d -exec chmod 755 {} +
    sudo find "$RELEASE_DIR/app" -type f -exec chmod 644 {} +
    sudo chown -R root:root "$RELEASE_DIR"
    sudo python3.12 -m venv "$RELEASE_DIR/venv"
    sudo "$RELEASE_DIR/venv/bin/pip" install --upgrade pip --quiet
    sudo "$RELEASE_DIR/venv/bin/pip" install -r "${RELEASE_DIR}/app/requirements.lock.txt" --quiet
    sudo "$RELEASE_DIR/venv/bin/pip" check
    sudo chown -R root:root "$RELEASE_DIR/venv"
    log_info "build-only 完成：${RELEASE_DIR}"
    exit 0
fi

main "$@"
