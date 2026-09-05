#!/usr/bin/env bash
# check_secrets.sh (P0-7) — 打包/发布前密钥泄漏扫描
# 用法: check_secrets.sh <dir> [dir...]
# 扫描五类: pem/key 文件、私钥块、api-key/token、password/secret 赋值、公网 IP 字面量
# 注意: 只做模式告警,不读文件内容入日志; 命中即 exit 1。
set -u
[ $# -ge 1 ] || { echo "usage: check_secrets.sh <dir> [dir...]"; exit 2; }
fail=0
for dir in "$@"; do
  [ -d "$dir" ] || { echo "FAIL | not a directory: $dir"; fail=1; continue; }
  # 1) pem/key files
  hits=$(find "$dir" -type f \( -name "*.pem" -o -name "*.key" -o -name "*.pfx" -o -name "*.p12" \) 2>/dev/null | head -20)
  [ -n "$hits" ] && { echo "FAIL | key files present in $dir:"; echo "$hits"; fail=1; }
  # 2) private key blocks
  hits=$(grep -rIl --exclude-dir=node_modules -E "BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY" "$dir" 2>/dev/null | head -20)
  [ -n "$hits" ] && { echo "FAIL | private key block in:"; echo "$hits"; fail=1; }
  # 3) api key / token assignments (assignment-style only, avoid prose false positives)
  hits=$(grep -rInE --include="*.py" --include="*.js" --include="*.sh" --include="*.yml" --include="*.yaml" --include="*.env" --include="*.ini" --include="*.conf" -E "(api[_-]?key|access[_-]?token|secret[_-]?token)['\"]?\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}" "$dir" 2>/dev/null | head -20)
  [ -n "$hits" ] && { echo "FAIL | hardcoded api-key/token:"; echo "$hits"; fail=1; }
  # 4) password / secret assignments
  hits=$(grep -rInE --include="*.py" --include="*.js" --include="*.sh" --include="*.yml" --include="*.yaml" --include="*.env" --include="*.ini" --include="*.conf" -E "(password|passwd|secret)['\"]?\s*[:=]\s*['\"][A-Za-z0-9_@#%\-]{6,}" "$dir" 2>/dev/null | head -20)
  [ -n "$hits" ] && { echo "FAIL | hardcoded password/secret:"; echo "$hits"; fail=1; }
  # 5) public IPv4 literals — 只扫部署/配置面(conf/yaml/env/ini/sh)：基础设施 IP 出现在配置里才算泄漏；
  #    *.py/*.js/*.json 中的 IP 是数据来源证据(官方附件直链)，不属于本检查对象
  hits=$(grep -rInE --include="*.conf" --include="*.yml" --include="*.yaml" --include="*.env" --include="*.ini" --include="*.sh" -E "\b([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\b" "$dir" 2>/dev/null \
    | grep -vE "0\.0\.0\.0|127\.0\.0\.1|255\.|version|VERSION|[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+[a-zA-Z]|_v[0-9]" \
    | grep -vE "://[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(:[0-9]+)?/" | head -20)
  [ -n "$hits" ] && { echo "FAIL | public IP literal:"; echo "$hits"; fail=1; }
done
[ "$fail" -eq 0 ] && echo "PASS | check_secrets.sh clean on: $*" || true
exit $fail
