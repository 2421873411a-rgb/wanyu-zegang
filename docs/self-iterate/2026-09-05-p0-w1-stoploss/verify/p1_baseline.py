"""P1: 网盘最新版落地完整性 — manifest 逐文件 size 对账 + unittest + req-fields 在案"""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, SRC, SITE, check, finish

manifest = json.load(open(os.path.join(ROOT, '_dl', 'manifest.json'), encoding='utf-8'))
BASE = '/AI云空间/皖域择岗'

bad = []
for m in manifest:
    rel = m['path'].replace(BASE, '', 1).lstrip('/')
    dest = os.path.join(ROOT, rel.replace('/', os.sep))
    if not os.path.exists(dest):
        bad.append((rel, 'missing'))
    elif os.path.getsize(dest) != m['size']:
        bad.append((rel, f"size {os.path.getsize(dest)} != {m['size']}"))
check('manifest size audit (4265 files)', not bad, f'{len(manifest)} entries, {len(bad)} bad' + (f' e.g. {bad[:5]}' if bad else ''))

r = subprocess.run([sys.executable, '-m', 'unittest', 'tests.test_supplement_integrity', '-q'],
                   cwd=SRC, capture_output=True, text=True, timeout=600)
print(r.stdout[-1500:]); print(r.stderr[-1500:])
check('unittest tests.test_supplement_integrity', r.returncode == 0, f'rc={r.returncode}')

check('req-fields-2026.json in site data', os.path.exists(os.path.join(SITE, 'data', 'req-fields-2026.json')))
check('site-manifest.json present', os.path.exists(os.path.join(SITE, 'data', 'site-manifest.json')))
finish()
