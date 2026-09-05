#!/usr/bin/env bash
# SSL 证书到期自检：<21 天退出 1（crontab 周跑，或接入告警）
HOST="${1:-wan.kaogong.art}"
END=$(echo | openssl s_client -connect "$HOST:443" -servername "$HOST" 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2)
if [ -z "$END" ]; then echo "FAIL: 无法获取 $HOST 证书（站点不可达或网络受限）"; exit 1; fi
DAYS=$(( ( $(date -d "$END" +%s) - $(date +%s) ) / 86400 ))
echo "$HOST 证书到期：$END（剩余 ${DAYS} 天）"
[ "$DAYS" -lt 21 ] && { echo "ALERT: 证书 21 天内到期，请续期"; exit 1; }
echo "OK"
