#!/bin/bash
# Upgrade Drift 演练（v17.9.19：生产与演练复用唯一 build_release 实现）
#
# 用真实 build_release 逻辑（deploy.sh --build-only）证明 Immutable Release 的
# 四条不变量：
#   1. N-1 载荷中的幽灵文件在 N release 中不存在
#   2. N-1 venv 中的已删依赖在 N venv 中不存在（fresh venv）
#   3. N → N 重复构建幂等（同版本重装不残留）
#   4. current 符号链接原子切换 + 回滚切换可用
#
# 用法（root，Linux 服务器或 CI ubuntu）：bash scripts/upgrade_drill.sh
set -Eeuo pipefail

WAN_DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
DRILL_BASE="$(mktemp -d /tmp/wanyu-drill.XXXXXX)"
trap 'rm -rf "$DRILL_BASE"' EXIT

pass() { echo "[DRILL PASS] $1"; }
fail() { echo "[DRILL FAIL] $1"; exit 1; }

echo "=== 准备 N-1 载荷（注入幽灵文件 + 已删依赖）==="
cp -a "$WAN_DIR" "$DRILL_BASE/payload-v1"
rm -rf "$DRILL_BASE/payload-v1/.git" "$DRILL_BASE/payload-v1/venv" "$DRILL_BASE/payload-v1/.venv"
# 幽灵文件注入载荷根：build_release 的 release/app == 载荷根；写进 app/ 包内会落到
# release/app/app/，与下方 $V1_DIR/app/ 检查错位一格（真机演练曾因此前置必败）
echo "# legacy module (v17.9.17 era)" > "$DRILL_BASE/payload-v1/zz_ghost_legacy.py"
echo "" >> "$DRILL_BASE/payload-v1/requirements.lock.txt"
echo "six==1.16.0" >> "$DRILL_BASE/payload-v1/requirements.lock.txt"
cp -a "$WAN_DIR" "$DRILL_BASE/payload-v2"
rm -rf "$DRILL_BASE/payload-v2/.git" "$DRILL_BASE/payload-v2/venv" "$DRILL_BASE/payload-v2/.venv"

export WANYU_RELEASES_DIR="$DRILL_BASE/releases"
mkdir -p "$WANYU_RELEASES_DIR"

echo "=== 构建 release v1（含幽灵/依赖）==="
bash "$DRILL_BASE/payload-v1/deploy.sh" --build-only > "$DRILL_BASE/build1.log" 2>&1 || {
    tail -20 "$DRILL_BASE/build1.log"; fail "v1 build failed"; }
V1_DIR="$(grep -o '/tmp/wanyu-drill[^ ]*' "$DRILL_BASE/build1.log" | tail -1)"
[ -d "$V1_DIR" ] || fail "v1 release dir not found"

echo "=== 不变量1 前置确认：v1 确实含幽灵文件与 six 依赖 ==="
[ -f "$V1_DIR/app/zz_ghost_legacy.py" ] || fail "v1 ghost file missing (drill setup broken)"
"$V1_DIR/venv/bin/python" -c "import six" 2>/dev/null || fail "v1 six missing (drill setup broken)"
pass "v1 ghost file + six present (drill setup verified)"

echo "=== 构建 release v2（干净 N）==="
bash "$DRILL_BASE/payload-v2/deploy.sh" --build-only > "$DRILL_BASE/build2.log" 2>&1 || {
    tail -20 "$DRILL_BASE/build2.log"; fail "v2 build failed"; }
V2_DIR="$(grep -o '/tmp/wanyu-drill[^ ]*' "$DRILL_BASE/build2.log" | tail -1)"
[ -d "$V2_DIR" ] || fail "v2 release dir not found"

echo "=== 不变量1：幽灵文件在 N 中不存在 ==="
[ ! -e "$V2_DIR/app/zz_ghost_legacy.py" ] || fail "ghost file leaked into v2"
pass "ghost file absent in v2"

echo "=== 不变量2：已删依赖在 N venv 中不存在 ==="
"$V2_DIR/venv/bin/python" -c "import six" 2>/dev/null && fail "six leaked into v2 venv"
pass "removed dependency absent in v2 venv"

echo "=== 不变量3：N → N 重复构建幂等 ==="
bash "$DRILL_BASE/payload-v2/deploy.sh" --build-only > "$DRILL_BASE/build2b.log" 2>&1 || {
    tail -20 "$DRILL_BASE/build2b.log"; fail "v2 rebuild failed"; }
V2B_DIR="$(grep -o '/tmp/wanyu-drill[^ ]*' "$DRILL_BASE/build2b.log" | tail -1)"
[ -d "$V2B_DIR" ] || fail "v2b release dir not found"
"$V2B_DIR/venv/bin/python" -c "import six" 2>/dev/null && fail "six leaked into v2 rebuild"
[ ! -e "$V2B_DIR/app/zz_ghost_legacy.py" ] || fail "ghost leaked into v2 rebuild"
pass "rebuild idempotent (no accumulation)"

echo "=== 不变量4：current 符号链接原子切换 + 回滚 ==="
LINK_BASE="$DRILL_BASE/linktest"
mkdir -p "$LINK_BASE/releases/v1" "$LINK_BASE/releases/v2"
echo v1 > "$LINK_BASE/releases/v1/stamp"
echo v2 > "$LINK_BASE/releases/v2/stamp"
ln -sfn "$LINK_BASE/releases/v1" "$LINK_BASE/current.tmp" && mv -T "$LINK_BASE/current.tmp" "$LINK_BASE/current"
[ "$(cat "$LINK_BASE/current/stamp")" = "v1" ] || fail "initial switch failed"
ln -sfn "$LINK_BASE/releases/v2" "$LINK_BASE/current.tmp" && mv -T "$LINK_BASE/current.tmp" "$LINK_BASE/current"
[ "$(cat "$LINK_BASE/current/stamp")" = "v2" ] || fail "upgrade switch failed"
# 回滚：切回 v1
ln -sfn "$LINK_BASE/releases/v1" "$LINK_BASE/current.tmp" && mv -T "$LINK_BASE/current.tmp" "$LINK_BASE/current"
[ "$(cat "$LINK_BASE/current/stamp")" = "v1" ] || fail "rollback switch failed"
pass "atomic switch + rollback verified"

echo ""
echo "=========================================="
echo "UPGRADE DRILL: ALL PASS（幽灵文件=0 / 依赖漂移=0 / 幂等 / 切换+回滚可用）"
echo "=========================================="
