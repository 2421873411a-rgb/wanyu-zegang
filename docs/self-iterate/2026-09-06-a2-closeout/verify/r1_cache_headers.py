"""R1 (A2④ 收口): /data/ immutable 缓存头 — perf conf 补齐分级缓存并入库;
   A2 既有前端胜利(?sha= 寻址/SW cache-first/校验降级)作为回归锁不得倒退"""
import os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, SITE, SRC, check, finish, read, git

CONF = os.path.join(SRC, 'docs', 'ops', 'wan-kaogong-perf.conf')

# ---------- 新增要求（实现前必须 FAIL） ----------
tracked = git('ls-files', '--', '项目源码/docs/ops/wan-kaogong-perf.conf').strip()
check('perf conf 已入库（git ls-files 非空）', bool(tracked), tracked or 'untracked: 文件只存在于本机，APPLY_NGINX 在正式仓库是断的')

conf = read(CONF) if os.path.exists(CONF) else ''
# 剥离注释行再解析 location，避免说明文字里的 "location/server{}" 干扰匹配
conf_code = re.sub(r'(?m)^\s*#.*$', '', conf)
locs = [(m.replace('\\', ''), b) for m, b in re.findall(r'location\s+([^\{]+)\{([^\}]*)\}', conf_code)]
data_loc = next(((m, b) for m, b in locs if '/maintainable/data/' in m), None)
check('/data/ location 存在（锚定 /maintainable/data/）', data_loc is not None,
      data_loc[0].strip() if data_loc else 'missing: conf 无 /data/ 缓存头，回访仍走协商缓存')
if data_loc:
    body = data_loc[1]
    check('/data/ 头 = public, max-age=31536000, immutable',
          'immutable' in body and 'max-age=31536000' in body and 'public' in body,
          body.strip()[:100])
shell_loc = next(((m, b) for m, b in locs if 'index' in m and 'sw.js' in m), None)
check('index.html+sw.js 有 no-cache location（SW/manifest 驱动的前提）',
      shell_loc is not None and 'no-cache' in shell_loc[1],
      shell_loc[1].strip()[:80] if shell_loc else 'missing')

# ---------- A2 既有胜利回归锁（实现前后都必须 PASS） ----------
check('conf 保留 gzip_static on（P0-9① 成果不倒退）', 'gzip_static on;' in conf)
data_js = read(os.path.join(SITE, 'assets', 'maintainable-data.js'))
check('data loader 仍为 manifest 驱动 ?sha= URL', '?sha=${' in data_js and 'entry?.sha256' in data_js)
check('带 sha 走字节校验降级、无 sha 才全量 SHA-256 校验（A2⑤ 校验降级回退）',
      'if (!addressed && entry?.sha256 && globalThis.crypto?.subtle && bytes)' in data_js)
sw = read(os.path.join(SITE, 'sw.js'))
check('SW 对 ?sha= JSON 走 cache-first', 'searchParams.has("sha")' in sw and 'caches.match(request)' in sw)
check('SW 清理同路径旧 sha 条目（activate 语义）', 'kUrl.searchParams.get("sha") !== url.searchParams.get("sha")' in sw)
for f in ('index.html.gz', 'sw.js.gz', 'data/site-manifest.json.gz'):
    check(f'gzip_static 前提在盘: {f}', os.path.exists(os.path.join(SITE, f)))
finish()
