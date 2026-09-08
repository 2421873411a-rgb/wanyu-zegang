#!/bin/bash
# PostgreSQL 本机恢复点：daily dump + 配对 checksum + 7/4/3 分层保留。
# 配置 COS_BUCKET 后，同步生成的 dump/checksum 到异地对象存储。
set -Eeuo pipefail

BASE="${WANYU_BACKUP_BASE:-/opt/wanyu/backup}"
DB_NAME="${WANYU_DB_NAME:-wanyu_db}"
STAMP="$(date +%Y%m%d-%H%M%S)"
DOW="$(date +%u)"
DOM="$(date +%d)"
DUMP_NAME="${DB_NAME}-${STAMP}.dump"
OUT="${BASE}/daily/${DUMP_NAME}"
TMP="${OUT}.tmp"

cleanup() {
    rm -f "$TMP"
}
trap cleanup EXIT

copy_snapshot() {
    local tier="$1"
    cp "$OUT" "${BASE}/${tier}/${DUMP_NAME}"
    cp "${OUT}.sha256" "${BASE}/${tier}/${DUMP_NAME}.sha256"
    chmod 640 "${BASE}/${tier}/${DUMP_NAME}" "${BASE}/${tier}/${DUMP_NAME}.sha256"
    sudo chown root:postgres "${BASE}/${tier}/${DUMP_NAME}" "${BASE}/${tier}/${DUMP_NAME}.sha256"
}

prune_tier() {
    local tier="$1" keep="$2" index
    local candidates=() ordered=()
    shopt -s nullglob
    candidates=("${BASE}/${tier}"/*.dump)
    shopt -u nullglob
    if [ "${#candidates[@]}" -le "$keep" ]; then
        return 0
    fi
    mapfile -t ordered < <(ls -1t -- "${candidates[@]}")
    for ((index=keep; index<${#ordered[@]}; index++)); do
        rm -f "${ordered[$index]}" "${ordered[$index]}.sha256"
    done
}

mkdir -p "$BASE/daily" "$BASE/weekly" "$BASE/monthly"
# 750 root:postgres：restore_drill 的 pg_restore 以 postgres 运行，须经组权限遍历并读取
# （真机演练实测：700/600 时 postgres 读 dump 直接 Permission denied——备份链与恢复链断链）
chmod 750 "$BASE" "$BASE/daily" "$BASE/weekly" "$BASE/monthly"
sudo chown root:postgres "$BASE" "$BASE/daily" "$BASE/weekly" "$BASE/monthly"
sudo -u postgres pg_dump -Fc "$DB_NAME" > "$TMP"
[ -s "$TMP" ] || { echo "EMPTY BACKUP: $TMP" >&2; exit 1; }
chmod 640 "$TMP"
mv "$TMP" "$OUT"
sudo chown root:postgres "$OUT"
(
    cd "$BASE/daily"
    sha256sum "$DUMP_NAME" > "${DUMP_NAME}.sha256"
)
chmod 640 "$OUT.sha256"
sudo chown root:postgres "$OUT.sha256"

CREATED_TIERS=(daily)
if [ "$DOW" = "7" ]; then
    copy_snapshot weekly
    CREATED_TIERS+=(weekly)
fi
if [ "$DOM" = "01" ]; then
    copy_snapshot monthly
    CREATED_TIERS+=(monthly)
fi

prune_tier daily 7
prune_tier weekly 4
prune_tier monthly 3

if [ -n "${COS_BUCKET:-}" ]; then
    COSCLI_BIN="${COSCLI:-coscli}"
    COS_PREFIX="${COS_PREFIX:-wanyu-db}"
    command -v "$COSCLI_BIN" >/dev/null || {
        echo "COS BACKUP FAILED: 找不到 ${COSCLI_BIN}" >&2
        exit 1
    }
    for tier in "${CREATED_TIERS[@]}"; do
        "$COSCLI_BIN" cp "${BASE}/${tier}/${DUMP_NAME}" \
            "cos://${COS_BUCKET}/${COS_PREFIX}/${tier}/${DUMP_NAME}"
        "$COSCLI_BIN" cp "${BASE}/${tier}/${DUMP_NAME}.sha256" \
            "cos://${COS_BUCKET}/${COS_PREFIX}/${tier}/${DUMP_NAME}.sha256"
    done
    echo "offsite backup ok: cos://${COS_BUCKET}/${COS_PREFIX}/"
else
    echo "LOCAL RECOVERY POINT ONLY: COS_BUCKET 未配置；整机故障不受保护" >&1
fi
echo "backup ok: $OUT"
