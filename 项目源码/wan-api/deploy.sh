#!/bin/bash
# 皖域择岗 API 部署脚本
# 用于在服务器上部署FastAPI应用

set -e

# 配置变量
APP_DIR="/opt/wanyu/api"
# P1-9：静态数据目录（canonical 产物部署位置）——bash 脚本自用，不依赖 .env
STATIC_DATA_PATH="${STATIC_DATA_PATH:-/opt/wanyu/static/maintainable/data}"
VENV_DIR="${APP_DIR}/venv"
LOG_DIR="/var/log/wanyu"
PID_DIR="/var/run/wanyu"
SERVICE_NAME="wanyu-api"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为root用户
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "请使用root用户或sudo运行此脚本"
        exit 1
    fi
}

# 安装系统依赖
install_dependencies() {
    log_info "安装系统依赖..."
    
    apt update
    apt install -y python3.12 python3.12-venv python3-pip \
        postgresql postgresql-contrib \
        redis-server \
        nginx certbot python3-certbot-nginx
    
    # 启动服务
    systemctl enable postgresql redis-server nginx
    systemctl start postgresql redis-server nginx
}

# 配置数据库（幂等：role/DB 已存在时保留旧凭据，不覆盖密码）
setup_database() {
    log_info "配置PostgreSQL数据库..."

    # 检查 role 是否已存在
    ROLE_EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='wanyu_user'" 2>/dev/null)
    if [ "$ROLE_EXISTS" = "1" ]; then
        log_info "wanyu_user 已存在，保留旧凭据"
        # 从 .env 读取已有密码（如果 .env 存在）
        if [ -f "${APP_DIR}/.env" ]; then
            DB_PASSWORD=$(grep DATABASE_URL "${APP_DIR}/.env" | sed 's/.*:\/\/wanyu_user:\([^@]*\)@.*/\1/')
        fi
        if [ -z "$DB_PASSWORD" ]; then
            log_error "wanyu_user 已存在但无法从 .env 读取密码——请手动设置 DB_PASSWORD"
            exit 1
        fi
    else
        DB_PASSWORD="$(openssl rand -hex 16)"
        sudo -u postgres psql -c "CREATE USER wanyu_user WITH PASSWORD '${DB_PASSWORD}';"
    fi

    # 检查 DB 是否已存在
    DB_EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='wanyu_db'" 2>/dev/null)
    if [ "$DB_EXISTS" = "1" ]; then
        log_info "wanyu_db 已存在"
        # 验证 owner
        DB_OWNER=$(sudo -u postgres psql -tAc "SELECT pg_catalog.pg_get_userby(datdba) FROM pg_database WHERE datname='wanyu_db'" 2>/dev/null)
        if [ "$DB_OWNER" != "wanyu_user" ]; then
            log_warn "wanyu_db owner=$DB_OWNER，期望 wanyu_user——请手动 ALTER DATABASE"
        fi
    else
        sudo -u postgres psql -c "CREATE DATABASE wanyu_db OWNER wanyu_user;"
    fi

    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE wanyu_db TO wanyu_user;" 2>/dev/null || true
    sudo -u postgres psql -d wanyu_db -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;" 2>/dev/null || true
    sudo -u postgres psql -d wanyu_db -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;" 2>/dev/null || true
}

# 创建应用目录
setup_app_dir() {
    log_info "创建应用目录..."
    
    mkdir -p ${APP_DIR}
    mkdir -p ${LOG_DIR}
    mkdir -p ${PID_DIR}
    
    # 复制应用文件
    cp -r . ${APP_DIR}/
    
    # 创建虚拟环境
    cd ${APP_DIR}
    python3.12 -m venv venv
    source venv/bin/activate
    
    # 安装依赖
    pip install --upgrade pip
    pip install -r requirements.lock.txt
    
    # 创建环境变量文件
    if [ ! -f ${APP_DIR}/.env ]; then
        # P0-8: 无引号 heredoc——SECRET_KEY 的 $(openssl rand) 在此展开写入随机值，而非字面量；DB 密码用本轮生成的随机密码
        cat > ${APP_DIR}/.env << EOF
DATABASE_URL=postgresql+asyncpg://wanyu_user:${DB_PASSWORD}@localhost:5432/wanyu_db
REDIS_URL=redis://localhost:6379/0
ENV=production
SECRET_KEY=$(openssl rand -hex 32)
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
CORS_ORIGINS=["https://wan.kaogong.art","http://localhost:8765"]
STATIC_DATA_PATH=/opt/wanyu/static/maintainable/data
ALLOW_REGISTRATION=true
ADMIN_EMAIL=admin@kaogong.art
EOF
    fi
    
    # 设置权限（v17.9.1 S0：目录可 755，但 .env 内含 DB 密码与 JWT SECRET_KEY，
    # 必须单独收紧为 600 且属主 www-data，否则同机其他用户可读密钥）
    chown -R www-data:www-data ${APP_DIR}
    chmod -R 755 ${APP_DIR}
    chown www-data:www-data ${APP_DIR}/.env
    chmod 600 ${APP_DIR}/.env
}

# 配置systemd服务
setup_service() {
    log_info "配置systemd服务..."
    
    cat > /etc/systemd/system/${SERVICE_NAME}.service << 'EOF'
[Unit]
Description=WanYu Job API (FastAPI + Gunicorn)
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/wanyu/api
ExecStart=/opt/wanyu/api/venv/bin/gunicorn app.main:app \
    -c gunicorn.conf.py
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=5
KillMode=mixed
TimeoutStopSec=30

# 安全加固
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/log/wanyu /opt/wanyu/api

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable ${SERVICE_NAME}
}

# 配置Nginx（P1-9：先 HTTP-only，certbot 拿证书后再写 HTTPS 配置）
setup_nginx() {
    log_info "配置Nginx（HTTP-only 阶段）..."

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

    # certbot 验证路径
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # API 代理（HTTP 阶段即可用）
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

    # 健康检查
    location = /health {
        proxy_pass http://wanyu_api/health;
        proxy_set_header Host $host;
        access_log off;
    }

    # 静态站
    location /maintainable/ {
        alias /opt/wanyu/static/maintainable/;
        try_files $uri $uri/ =404;
        gzip on;
        gzip_vary on;
        gzip_comp_level 6;
        gzip_min_length 1024;
        gzip_types text/plain text/css application/javascript application/json image/svg+xml;
    }

    location = / {
        return 302 /maintainable/index.html;
    }
}
EOF

    ln -sf /etc/nginx/sites-available/wan.kaogong.art /etc/nginx/sites-enabled/
    nginx -t && systemctl reload nginx
}

# 配置SSL证书（HTTP server block 已存在，certbot --nginx 自动升级为 HTTPS）
setup_ssl() {
    log_info "配置SSL证书..."

    mkdir -p /var/www/certbot
    certbot --nginx -d wan.kaogong.art --non-interactive --agree-tos --email admin@kaogong.art
    systemctl enable certbot.timer
}

# 部署后 smoke 测试
post_deploy_smoke() {
    log_info "部署后 smoke 测试..."

    # 等待服务启动
    sleep 3

    # API 健康检查
    if curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then
        log_info "✓ API /health 200"
    else
        log_error "✗ API /health 失败"
        exit 1
    fi

    # Nginx HTTPS 健康检查
    if curl -sf https://wan.kaogong.art/health > /dev/null 2>&1; then
        log_info "✓ Nginx HTTPS /health 200"
    else
        log_warn "Nginx HTTPS /health 失败（可能证书未生效）"
    fi

    # 数据计数 smoke（至少应有岗位数据）
    JOBS_COUNT=$(curl -sf http://127.0.0.1:8000/api/v1/jobs/search 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('total',0))" 2>/dev/null || echo "0")
    if [ "$JOBS_COUNT" -gt "0" ] 2>/dev/null; then
        log_info "✓ 岗位数据: ${JOBS_COUNT} 条"
    else
        log_error "✗ 岗位数据为空——导入可能失败"
        exit 1
    fi
}

# 导入数据
import_data() {
    log_info "导入数据..."

    # P1-9：静态数据目录必须存在（canonical 产物已部署到位）——缺失即 fail-closed，
    # 不启动一个空数据库 API（否则 /jobs/search 无数据、导入静默跳过）
    if [ ! -d "${STATIC_DATA_PATH}/cycles" ]; then
        log_error "静态数据目录不存在：${STATIC_DATA_PATH}/cycles"
        log_error "请先部署 canonical 产物到 ${STATIC_DATA_PATH}（deploy_wan.sh 或手动同步 网站/data/）"
        exit 1
    fi

    cd ${APP_DIR}
    source venv/bin/activate

    # 运行数据库迁移
    alembic upgrade head

    # 导入数据
    python -c "
import asyncio
from app.database import init_db, async_session_factory
from app.services.import_service import import_all_data

async def main():
    await init_db()
    async with async_session_factory() as db:
        results = await import_all_data(db)
        print('导入结果:', results)

asyncio.run(main())
"
}

# 启动服务
start_service() {
    log_info "启动服务..."
    
    systemctl start ${SERVICE_NAME}
    systemctl status ${SERVICE_NAME}
}

# 主函数
main() {
    log_info "开始部署皖域择岗 API..."
    
    check_root
    install_dependencies
    setup_database
    setup_app_dir
    setup_service
    # P1-9：先写 HTTP-only nginx 配置 → certbot 拿证书 → certbot 自动升级为 HTTPS
    setup_nginx
    setup_ssl
    import_data
    start_service
    post_deploy_smoke
    
    log_info "部署完成！"
    log_info "API文档: https://wan.kaogong.art/api/docs"
    log_info "健康检查: https://wan.kaogong.art/health"
}

# 运行主函数
main "$@"
