#!/bin/bash
# Restore Drill：daily 恢复点 → 临时库 → schema/canonical 基线核验 → 强制清理。
# 用法（root，服务器）：bash scripts/restore_drill.sh
set -Eeuo pipefail

BASE="${WANYU_BACKUP_BASE:-/opt/wanyu/backup}"
CURRENT_LINK="${WANYU_CURRENT_LINK:-/opt/wanyu/current}"
DRILL_DB="${WANYU_RESTORE_DRILL_DB:-wanyu_restore_drill}"
DB_NAME="${WANYU_DB_NAME:-wanyu_db}"
DB_CREATED=0

fail() {
    echo "[DRILL FAIL] $1" >&2
    return 1
}

if [[ ! "$DRILL_DB" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    fail "临时数据库名非法：${DRILL_DB}"
fi

drop_drill_database() {
    sudo -u postgres psql -v ON_ERROR_STOP=1 \
        -c "DROP DATABASE IF EXISTS \"${DRILL_DB}\" WITH (FORCE);" > /dev/null
}

cleanup() {
    local status=$?
    trap - EXIT
    if [ "$DB_CREATED" -eq 1 ]; then
        if drop_drill_database; then
            echo "[drill] 临时库已清理：${DRILL_DB}"
        else
            echo "[DRILL FAIL] 临时库清理失败：${DRILL_DB}" >&2
            status=1
        fi
    fi
    exit "$status"
}
trap cleanup EXIT

shopt -s nullglob
BACKUPS=("$BASE"/daily/"${DB_NAME}"-*.dump)
shopt -u nullglob
[ "${#BACKUPS[@]}" -gt 0 ] || fail "无 daily 备份可恢复"
LATEST="${BACKUPS[0]}"
for candidate in "${BACKUPS[@]:1}"; do
    if [ "$candidate" -nt "$LATEST" ]; then
        LATEST="$candidate"
    fi
done
echo "[drill] 备份文件：$LATEST"

# 自动备份的 checksum 是恢复契约的一部分；缺失时拒绝把裸 dump 当成已验证恢复点。
[ -f "$LATEST.sha256" ] || fail "备份缺少 checksum：$LATEST.sha256"
(
    cd "$(dirname "$LATEST")"
    sha256sum -c "$(basename "$LATEST").sha256"
) || fail "备份校验和不匹配"
echo "[drill] sha256 校验 PASS"

# pg_dump -Fc 不含 CREATE DATABASE；目标库必须先显式创建。
drop_drill_database
DB_CREATED=1
sudo -u postgres psql -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE \"${DRILL_DB}\";" > /dev/null
sudo cat "$LATEST" | sudo -u postgres pg_restore --exit-on-error --no-owner -d "$DRILL_DB" \
    || fail "pg_restore 失败"
echo "[drill] pg_restore PASS"

# immutable release 布局是 current/{app,venv}；以代码 head 对账恢复库 revision。
ALEMBIC_BIN="${CURRENT_LINK}/venv/bin/alembic"
[ -x "$ALEMBIC_BIN" ] || fail "Alembic 不可执行：$ALEMBIC_BIN"
HEAD_OUTPUT="$(cd "${CURRENT_LINK}/app" && "$ALEMBIC_BIN" heads 2>/dev/null)"
mapfile -t HEAD_LINES <<< "$HEAD_OUTPUT"
[ "${#HEAD_LINES[@]}" -eq 1 ] || fail "代码存在多个 Alembic head，拒绝恢复核验"
read -r HEAD_REV _ <<< "${HEAD_LINES[0]}"
[ -n "${HEAD_REV:-}" ] || fail "代码 head revision 读取失败"
DB_REV="$(sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$DRILL_DB" -tAc \
    "SELECT version_num FROM alembic_version" | tr -d '[:space:]')"
[ "$DB_REV" = "$HEAD_REV" ] \
    || fail "revision 不一致：drill=$DB_REV code_head=$HEAD_REV"
echo "[drill] alembic revision PASS ($DB_REV)"

query_count() {
    sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$DRILL_DB" -tAc "$1" \
        | tr -d '[:space:]'
}

assert_exact_count() {
    local label="$1" actual="$2" expected="$3"
    [[ "$actual" =~ ^[0-9]+$ ]] || fail "$label 行数不是整数：$actual"
    [ "$actual" = "$expected" ] || fail "$label=$actual，期望 $expected"
}

declare -A EXPECTED_JOBS=(
    [2024]=10017
    [2025]=10150
    [2026]=8511
)
for cycle in 2024 2025 2026; do
    count="$(query_count "SELECT count(*) FROM jobs WHERE cycle='$cycle'")"
    echo "[drill] jobs $cycle = $count"
    assert_exact_count "jobs $cycle" "$count" "${EXPECTED_JOBS[$cycle]}"
done

active_2026="$(query_count \
    "SELECT count(*) FROM jobs WHERE cycle='2026' AND record_status='active'")"
assert_exact_count "2026 active" "$active_2026" 8401

salary_count="$(query_count "SELECT count(*) FROM salary_data")"
review_count="$(query_count "SELECT count(*) FROM review_events")"
user_count="$(query_count "SELECT count(*) FROM users")"
for pair in "salary:$salary_count" "review:$review_count" "users:$user_count"; do
    value="${pair#*:}"
    [[ "$value" =~ ^[0-9]+$ ]] || fail "${pair%%:*} 行数不是整数：$value"
done
[ "$salary_count" -ge 160 ] || fail "salary 行数异常：$salary_count"
[ "$review_count" -le 200 ] || fail "review 行数异常：$review_count"
echo "[drill] salary=$salary_count review=$review_count users=$user_count"

echo "[DRILL PASS] dump 可恢复、schema 与 canonical 基线正确（退出时清理临时库）"
