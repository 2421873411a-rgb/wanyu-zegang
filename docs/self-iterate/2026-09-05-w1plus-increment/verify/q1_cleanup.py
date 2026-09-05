"""Q1 (A5): 幽灵资产删除 + Legacy 函数摘除 + 无误伤（renderChangelog 事故教训固化）"""
import os, re, subprocess, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import SITE, check, finish, read, js_path

GHOSTS = ['search-history.js', 'search-history.css', 'share-link.js', 'share-link.css', 'toast.js', 'toast.css', 'v17-enhancements.js']
for g in GHOSTS:
    check(f'ghost asset deleted: {g}', not os.path.exists(os.path.join(SITE, 'assets', g)))

scan = []
for pat in ('index.html', 'sw.js', 'manifest.webmanifest', 'assets/*.js', 'assets/*.css', 'data/*.json'):
    scan += glob.glob(os.path.join(SITE, pat))
refs = {}
for f in scan:
    if os.path.basename(f) in GHOSTS:
        continue
    t = read(f)
    for g in GHOSTS:
        if g.split('.')[0] in t:
            refs.setdefault(g, []).append(os.path.basename(f))
check('ghost assets zero-referenced site-wide', not refs, str(refs))

js = read(js_path())
check('no Legacy functions remain', 'Legacy' not in js)
LIVE_RENDERS = ['renderOverview', 'renderRanking', 'renderSearch', 'renderMap', 'renderSalaryMap',
                'renderCompare', 'renderChanges', 'renderSaved', 'renderAuditCenter',
                'renderSupplementEvidence', 'renderHelp', 'renderChangelog', 'renderDetailDrawer',
                'renderNav', 'renderMobileNav', 'renderCyclePicker']
missing = [n for n in LIVE_RENDERS if f'const {n} = ' not in js]
check('all live render functions intact (no collateral excision)', not missing, f'missing: {missing}')

r = subprocess.run(['node', '--check', js_path()], capture_output=True, text=True)
check('node --check passes', r.returncode == 0, r.stderr[:200])
finish()
