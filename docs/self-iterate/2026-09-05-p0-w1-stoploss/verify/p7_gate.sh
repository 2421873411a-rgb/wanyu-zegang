#!/usr/bin/env bash
# P7 (P0-6) gate wrapper: run the real check_release.sh from the toolchain; the real script is the acceptance artifact.
set -u
REAL="E:/zcode/择岗/项目源码/tools/anhui_web/check_release.sh"
SITE_DIR="E:/zcode/择岗/网站"
fail=0
[ -f "$REAL" ] || { echo "FAIL | check_release.sh missing at $REAL"; exit 1; }
# the gate must assert these families (grep the real script)
for pat in '?v=' 'PRECACHE' 'VERSION' 'release' 'check_secrets\|check-secrets' 'verify_maintainable_site'; do
  if ! grep -q "$pat" "$REAL"; then
    echo "FAIL | check_release.sh lacks assertion family: $pat"
    fail=1
  fi
done
[ "$fail" = 0 ] || exit 1
bash "$REAL" "$SITE_DIR"
rc=$?
if [ $rc -eq 0 ]; then echo "PASS | check_release.sh exited 0 on current tree"; else echo "FAIL | check_release.sh rc=$rc"; fi
exit $rc
