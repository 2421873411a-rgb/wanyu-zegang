#!/bin/bash
# 皖域择岗 API 部署脚本

set -Eeuo pipefail

APP_DIR="/opt/wanyu/api"
BACKUP_ROOT="/opt/wanyu/backup"
STATIC_DATA_PATH="${STATIC_DATA_PATH:-/opt/wanyu/static/maintainable/data}"
LOG_DIR="/var/log/wanyu"
SERVICE_NAME="wanyu-api"
DB_PASSWORD="${DB_PASSWORD:-}"
# 部署载荷 = 本脚本所在目录（wan-api/）；API 版本真源 = 载荷内 release.json（wanyu-api-release/v1）
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
RELEASE_JSON="${SCRIPT_DIR}/release.json"

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
    log_error "如需回滚见 项目源码/wan-api/docs/ops/RUNBOOK.md（备份位于 ${BACKUP_ROOT}）"
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
    local cmd
    for cmd in curl sudo openssl python3 tar; do
        command -v "$cmd" >/dev/null || {
            log_error "缺少前置命令：$cmd（minimal 镜像请先 apt install curl sudo openssl）"
            exit 1
        }
    done
}

install_dependencies() {
    log_info "安装系统依赖..."
    apt update
    # curl/sudo 是本脚本自身依赖（smoke 与 psql 提权），minimal 镜像不保证预装。
    apt install -y python3.12 python3.12-venv python3-pip \
        postgresql postgresql-contrib redis-server nginx certbot python3-certbot-nginx \
        curl sudo
    systemctl enable postgresql redis-server nginx
    systemctl start postgresql redis-server nginx
}

read_existing_db_password() {
    local env_file="${APP_DIR}/.env"
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
            log_error "wanyu_user 已存在，但既未传 DB_PASSWORD，也无法从 ${APP_DIR}/.env 读取旧密码"
            exit 1
        fi
    else
        if [ -f "${APP_DIR}/.env" ]; then
            log_error "数据库角色不存在但旧 .env 仍存在；拒绝自动制造凭据漂移，请先核实恢复状态"
            exit 1
        fi
        DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -hex 16)}"
        # 新建角色时密码由本脚本生成 hex，避免 SQL quoting 注入面。
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

    # 这些都是生产前置条件：任何失败都必须中止，不能 || true 吞掉。
    sudo -u postgres psql -v ON_ERROR_STOP=1 -c \
        "GRANT ALL PRIVILEGES ON DATABASE wanyu_db TO wanyu_user;"
    sudo -u postgres psql -v ON_ERROR_STOP=1 -d wanyu_db -c \
        "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
    sudo -u postgres psql -v ON_ERROR_STOP=1 -d wanyu_db -c \
        "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
}

backup_previous_release() {
    # 回滚脚手架：换血前把旧版本代码（不含 venv，可由 lock 重建）快照到 BACKUP_ROOT。
    # 数据库回滚锚点（alembic 版本戳）在 import_data 升级前补记。
    local ts dest
    if [ -d "$APP_DIR" ] && [ -n "$(ls -A "$APP_DIR" 2>/dev/null)" ]; then
        ts="$(date +%Y%m%d-%H%M%S)"
        dest="${BACKUP_ROOT}/${ts}"
        mkdir -p "$dest"
        tar -C "$APP_DIR" --exclude='./venv' --exclude='./.env' -cf - . | tar -C "$dest" -xf -
        echo "$ts" > "${BACKUP_ROOT}/LATEST"
        log_info "已备份旧版本代码到 ${dest}（不含 venv/.env）"
    else
        log_info "首次部署：无旧版本可备份"
    fi
}

setup_app_dir() {
    log_info "创建应用目录..."
    mkdir -p "$APP_DIR" "$LOG_DIR"
    # P0：gunicorn 以 www-data 运行，日志目录必须归 www-data 可写，否则启动即崩。
    chown www-data:www-data "$LOG_DIR"
    chmod 750 "$LOG_DIR"

    # 版本真源：部署必须携带源仓 release.json 声明的版本（缺失即拒绝——不可证明的部署不做）。
    [ -f "$RELEASE_JSON" ] || { log_error "版本真源缺失：${RELEASE_JSON}"; exit 1; }
    APP_VERSION="$(python3 -c "import json; print(json.load(open('$RELEASE_JSON'))['release'])")"
    log_info "部署版本：${APP_VERSION}"

    # 确定性载荷：始终部署脚本所在目录，排除开发垃圾（venv/git/缓存）。
    cd "$SCRIPT_DIR"
    tar --exclude='./.git' --exclude='./.venv' --exclude='./venv' \
        --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ruff_cache' \
        --exclude='*.pyc' --exclude='./_ci_migrate.db' -cf - . | tar -C "$APP_DIR" -xf -
    cd "$APP_DIR"

    # 权限扫除必须在 venv 创建之前：644 扫除会抹掉 venv 可执行位（历史上靠 || true 兜底的根因）。
    chown -R www-data:www-data "$APP_DIR"
    find "$APP_DIR" -type d -exec chmod 755 {} +
    find "$APP_DIR" -type f -exec chmod 644 {} +
    chmod 755 "$APP_DIR/deploy.sh"

    python3.12 -m venv venv
    chown -R www-data:www-data "$APP_DIR/venv"
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.lock.txt
    pip check

    if [ ! -f "${APP_DIR}/.env" ]; then
        if [ -z "$DB_PASSWORD" ]; then
            log_error "缺少 DB_PASSWORD，不能生成生产 .env"
            exit 1
        fi
        cat > "${APP_DIR}/.env" << EOF
DATABASE_URL=postgresql+asyncpg://wanyu_user:${DB_PASSWORD}@localhost:5432/wanyu_db
REDIS_URL=redis://localhost:6379/0
ENV=production
SECRET_KEY=$(openssl rand -hex 32)
APP_VERSION=${APP_VERSION}
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
CORS_ORIGINS=["https://wan.kaogong.art","http://localhost:8765"]
STATIC_DATA_PATH=${STATIC_DATA_PATH}
ALLOW_REGISTRATION=true
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@kaogong.art}
EOF
    fi
    chown www-data:www-data "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"

    # 在 systemd 接管前先证明 Gunicorn 配置可以加载。
    sudo -u www-data "$APP_DIR/venv/bin/gunicorn" --check-config app.main:app -c gunicorn.conf.py
}

setup_service() {
    log_info "配置 systemd 服务..."
    cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=WanYu Job API (FastAPI + Gunicorn)
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/venv/bin/gunicorn app.main:app -c gunicorn.conf.py
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=on-failure
RestartSec=5
KillMode=mixed
TimeoutStopSec=30
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=${LOG_DIR} ${APP_DIR}

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
}

setup_nginx() {
    log_info "配置 Nginx（HTTP-only 阶段）..."
    # 注意：/maintainable/ 必须用 root 而非 alias——alias+try_files 是 nginx 已知缺陷
    # （trac #97，URI 拼接产生双前缀 404）。root 要求父目录名与 URI 前缀一致：
    # /opt/wanyu/static/maintainable/ ← /maintainable/，天然吻合。
    cat > /etc/nginx/sites-available/wan.kaogong.art << 'EOF'
upstream wanyu_api {
    server 127.0.0.1:8000;
    keepalive 32;
}
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
server {
    listen 80;
    listen [::]:80;
    server_name wan.kaogong.art;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location /api/ {
        limit_req zone=api burst=60 nodelay;
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
        proxy_pass http://wanyu_api/health;
        proxy_set_header Host $host;
        access_log off;
    }
    location /maintainable/ {
        root /opt/wanyu/static;
        try_files $uri $uri/ =404;
        gzip on;
        gzip_vary on;
        gzip_comp_level 6;
        gzip_min_length 1024;
        gzip_types text/plain text/css application/javascript application/json image/svg+xml;
    }
    location = / { return 302 /maintainable/index.html; }
}
EOF
    ln -sf /etc/nginx/sites-available/wan.kaogong.art /etc/nginx/sites-enabled/
    nginx -t
    systemctl reload nginx
}

setup_ssl() {
    log_info "配置 SSL 证书..."
    mkdir -p /var/www/certbot
    # --redirect：certbot 追加 443 server 块的同时强制 80 → 443 跳转；
    # 缺省（非交互默认不跳转）会让 token 暴露在明文 HTTP。
    certbot --nginx -d wan.kaogong.art --non-interactive --agree-tos --redirect \
        --email admin@kaogong.art
    nginx -t
    systemctl reload nginx
    systemctl enable certbot.timer
}

import_data() {
    log_info "导入数据..."
    if [ ! -d "${STATIC_DATA_PATH}/cycles" ]; then
        log_error "静态数据目录不存在：${STATIC_DATA_PATH}/cycles"
        exit 1
    fi
    cd "$APP_DIR"
    source venv/bin/activate

    # 回滚锚点：升级迁移前记录当前 alembic 版本（仅重部署时有备份目录）。
    if [ -f "${BACKUP_ROOT}/LATEST" ]; then
        alembic current > "${BACKUP_ROOT}/$(cat "${BACKUP_ROOT}/LATEST")/alembic-before.txt"
    fi

    alembic upgrade head
    python - <<'PY'
import asyncio
from app.database import init_db, async_session_factory
from app.services.import_service import import_all_data

async def main():
    await init_db()
    async with async_session_factory() as db:
        results = await import_all_data(db)
        cycles = [results.get(f"cycle_{year}") for year in ("2024", "2025", "2026")]
        if not any(cycles):
            raise RuntimeError("三个周期均未导入，拒绝启动空镜像")
        print("导入结果:", results)

asyncio.run(main())
PY
}

bootstrap_admin() {
    cd "$APP_DIR"
    source venv/bin/activate
    if [ -n "${ADMIN_BOOTSTRAP_PASSWORD:-}" ]; then
        python scripts/create_admin.py \
            --email "${ADMIN_EMAIL:-admin@kaogong.art}" \
            --username admin \
            --password "$ADMIN_BOOTSTRAP_PASSWORD"
        log_info "✓ 管理员引导完成（${ADMIN_EMAIL:-admin@kaogong.art}）"
    else
        log_warn "未设置 ADMIN_BOOTSTRAP_PASSWORD，跳过管理员引导。生产管理员是唯一管理入口，必须补做："
        log_warn "  cd ${APP_DIR} && source venv/bin/activate && python scripts/create_admin.py --email ${ADMIN_EMAIL:-admin@kaogong.art} --username admin"
    fi
}

start_service() {
    log_info "启动/重启服务..."
    systemctl restart "$SERVICE_NAME"
    systemctl is-active --quiet "$SERVICE_NAME"
    systemctl status "$SERVICE_NAME" --no-pager
}

post_deploy_smoke() {
    log_info "部署后 smoke 测试..."
    local i code expected_version actual_version jobs_count

    for i in {1..15}; do
        if curl -sf http://127.0.0.1:8000/health >/dev/null; then
            break
        fi
        sleep 1
    done
    curl -sf http://127.0.0.1:8000/health >/dev/null || {
        log_error "API /health 失败"; exit 1;
    }

    # 版本一致性：跑起来的必须是部署时注入的版本（防止 restart 落空/旧进程残留）。
    actual_version="$(curl -sf http://127.0.0.1:8000/health | \
        python3 -c "import sys,json; print(json.load(sys.stdin).get('version',''))")"
    if [ "$actual_version" != "${APP_VERSION}" ]; then
        log_error "版本不一致：/health=${actual_version}，部署版本=${APP_VERSION}——部署未真正生效"
        exit 1
    fi

    curl -sf https://wan.kaogong.art/health >/dev/null || {
        log_error "公网 HTTPS /health 失败"; exit 1;
    }

    # 静态站可达（root 指令修复后必须 200）+ HTTP 强制跳转 HTTPS。
    code="$(curl -s -o /dev/null -w '%{http_code}' https://wan.kaogong.art/maintainable/index.html)"
    if [ "$code" != "200" ]; then
        log_error "静态站 /maintainable/index.html 返回 ${code}（期望 200）"; exit 1;
    fi
    code="$(curl -s -o /dev/null -w '%{http_code}' http://wan.kaogong.art/maintainable/index.html)"
    if [ "$code" != "301" ]; then
        log_error "HTTP 未强制跳转 HTTPS（返回 ${code}，期望 301）"; exit 1;
    fi

    jobs_count="$(curl -sf http://127.0.0.1:8000/api/v1/jobs/search | \
        python3 -c "import sys,json; print(json.load(sys.stdin).get('total',0))")"
    if ! [[ "$jobs_count" =~ ^[0-9]+$ ]] || [ "$jobs_count" -le 0 ]; then
        log_error "岗位数据为空或响应非法：${jobs_count}"
        exit 1
    fi
    log_info "✓ 健康/HTTPS/版本(${actual_version})/静态站/强制跳转/岗位数据(${jobs_count}) smoke 全通过"
}

main() {
    log_info "开始部署皖域择岗 API..."
    check_root
    check_prerequisites
    install_dependencies
    setup_database
    backup_previous_release
    setup_app_dir
    setup_service
    setup_nginx
    setup_ssl
    import_data
    start_service
    post_deploy_smoke
    bootstrap_admin
    log_info "部署完成：API https://wan.kaogong.art/api/docs · health https://wan.kaogong.art/health"
}

main "$@"
