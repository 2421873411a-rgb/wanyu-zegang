"""P6 (P0-5): 工具链反向同步 — templates/build/release 与现役 v17.7.0 对齐"""
import re, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from common import SRC, check, finish, read

TOOL = os.path.join(SRC, 'tools', 'anhui_web')
sw_t = read(os.path.join(TOOL, 'templates', 'maintainable-sw.js'))
build_py = read(os.path.join(TOOL, 'build_maintainable_site.py'))
release_py = read(os.path.join(TOOL, 'release.py'))

check('template sw VERSION = wanyu-shell-v41', 'wanyu-shell-v41' in sw_t)
m = re.search(r'PRECACHE\s*=\s*\[(.*?)\]', sw_t, re.S)
n_precache = len(re.findall(r'["\'][^"\']+["\']', m.group(1))) if m else 0
check('template PRECACHE has 15 entries', n_precache == 15, f'{n_precache} entries')

check('build_maintainable_site.py RELEASE = v17.7.1', bool(re.search(r'RELEASE\s*=\s*["\']v17\.7\.1["\']', build_py)))
check('release.py no hardcoded v17.6.4', not re.search(r'["\']v17\.6\.4["\']', release_py))

# shipped index vs template: ghost assets absent in both
site_index = read(os.path.join(os.path.dirname(build_py), '..', '..', '..', '网站', 'index.html')) if False else None
import glob
idx = glob.glob(r'E:\zcode\择岗\网站\index.html')
tmpl_idx = glob.glob(os.path.join(TOOL, 'templates', '*.html')) + glob.glob(os.path.join(TOOL, 'templates', '*index*'))
GHOST = re.compile(r'(search-history|share-link|toast|v17-enhancements)\.(js|css)')
for label, files in (('site index', idx), ('template index', tmpl_idx)):
    hits = []
    for p in files:
        c = read(p)
        hits += [(p, m.group(0)) for m in GHOST.finditer(c)]
    check(f'{label}: no ghost asset links', not hits, str(hits[:3]))

# index template version stamp
if tmpl_idx:
    t = read(tmpl_idx[0])
    check('embedded index uses {RELEASE} (now v17.7.1) and no ghosts', 'assets/maintainable-tokens.css?v={RELEASE}' in read(os.path.join(TOOL, 'build_maintainable_site.py')))
finish()
