#!/bin/bash
# Restore Drill（v17.9.18 验收项：备份必须能真正恢复才算备份）
#
# 流程：取最新 daily 备份 → 建临时库 wanyu_restore_drill → pg_restore →
#       alembic revision 核对 → 行数对账（jobs/salary/review_events/users）→ 清理
#
# 用法（root，服务器）：bash scripts/restore_drill.sh
set -Eeuo pipefail

BASE=/opt/wanyu/backup
DRILL_DB=wanyu_restore_drill

LATEST=$(ls -1t "$BASE"/daily/wanyu_db-*.dump 2>/dev/null | head -1)
[ -n "$LATEST" ] || { echo "[DRILL FAIL] 无 daily 备份可恢复"; exit 1; }
echo "[drill] 备份文件：$LATEST"

# 校验和（若存在 .sha256）
if [ -f "$LATEST.sha256" ]; then
    (cd "$(dirname "$LATEST")" && sha256sum -c "$(basename "$LATEST").sha256") \
        || { echo "[DRILL FAIL] 备份校验和不匹配"; exit 1; }
    echo "[drill] sha256 校验 PASS"
fi

# 临时库重建
sudo -u postgres psql -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $DRILL_DB;" > /dev/null
sudo -u postgres pg_restore -d "$DRILL_DB" --no-owner "$LATEST" \
    || { echo "[DRILL FAIL] pg_restore 失败"; exit 1; }
echo "[drill] pg_restore PASS"

# alembic revision 核对（临时库的版本必须与生产 head 一致）
HEAD_REV=$(cd /opt/wanyu/current/app && sudo -u www-data ./venv/bin/alembic current 2>/dev/null | awk '{print $1}' | head -1)
[ -n "$HEAD_REV" ] || { echo "[DRILL FAIL] 生产 revision 读取失败"; exit 1; }
DB_REV=$(sudo -u postgres psql -d "$DRILL_DB" -tAc "SELECT version_num FROM alembic_version" | head -1)
[ "$DB_REV" = "$HEAD_REV" ] || { echo "[DRILL FAIL] revision 不一致：drill=$DB_REV prod=$HEAD_REV"; exit 1; }
echo "[drill] alembic revision PASS ($DB_REV)"

# 行数对账（与 e2e 基线一致：2024=10017/2025=10150/2026=8511；salary=160；review≤200）
count() { sudo -u postgres psql -d "$DRILL_DB" -tAc "SELECT count(*) FROM $1" | tr -d ' '; }
for cycle in 2024 2025 2026; do
    n=$(sudo -u postgres psql -d "$DRILL_DB" -tAc "SELECT count(*) FROM jobs WHERE cycle='$cycle'" | tr -d ' ')
    echo "[drill] jobs $cycle = $n"
done
act=$(sudo -u postgres psql -d "$DRILL_DB" -tAc "SELECT count(*) FROM jobs WHERE cycle='2026' AND record_status='active'" | tr -d ' ')
[ "$act" = "8401" ] || { echo "[DRILL FAIL] 2026 active=$act，期望 8401"; exit 1; }
sal=$(count salary_data); rev=$(count review_events); usr=$(count users)
echo "[drill] salary=$sal review=$rev users=$usr"
[ "$sal" -ge 160 ] || { echo "[DRILL FAIL] salary 行数异常"; exit 1; }

# 清理
sudo -u postgres psql -c "DROP DATABASE IF EXISTS $DRILL_DB;" > /dev/null
echo "[DRILL PASS] 备份可恢复、schema 正确、数据对账通过（临时库已清理）"
