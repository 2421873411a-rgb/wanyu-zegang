"""shared helpers for p* verify scripts — PASS/FAIL accumulator, exit 1 on any FAIL"""
import os, re, sys, glob, json

ROOT = r'E:\zcode\择岗'
SITE = os.path.join(ROOT, '网站')
SRC = os.path.join(ROOT, '项目源码')
RUN = os.path.join(ROOT, r'docs\self-iterate\2026-09-05-p0-w1-stoploss')

_results = []

def check(name, ok, detail=''):
    _results.append((name, bool(ok), detail))
    print(('PASS' if ok else 'FAIL'), '|', name, ('| ' + detail if detail else ''))
    return bool(ok)

def finish():
    fails = [r for r in _results if not r[1]]
    print(f"== {len(_results)-len(fails)}/{len(_results)} checks passed ==")
    sys.exit(1 if fails else 0)

def read(p, binary=False):
    with open(p, 'rb' if binary else 'r', encoding=None if binary else 'utf-8', errors='replace') as f:
        return f.read()

def find_one(pattern, desc):
    hits = glob.glob(pattern, recursive=True)
    if not hits:
        print(f'FAIL | locate {desc}: no match for {pattern}')
        sys.exit(2)
    return hits[0]

def js_path():
    return find_one(os.path.join(SITE, 'assets', 'maintainable-site.js'), 'maintainable-site.js')

def wcag_ratio(fg, bg):
    """fg/bg = (r,g,b) 0-255 floats; returns WCAG contrast ratio"""
    def lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    l1 = 0.2126*lin(fg[0]) + 0.7152*lin(fg[1]) + 0.0722*lin(fg[2])
    l2 = 0.2126*lin(bg[0]) + 0.7152*lin(bg[1]) + 0.0722*lin(bg[2])
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)

def parse_color(v):
    v = v.strip()
    m = re.match(r'^#([0-9a-f]{6})$', v, re.I)
    if m:
        h = m.group(1)
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    m = re.match(r'^#([0-9a-f]{3})$', v, re.I)
    if m:
        h = m.group(1)
        return tuple(int(h[i]*2, 16) for i in range(3))
    m = re.match(r'^rgba?\(([^)]+)\)$', v, re.I)
    if m:
        parts = [p.strip() for p in m.group(1).split(',')]
        vals = []
        for p in parts[:3]:
            vals.append(float(p) if '.' in p or '%' not in p else float(p.strip('%'))/100*255)
        return tuple(vals)
    return None
