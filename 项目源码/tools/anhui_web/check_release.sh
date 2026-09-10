#!/usr/bin/env bash
# check_release.sh (P0-6) — 发布前版本一致性门禁
# 用法: check_release.sh <site_dir>
# 断言: index 全部 ?v= 同值；sw VERSION 单调(v>=40)且 PRECACHE ?v= 与 index 一致；
#       PRECACHE 文件存在；manifest release == index ?v=；随后内嵌 check_secrets + 磁盘校验器。
set -u
SITE="${1:?usage: check_release.sh <site_dir>}"
fail=0
err() { echo "FAIL | $1"; fail=1; }

[ -f "$SITE/index.html" ] || { err "index.html missing"; exit 1; }
[ -f "$SITE/sw.js" ] || { err "sw.js missing"; exit 1; }
[ -f "$SITE/data/site-manifest.json" ] || { err "site-manifest.json missing"; exit 1; }

# 1) index ?v= uniformity
vers=$(grep -o '?v=[0-9][0-9A-Za-z.-]*' "$SITE/index.html" | sort -u)
count=$(echo "$vers" | grep -c '^?v=')
[ "$count" -eq 1 ] || err "index has $count distinct ?v= values: $vers"
V=$(echo "$vers" | head -1 | cut -d= -f2)
[ -n "$V" ] || err "cannot extract index ?v="

# 2) sw VERSION monotonic (>= v40) and matches PRECACHE versioning
SWV=$(grep -o 'wanyu-shell-v[0-9]*' "$SITE/sw.js" | head -1 | grep -o '[0-9]*$')
[ -n "$SWV" ] || err "sw VERSION not found"
[ "${SWV:-0}" -ge 40 ] || err "sw VERSION v$SWV must be >= 40 (monotonic guard)"

# 3) PRECACHE ?v= values identical to index ?v=
pc_vers=$(grep -o '?v=[0-9][0-9A-Za-z.-]*' "$SITE/sw.js" | sort -u)
pc_count=$(echo "$pc_vers" | grep -c '^?v=')
[ "$pc_count" -eq 1 ] || err "sw PRECACHE has $pc_count distinct ?v= values: $pc_vers"
PCV=$(echo "$pc_vers" | head -1 | cut -d= -f2)
[ "$PCV" = "$V" ] || err "sw PRECACHE ?v=$PCV != index ?v=$V"

# 4) every PRECACHE entry exists on disk
grep -o '"[^"]*"' "$SITE/sw.js" | tr -d '"' | grep -v '^$' | while IFS= read -r entry; do
  case "$entry" in
    assets/*|data/*|index.html|manifest.webmanifest)
      f="${entry%%\?*}"
      [ -f "$SITE/$f" ] || echo "FAIL | PRECACHE entry missing: $entry"
      ;;
  esac
done | sort -u > /tmp/check_release_precache.txt
if [ -s /tmp/check_release_precache.txt ]; then
  err "PRECACHE missing files:"; cat /tmp/check_release_precache.txt
fi

# 5) manifest release == index ?v=
REL=$(python -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8')).get('release',''))" "$SITE/data/site-manifest.json" 2>/dev/null)
[ "$REL" = "v$V" ] || err "manifest release '$REL' != index ?v=$V"

echo "site version: index ?v=$V, sw wanyu-shell-v$SWV, manifest $REL"

# 6) gates: secrets scan + disk verifier (run from this tool dir)
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$HERE/check_secrets.sh" ]; then
  bash "$HERE/check_secrets.sh" "$SITE" || fail=1
else
  err "check_secrets.sh not found next to check_release.sh"
fi
# 6b) v17.10.1 审查修复：secrets 扫描覆盖源码树——原实现只扫 $SITE，
#     wan-api/tools/docs 全靠手工补跑（self-iterate 手工 evidence 为证，审查 P1）。
#     tests 目录已在 check_secrets.sh 内豁免（fixture 假密钥）。
ROOT="$(cd "$HERE/../.." && pwd)"
if [ -d "$ROOT" ]; then
  bash "$HERE/check_secrets.sh" "$ROOT" || fail=1
else
  err "source tree root not found: $ROOT"
fi
if [ -f "$HERE/verify_maintainable_site.py" ]; then
  python "$HERE/verify_maintainable_site.py" "$SITE" >/tmp/check_release_verify.txt 2>&1 \
    && echo "PASS | disk verifier" \
    || { err "disk verifier failed"; tail -3 /tmp/check_release_verify.txt; }
else
  err "verify_maintainable_site.py not found"
fi

[ "$fail" -eq 0 ] && echo "PASS | check_release.sh all gates green" || true
exit $fail
