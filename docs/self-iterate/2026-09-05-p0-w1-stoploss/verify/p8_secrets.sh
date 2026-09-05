#!/usr/bin/env bash
# P8 (P0-7) gate wrapper: run the real check_secrets.sh; the real script is the acceptance artifact.
set -u
REAL="E:/zcode/择岗/项目源码/tools/anhui_web/check_secrets.sh"
fail=0
[ -f "$REAL" ] || { echo "FAIL | check_secrets.sh missing at $REAL"; exit 1; }
for pat in "pem" "PRIVATE KEY" "api" "token" "password" "([0-9]{1,3})"; do
  if ! grep -qF "$pat" "$REAL"; then
    echo "FAIL | check_secrets.sh lacks scan family: $pat"
    fail=1
  fi
done
[ "$fail" = 0 ] || exit 1
bash "$REAL" "E:/zcode/择岗/网站" "E:/zcode/择岗/项目源码/tools" "E:/zcode/择岗/项目源码/wan-api"
rc=$?
if [ $rc -eq 0 ]; then echo "PASS | check_secrets.sh clean on 网站/ + tools/ + wan-api/"; else echo "FAIL | check_secrets.sh rc=$rc"; fi
exit $rc
