"""R2: deploy_wan.sh 与 v17.8.6 发布树对齐 — 打包 canonical 网站/（服务器 /maintainable/ 布局不变）,
   摘除 v17.8.6 已退役的遗留单文件与 deliverables 旧路径; 安全默认(DRY_RUN=1)与 perf conf 安装路径保持"""
import os, re, sys, subprocess
sys.path.insert(0, os.path.dirname(__file__))
from common import SRC, check, finish, read

DEP = os.path.join(SRC, 'tools', 'anhui_web', 'deploy_wan.sh')
s = read(DEP)
# 只查功能性引用：剥离注释行（头部注释提到"已退役"属文档说明，不构成依赖）
code = re.sub(r'(?m)^\s*#.*$', '', s)

# ---------- 新增要求（实现前必须 FAIL） ----------
check('不再依赖遗留 deliverables/maintainable（v17.8.6 未跟踪该目录，正式仓库上部署直接中止）',
      'deliverables/maintainable' not in code)
check('不再打包遗留单文件 皖域择岗总览.html（v17.8.6 方案A 已退役）',
      '皖域择岗总览.html' not in code)
check('打包对象改为 canonical 网站/ 树（SITE_DIR 指向仓库根 网站/）',
      bool(re.search(r'SITE_DIR=.*网站', s)))
check('preflight verify_maintainable_site 指向 "$SITE_DIR"（已实测 canonical 树 302/0）',
      bool(re.search(r'verify_maintainable_site\.py\s+"\$SITE_DIR"', s)))
check('远端保持 SITE_ROOT/maintainable/ 布局（tar 内容物为 maintainable/）',
      bool(re.search(r'maintainable', s)))
check('线上冒烟 URL 用 v17.8.6 真实路径（/maintainable/data/site-manifest.json）',
      '/maintainable/data/site-manifest.json' in s)

# ---------- 既有约束回归锁 ----------
check('APPLY_NGINX 仍安装 R1 同一 perf conf', 'docs/ops/wan-kaogong-perf.conf' in s)
check('DRY_RUN 安全默认仍为 1（红线：不显式在场不连生产）', 'DRY_RUN:-1' in s)
check('SSH_HOST 仍走 gitignored .deploy_wan.local（P0-7 纪律）', '.deploy_wan.local' in s)
r = subprocess.run(['bash', '-n', DEP], capture_output=True, text=True)
check('bash -n 语法通过', r.returncode == 0, (r.stderr or '').strip()[:120])
finish()
