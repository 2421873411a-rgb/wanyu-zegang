#!/usr/bin/env bash
# 皖域择岗 · 部署到 wan.kaogong.art（腾讯云轻量「小陈」）
# v17.8.6 起：打包对象 = canonical 发布树 网站/（release.py 流水线原子提升产物，
# 含 .gz 预压缩），远端保持 SITE_ROOT/maintainable/ 布局；
# 遗留单文件 皖域择岗总览.html 与 deliverables/maintainable 已退役，不再打包。
# 安全默认：DRY_RUN=1（只打印将执行的命令，绝不连生产、绝不动服务器）。
# 真正执行需你显式在场：DRY_RUN=0 ./deploy_wan.sh
#
# 可用环境变量（均有安全默认）：
#   SSH_KEY   SSH 私钥路径（默认 ~/.ssh/wanyu111_fixed.pem；不要写进仓库）
#   SSH_HOST  user@host（本机在 tools/anhui_web/.deploy_wan.local 提供，不入库）
#   SITE_ROOT 服务器站点目录（默认 /var/www/wan.kaogong.art）
#   APPLY_NGINX=1 额外安装 docs/ops/wan-kaogong-perf.conf 并 reload nginx（默认关；
#                 首次还需在 server{} 内人工加一行 include snippets/wan-kaogong-perf.conf;）
#   FULL_BUILD=1  先跑 tools/anhui_web/release.py 全门禁再部署（默认 0，用现有产物）
set -euo pipefail

DRY_RUN="${DRY_RUN:-1}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/wanyu111_fixed.pem}"
# P0-7: 生产主机不再硬编码入库（check_secrets.sh 会拦）；本机覆盖文件 .deploy_wan.local（gitignored）提供 SSH_HOST
LOCAL_CONF="$(dirname "${BASH_SOURCE[0]}")/.deploy_wan.local"
[ -f "$LOCAL_CONF" ] && . "$LOCAL_CONF"
SSH_HOST="${SSH_HOST:?export SSH_HOST=ubuntu@<host>，或写入 tools/anhui_web/.deploy_wan.local}"
SITE_ROOT="${SITE_ROOT:-/var/www/wan.kaogong.art}"
APPLY_NGINX="${APPLY_NGINX:-0}"
FULL_BUILD="${FULL_BUILD:-0}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SITE_DIR="$(cd "$REPO/.." && pwd)/网站"
# Git Bash 下 pwd 产生 /c/... 形式路径，直接传给 Windows 原生 python 会
# 打不开（2026-09-10 实测：verify_maintainable_site 对 /c/... 报
# manifest.present FAIL，fail-closed 中止于第 2 步，未触碰服务器）。
# cygpath -m 归一化为 C:/... 混合形式；无 cygpath 的 Linux 环境原样跳过。
command -v cygpath >/dev/null 2>&1 && SITE_DIR="$(cygpath -m "$SITE_DIR")"
TMP_TGZ="/tmp/wan-deploy-$(date +%Y%m%d%H%M%S).tgz"

log(){ printf '\033[1;36m[deploy_wan]\033[0m %s\n' "$*"; }
run(){ if [ "$DRY_RUN" = "1" ]; then log "DRY: $*"; else log "RUN: $*"; "$@"; fi; }

# 0) 预检
command -v ssh >/dev/null && command -v scp >/dev/null && command -v tar >/dev/null
if [ ! -f "$SSH_KEY" ]; then log "缺少私钥 $SSH_KEY —— 中止（不要把私钥提交进仓库）。"; exit 1; fi
if [ ! -f "$SITE_DIR/index.html" ]; then log "未找到 canonical 发布树 网站/index.html，先跑 release.py（原子提升）。"; exit 1; fi
log "repo=$REPO site=网站（v17.8.6 发布树，含 .gz 预压缩）"
[ "$DRY_RUN" = "1" ] && log "当前为 DRY_RUN；真正部署请：DRY_RUN=0 $0"

# 1) 可选：完整门禁构建（release.py 会跑测试→staging 构建→校验→原子提升→记录）
if [ "$FULL_BUILD" = "1" ]; then
  ( cd "$REPO" && run python tools/anhui_web/release.py )
fi

# 2) 构建前磁盘校验（快，防把坏产物推上线；v17.8.6 实测 canonical 树 302/0）
( cd "$REPO" && run python tools/anhui_web/verify_maintainable_site.py "$SITE_DIR" )

# 3) 打包站点内容（staging 拷贝改名 maintainable/，保持远端 /maintainable/ 布局）
log "打包 网站/ → maintainable/ → $TMP_TGZ"
if [ "$DRY_RUN" != "1" ]; then
  STAGE="$(mktemp -d)"
  cp -r "$SITE_DIR" "$STAGE/maintainable"
  tar czf "$TMP_TGZ" -C "$STAGE" maintainable
  rm -rf "$STAGE"
else
  log "DRY: cp -r 网站 <stage>/maintainable && tar czf $TMP_TGZ -C <stage> maintainable"
fi

# 4) 上传
run scp -i "$SSH_KEY" "$TMP_TGZ" "$SSH_HOST:/tmp/"

# 5) 远端解包 + 属主（原地覆盖；旧布局遗留文件不影响 SW/manifest 寻址，可后续人工清理）
log "远端解包到 $SITE_ROOT/maintainable"
REMOTE_SCRIPT=$(cat <<REMOTE
set -euo pipefail
sudo mkdir -p ${SITE_ROOT}
tar xzf /tmp/$(basename "$TMP_TGZ") -C ${SITE_ROOT}
sudo chown -R www-data:www-data ${SITE_ROOT}/maintainable
rm -f /tmp/$(basename "$TMP_TGZ")
echo "OK deployed"
REMOTE
)
if [ "$DRY_RUN" = "1" ]; then
  log "DRY: ssh -i $SSH_KEY $SSH_HOST 'sudo bash -s' <<REMOTE ... (见下)"
  printf '%s\n' "$REMOTE_SCRIPT"
else
  ssh -i "$SSH_KEY" "$SSH_HOST" "sudo bash -s" <<<"$REMOTE_SCRIPT"
fi

# 6) 可选：安装 nginx 提速/缓存分级片段并 reload（gzip_static + /data/ immutable + shell no-cache）
if [ "$APPLY_NGINX" = "1" ]; then
  NGINX_CONF="$REPO/docs/ops/wan-kaogong-perf.conf"
  log "安装 nginx 提速片段 $NGINX_CONF"
  run scp -i "$SSH_KEY" "$NGINX_CONF" "$SSH_HOST:/tmp/wan-kaogong-perf.conf"
  NGINX_SCRIPT='
set -euo pipefail
sudo cp /tmp/wan-kaogong-perf.conf /etc/nginx/snippets/wan-kaogong-perf.conf
# 需在 wan.kaogong.art 的 server{} 内确保有一行： include snippets/wan-kaogong-perf.conf;
# 该 include 由人工首次添加（避免脚本改站点配置出错）。此处仅校验+重载：
sudo nginx -t && sudo systemctl reload nginx && echo "nginx reloaded"
'
  if [ "$DRY_RUN" = "1" ]; then log "DRY nginx: 复制片段到 snippets + nginx -t + reload（server{} 的 include 需人工加一次）"; else ssh -i "$SSH_KEY" "$SSH_HOST" "sudo bash -s" <<<"$NGINX_SCRIPT"; fi
else
  log "APPLY_NGINX=0：跳过 nginx 提速/缓存分级安装（A2④ immutable 头与 gzip_static 靠它生效，建议尽快开启）"
fi

# 7) 线上冒烟验证（v17.8.6 真实路径）
log "线上验证（可硬刷新清缓存； SW/manifest 驱动缓存，回访流量应为 KB 级）"
run curl -s -o /dev/null -w 'maintainable/index.html HTTP %{http_code}\n' "https://wan.kaogong.art/maintainable/"
run curl -s --compressed -o /dev/null -w 'data/site-manifest.json HTTP %{http_code}\n' "https://wan.kaogong.art/maintainable/data/site-manifest.json" || true
log "完成。提醒：那把 SSH 私钥随交接包分发有泄露风险，建议尽快在腾讯云控制台重置密钥对。"
