#!/bin/bash
# 皖域择岗 API 部署脚本 v2 —— Immutable Release 架构（v17.9.19）
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
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
RELEASE_JSON="${SCRIPT_DIR}/release.json"
APP_VERSION=""
WANYU_RELEASE_SUFFIX=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

load_release_metadata() {
    [ -f "$RELEASE_JSON" ] || {
        log_error "版本真源缺失：${RELEASE_JSON}"
        return 1
    }
    APP_VERSION="$(python3 - "$RELEASE_JSON" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    print(json.load(handle)["release"])
PY
)"
    if [[ ! "$APP_VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        log_error "release.json 版本格式非法：${APP_VERSION:-<empty>}"
        return 1
    fi
}

# 自动回滚锚点：atomic_switch 记录上一 release；迁移完成后才允许自动回切——
# RUNBOOK 顺序铁律：不兼容迁移失败时必须先用新 release 降库、再切旧 release，
# 迁移前/中自动回切会让旧代码面对新 schema（"Can't locate revision"）。
PREVIOUS_RELEASE=""
SWITCHED=0
MIGRATION_DONE=0

rollback_to_previous() {
    if [ "$SWITCHED" != "1" ]; then
        return 0
    fi
    if [ "$MIGRATION_DONE" != "1" ] || [ -z "$PREVIOUS_RELEASE" ]; then
        log_error "迁移前/中失败：禁止自动回切（旧代码缺少新 revision，RUNBOOK 顺序铁律：先降库后切旧 release）。"
        log_error "恢复点：迁移前 dump 与 .alembic-before.txt sidecar 在 ${BACKUP_ROOT}；按 RUNBOOK「回滚」节人工执行。"
        return 0
    fi
    local prev_dir="${RELEASES_DIR}/${PREVIOUS_RELEASE}"
    if [ ! -d "$prev_dir" ]; then
        log_error "自动回滚中止：上一 release 目录不存在：${prev_dir}"
        return 0
    fi
    # 审计 API-002：迁移已应用后（DB head 前移，旧代码 head 停留在迁移前 revision），
    # 直接回切会被旧 release 的启动门（alembic 版本一致性）拒绝——服务起不来。
    # 用迁移前 sidecar 判定：不一致则拒绝自动回切，给出人工降库路径。
    local latest_sidecar="" before_rev="" db_rev=""
    # 探测是 best-effort：显式 if! 容错（pipefail 下探测失败→跳过守卫、回退原回滚语义），
    # 不用 || true 字面吞错，满足无吞错回归锁（审计核验 round-3）
    if ! latest_sidecar="$(ls -1t "${BACKUP_ROOT}"/*.alembic-before.txt 2>/dev/null | head -1)"; then
        latest_sidecar=""
    fi
    if ! db_rev="$(sudo -u postgres psql -v ON_ERROR_STOP=1 -d wanyu_db -tAc "SELECT version_num FROM alembic_version LIMIT 1" 2>/dev/null | tr -d '[:space:]')"; then
        db_rev=""
    fi
    if [ -n "$latest_sidecar" ] && [ -n "$db_rev" ]; then
        before_rev="$(sudo cat "$latest_sidecar" 2>/dev/null | tr -d '[:space:]')"
        if [ -n "$before_rev" ] && [ "$before_rev" != "base" ] && [ "$db_rev" != "$before_rev" ]; then
            log_error "自动回滚中止：迁移已应用（DB=${db_rev}，迁移前=${before_rev}），旧代码无法运行新 schema。"
            log_error "人工路径A：${prev_dir}/venv/bin/alembic downgrade ${before_rev} 后重试回切；"
            log_error "人工路径B：直接修复新版问题后重新部署。恢复点 dump：${latest_sidecar%.alembic-before.txt}"
            return 0
        fi
    fi
    log_error "自动回滚：current -> ${PREVIOUS_RELEASE}"
    sudo ln -sfn "$prev_dir" "${CURRENT_LINK}.tmp"
    sudo mv -T "${CURRENT_LINK}.tmp" "${CURRENT_LINK}"
    local prev_ver
    prev_ver="$(sed -n 's/.*"release"[[:space:]]*:[[:space:]]*"\(v[0-9][0-9.]*\)".*/\1/p' "$prev_dir/app/release.json" 2>/dev/null | head -1)"
    if [ -n "$prev_ver" ]; then
        sudo sed -i "s/^APP_VERSION=.*/APP_VERSION=${prev_ver}/" "$SECRET_ENV"
    fi
    sudo systemctl restart "$SERVICE_NAME" || log_error "回滚后服务重启失败，需人工介入：journalctl -u ${SERVICE_NAME}"
    sleep 2
    if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
        log_error "✓ 已回滚至 ${PREVIOUS_RELEASE}（version=${prev_ver:-unknown}），服务健康"
    else
        log_error "回滚完成但 /health 未就绪，需人工检查：journalctl -u ${SERVICE_NAME}"
    fi
}

# v17.10.0 部署状态持久化：排障时先看 /opt/wanyu/deploy-state.json（无密钥，可读）
DEPLOY_STATE_FILE="${DEPLOY_STATE_FILE:-/opt/wanyu/deploy-state.json}"

record_deploy_state() {
    # best-effort：状态文件只服务排障，写失败绝不阻断部署（失败全在 if 条件内消化）
    local tmp="${DEPLOY_STATE_FILE}.tmp"
    if printf '{"phase":"%s","release":"%s","timestamp":"%s"}
'         "$1" "${APP_VERSION:-}" "$(date -Is 2>/dev/null || date)" > "$tmp" 2>/dev/null         && mv -f "$tmp" "$DEPLOY_STATE_FILE" 2>/dev/null; then
        :
    fi
    return 0
}

on_error() {
    local exit_code=$?
    log_error "部署失败：line=${BASH_LINENO[0]:-unknown} command=${BASH_COMMAND:-unknown} exit=${exit_code}"
    record_deploy_state "FAILED"
    rollback_to_previous
    log_error "回滚处理完成（详见上方）。人工预案：docs/ops/RUNBOOK.md"
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
    # 静态数据前置：逐项校验（缺失在预检阶段就中止，不在装完全部依赖后）
    check_static_data
    local cmd
    for cmd in curl sudo openssl python3 tar; do
        command -v "$cmd" >/dev/null || {
            log_error "缺少前置命令：$cmd"
            exit 1
        }
    done
}

check_static_data() {
    # API 运行时与 nginx 都直接消费这些静态派生文件；缺失必须在预检阶段点名中止
    local missing=""
    local cycle
    for cycle in 2024 2025 2026; do
        [ -f "${STATIC_DATA_PATH}/cycles/${cycle}/jobs.json" ] || missing="${missing} cycles/${cycle}/jobs.json"
    done
    [ -f "${STATIC_DATA_PATH}/salary/anhui.json" ] || missing="${missing} salary/anhui.json"
    [ -f "${STATIC_DATA_PATH}/audit/review-queue.json" ] || missing="${missing} audit/review-queue.json"
    if [ -n "$missing" ]; then
        log_error "部署前置缺失静态数据（${STATIC_DATA_PATH}）：${missing}——请先放置 canonical 派生数据，见 docs/ops/RUNBOOK.md"
        return 1
    fi
    log_info "✓ 静态数据前置完整（三周期 jobs + salary + audit）"
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
    # v17.10.1 审查修复：ADMIN_EMAIL 写入 secret heredoc 前先校验——heredoc 无引号
    # 展开，含换行/引号/空白的值会注入额外 env 行（operator 自伤面，fail-fast）。
    if [ -n "${ADMIN_EMAIL:-}" ] && ! printf '%s' "${ADMIN_EMAIL}" | grep -Eq '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+$'; then
        log_error "ADMIN_EMAIL 格式非法（须为不含空白/引号/换行的邮箱字面量），拒绝继续：${ADMIN_EMAIL}"
        exit 1
    fi
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
CORS_ORIGINS='["https://wan.kaogong.art"]'
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

run_as_app() {
    # systemd 通过 EnvironmentFile 启动服务；迁移/导入等一次性 CLI 也必须读取同一真源。
    [ -r "$SECRET_ENV" ] || {
        log_error "生产 EnvironmentFile 不可读：${SECRET_ENV}"
        return 1
    }
    # 不直接 source：EnvironmentFile 是数据而非可执行 shell；只解析 key=value 与外层引号。
    # -c 代码不占 stdin，因此目标 python 的 heredoc 仍可原样透传。
    sudo -u www-data python3 -c '
import os
import re
import shlex
import subprocess
import sys

env_file = sys.argv[1]
command = sys.argv[2:]
if not command:
    raise SystemExit("missing app command")
env = os.environ.copy()
with open(env_file, encoding="utf-8") as handle:
    for number, raw in enumerate(handle, 1):
        line = raw.rstrip("\r\n")
        if not line or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise SystemExit(f"invalid EnvironmentFile line {number}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in chr(34) + chr(39):
            parsed = shlex.split(value, comments=False, posix=True)
            if len(parsed) != 1:
                raise SystemExit(f"invalid EnvironmentFile value {number}")
            value = parsed[0]
        env[key] = value
raise SystemExit(subprocess.run(command, env=env).returncode)
' "$SECRET_ENV" "$@"
}

build_release() {
    # Immutable release：全新目录 + 全新 venv，root 属主（www-data 只读）
    log_info "构建 release ${APP_VERSION}..."
    local git_sha
    git_sha="$(git -C "$SCRIPT_DIR" rev-parse --short HEAD 2>/dev/null || echo nodata)"
    RELEASE_DIR="${RELEASES_DIR}/${APP_VERSION}-${git_sha}${WANYU_RELEASE_SUFFIX}"

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
# strict 使 /tmp 只读；必须隔离私有 tmp（v17.9.18 实测：缺失→gunicorn
# "No usable temporary directory" exit 255）
PrivateTmp=true
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
    # fresh-host 首部署时 current 不存在，readlink 预期失败——用 if 条件形式吞掉（-e/-E 安全）
    local prev_link=""
    if prev_link="$(readlink "$CURRENT_LINK" 2>/dev/null)"; then
        PREVIOUS_RELEASE="$(basename "$prev_link")"
    else
        PREVIOUS_RELEASE=""
    fi
    sudo ln -sfn "$RELEASE_DIR" "${CURRENT_LINK}.tmp"
    sudo mv -T "${CURRENT_LINK}.tmp" "${CURRENT_LINK}"
    [ "$(readlink "$CURRENT_LINK" 2>/dev/null)" = "$RELEASE_DIR" ] || {
        log_error "current 符号链接切换失败"
        exit 1
    }
    SWITCHED=1
    record_deploy_state "SWITCHED"
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
    # 唯一实现：仓库脚本既由 pytest 行为验证，也由 systemd 原样执行。
    sudo install -m 0750 "${SCRIPT_DIR}/scripts/backup_database.sh" /etc/wanyu/wanyu-backup.sh
    sudo tee /etc/systemd/system/wanyu-backup.service > /dev/null <<'BSEOF'
[Unit]
Description=WanYu DB local recovery point and optional COS backup

[Service]
Type=oneshot
EnvironmentFile=-/etc/wanyu/backup.env
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
    # 普通匿名 API 收紧到 512k（v17.10.2 P1-04）；64MB 只给 admin JSON 导入。
    # 两段 proxy 指令完全一致：改 proxy 行为时两处必须同步改。
    location /api/ {
        limit_req zone=wanapi burst=60 nodelay;
        client_max_body_size 512k;
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
    # admin 单周期 JSON 导入独享 64MB（应用层另有流式 413 兜底）
    location ~ ^/api/v1/admin/import/ {
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
        root /var/www/wan.kaogong.art;
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

migrate_and_import_release() {
    (
        cd "${RELEASE_DIR}/app"
        run_as_app "${RELEASE_DIR}/venv/bin/alembic" upgrade head
        run_as_app "${RELEASE_DIR}/venv/bin/python" - <<'PY'
import asyncio
from app.database import init_db, async_session_factory
from app.services.import_service import import_all_data

async def main():
    await init_db()
    async with async_session_factory() as db:
        results = await import_all_data(db, data_path=None)
        cycles = [results.get(f"cycle_{year}") for year in ("2024", "2025", "2026")]
        if not all(cycles):
            raise RuntimeError("三个周期未全部导入，拒绝启动不完整镜像")
        print("导入结果:", {k: v for k, v in results.items()})

asyncio.run(main())
PY
    )
}

create_database_snapshot() {
    local label="${1:-}" stem dump_file temp_file
    stem="wanyu_db"
    if [ -n "$label" ]; then
        stem="${stem}-${label}"
    fi
    dump_file="${BACKUP_ROOT}/${stem}-$(date +%Y%m%d-%H%M%S).dump"
    temp_file="$(mktemp "${BACKUP_ROOT}/.${stem}.XXXXXX")"
    if ! sudo -u postgres pg_dump -Fc wanyu_db > "$temp_file"; then
        rm -f "$temp_file"
        log_error "pg_dump 执行失败：${stem}"
        return 1
    fi
    if [ ! -s "$temp_file" ]; then
        rm -f "$temp_file"
        log_error "pg_dump 产物为空，拒绝继续：${stem}"
        return 1
    fi
    chmod 640 "$temp_file"
    sudo chown root:postgres "$temp_file"
    mv "$temp_file" "$dump_file"
    (
        cd "$BACKUP_ROOT"
        sha256sum "$(basename "$dump_file")" > "$(basename "$dump_file").sha256"
    )
    chmod 640 "${dump_file}.sha256"
    sudo chown root:postgres "${dump_file}.sha256"
    printf '%s\n' "$dump_file"
}

record_pre_migration_revision() {
    local dump_file="$1" relation revision="base"
    relation="$(sudo -u postgres psql -v ON_ERROR_STOP=1 -d wanyu_db -tAc \
        "SELECT to_regclass('public.alembic_version')" | tr -d '[:space:]')"
    if [ "$relation" = "alembic_version" ]; then
        revision="$(sudo -u postgres psql -v ON_ERROR_STOP=1 -d wanyu_db -tAc \
            "SELECT version_num FROM alembic_version" | tr -d '[:space:]')"
        [ -n "$revision" ] || revision="unknown"
    fi
    printf '%s\n' "$revision" > "${dump_file}.alembic-before.txt"
    chmod 600 "${dump_file}.alembic-before.txt"
}

import_data() {
    log_info "导入数据（使用新 release venv）..."
    # 迁移前数据库快照（数据级还原点）
    sudo mkdir -p "$BACKUP_ROOT"
    # 审计 API-003：与 backup_database.sh 统一为 750 root:postgres——700 会让
    # postgres 无法遍历读取部署期快照，部署后到下一次定时备份之间恢复链是断的。
    sudo chmod 750 "$BACKUP_ROOT"
    sudo chown root:postgres "$BACKUP_ROOT"
    local dump_file
    dump_file="$(create_database_snapshot)"
    record_pre_migration_revision "$dump_file"
    log_info "✓ 数据库快照：${dump_file}"

    migrate_and_import_release
    local post_dump
    post_dump="$(create_database_snapshot post-import)"
    log_info "✓ 导入后快照：${post_dump}"
    # 迁移+导入完成：此后失败允许自动回切旧 release（DB schema 已与新代码兼容）
    MIGRATION_DONE=1
    record_deploy_state "IMPORTED"
}

start_service() {
    log_info "启动服务..."
    sudo systemctl restart "$SERVICE_NAME"
    sudo systemctl is-active --quiet "$SERVICE_NAME"
    systemctl status "$SERVICE_NAME" --no-pager | head -3
}

smoke_public_root() {
    # fresh-host 模板的 / 先 302 到静态入口；现网也可能直接 200。
    # 先不带 -L 钉死跳转目标（必须指向 /maintainable/ 静态入口，防止 302 到任意路径
    # 仍被判绿），再跟随跳转验证用户最终拿到的页面是 200。
    local first redirect_url final_code
    first="$(curl -sS -o /dev/null -w '%{http_code}' https://wan.kaogong.art/)" || {
        log_error "公网 HTTPS 静态站请求失败"
        return 1
    }
    if [ "$first" = "301" ] || [ "$first" = "302" ]; then
        redirect_url="$(curl -sS -o /dev/null -w '%{redirect_url}' https://wan.kaogong.art/)"
        case "$redirect_url" in
            */maintainable/index.html|*/maintainable/) ;;
            *)
                log_error "根路径跳转目标异常：${redirect_url:-<empty>}（期望 /maintainable/ 静态入口）"
                return 1
                ;;
        esac
    fi
    final_code="$(curl -sS -L -o /dev/null -w '%{http_code}' https://wan.kaogong.art/)" || {
        log_error "公网 HTTPS 静态站（跟随跳转）请求失败"
        return 1
    }
    if [ "$final_code" != "200" ]; then
        log_error "静态站跟随跳转后返回 ${final_code}（期望 200）"
        return 1
    fi
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
        smoke_public_root
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
    record_deploy_state "HEALTHY"
    log_info "✓ 健康/版本(${actual_version})/岗位(${jobs_count}) smoke 全通过"
}

bootstrap_admin() {
    cd "${CURRENT_LINK}/app"
    if [ -n "${ADMIN_BOOTSTRAP_PASSWORD:-}" ]; then
        # v17.10.1 审查修复：密码走 stdin 管道，不再经 argv——/proc/<pid>/cmdline
        # 全员可读，env 亦受限；run_as_app 的 python3 -c 不占 stdin，管道原样透传
        # 到目标 python（create_admin.py 侧非 tty 时从 stdin 读取）。
        printf '%s' "${ADMIN_BOOTSTRAP_PASSWORD}" | run_as_app "${CURRENT_LINK}/venv/bin/python" scripts/create_admin.py \
            --email "${ADMIN_EMAIL:-admin@kaogong.art}" \
            --username admin
        log_info "✓ 管理员引导完成（${ADMIN_EMAIL:-admin@kaogong.art}）"
    else
        log_warn "未设置 ADMIN_BOOTSTRAP_PASSWORD，跳过管理员引导。生产管理员必须补做："
        log_warn "  cd ${CURRENT_LINK}/app && sudo -u www-data ${CURRENT_LINK}/venv/bin/python scripts/create_admin.py --email ${ADMIN_EMAIL:-admin@kaogong.art} --username admin"
    fi
}

main() {
    log_info "开始部署皖域择岗 API（Immutable Release）..."
    record_deploy_state "PRECHECK"
    check_root
    check_prerequisites
    # 版本必须先于任何 secret 写入解析；build_release 不再隐式修改全局版本。
    load_release_metadata
    install_dependencies
    setup_database
    setup_secret_env
    build_release
    record_deploy_state "BUILT"
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
build_only_main() {
    check_root
    load_release_metadata
    RELEASES_DIR="${WANYU_RELEASES_DIR:-${RELEASES_DIR}}"
    WANYU_RELEASE_SUFFIX="-drill"
    build_release
    log_info "build-only 完成：${RELEASE_DIR}"
}

dispatch() {
    if [ "${1:-}" = "--build-only" ]; then
        build_only_main
    else
        main "$@"
    fi
}

# 允许测试/运维工具只加载函数定义，不触发 root 部署。
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    dispatch "$@"
fi
