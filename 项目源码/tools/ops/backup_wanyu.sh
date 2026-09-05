#!/usr/bin/env bash
# 皖域择岗 · COS 异地备份（v2 计划 R2）
# 前置（一次性）：
#   1. 安装 coscli 并初始化：coscli config init  （密钥只存本机 ~/.cos，权限 600，绝不入库/入包）
#   2. export COS_BUCKET=<桶名-APPID>
#   3. COS 控制台配生命周期：wanyu-backup/daily/ 7 天过期；weekly/ 保留 4 版；monthly/ 保留 180 天
# 用法：./backup_wanyu.sh [daily|monthly] [项目根]     （建议 crontab：daily 每日 03:30，monthly 每月 1 日）
# 恢复演练（首次必做）：从 COS 下载 site-*.tgz 与 code-*.bundle 到空目录，
#   tar -xzf site-*.tgz && git clone code-*.bundle 检出 --all，逐文件对账 SHA256SUMS。
set -euo pipefail
MODE="${1:-daily}"
ROOT="${2:-$(cd "$(dirname "$0")/../.." && pwd)}"
STAMP="$(date +%F)"
BUCKET="${COS_BUCKET:?请先 export COS_BUCKET=桶名-APPID}"
COSCLI="${COSCLI:-coscli}"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

case "$MODE" in
  daily)
    git -C "$ROOT" bundle create "$OUT/code-$STAMP.bundle" --all
    tar -czf "$OUT/site-$STAMP.tgz" -C "$ROOT" 网站 docs *.md .gitignore 交接包清单.txt 交接说明_20260905.md 2>/dev/null \
      || tar -czf "$OUT/site-$STAMP.tgz" -C "$ROOT" 网站 docs
    ;;
  monthly)
    # 大数据三件套：源证据链 + 收割中间数据 + 派生副本（git 不入库，靠月备兜底）
    tar -czf "$OUT/bigdata-$STAMP.tgz" -C "$ROOT" 项目源码/source_data 项目源码/tools/anhui_web/data 网站-lite
    ;;
  *)
    echo "用法: $0 [daily|monthly] [项目根]"; exit 1;;
esac

( cd "$OUT" && sha256sum -- * > SHA256SUMS )
"$COSCLI" cp -r "$OUT/." "cos://$BUCKET/wanyu-backup/$MODE/$STAMP/" --recursive
mkdir -p "$ROOT/docs/ops"
{ echo "[$(date '+%F %T')] $MODE → $BUCKET/wanyu-backup/$MODE/$STAMP/"; cat "$OUT/SHA256SUMS"; } >> "$ROOT/docs/ops/backup-log.txt"
echo "[$MODE] 备份完成：$BUCKET/wanyu-backup/$MODE/$STAMP/"
