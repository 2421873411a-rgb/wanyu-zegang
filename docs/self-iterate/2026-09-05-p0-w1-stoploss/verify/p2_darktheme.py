"""P2 (P0-1): 深色主题修复 —
1) shipped JS 中变更徽章不再有内联 hex/rgb 颜色样式
2) CSS 中考试类别按钮容器/页头在深色主题有 token 覆盖（不允许白底残留）
3) 变更徽章四色在浅色与深色主题下均由 token 成对提供，且按 WCAG 计算：
   徽章文字色对徽章底 ≥4.5；图表线条色对页面底 ≥3
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import SITE, check, finish, read, js_path, wcag_ratio, parse_color

js = read(js_path())
css_files = []
for root, _, fs in os.walk(os.path.join(SITE, 'assets')):
    for f in fs:
        if f.endswith('.css'):
            css_files.append(os.path.join(root, f))
css = {os.path.basename(p): read(p) for p in css_files}

# 1) badge inline colors gone: find badge-ish render code, forbid hex/rgb in inline styles near it
badges = [m.start() for m in re.finditer(r'badge', js, re.I)]
inline_bad = []
for pos in badges:
    window = js[max(0, pos-300): pos+300]
    if re.search(r'style\s*=\s*["\'][^"\']*(#[0-9a-fA-F]{3,8}|rgb)', window):
        inline_bad.append(pos)
check('no inline hex/rgb colors in badge rendering', not inline_bad,
      f'{len(badges)} badge mentions, {len(inline_bad)} inline-color hits')

# 2) dark-theme overrides for picker container & header exist
dark_rules = []
for name, c in css.items():
    for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', c):
        sel, body = m.group(1).strip(), m.group(2)
        if re.search(r'(data-theme=["\']?dark|\.theme-dark|prefers-color-scheme:\s*dark)', sel):
            dark_rules.append((name, sel, body))
picker_dark = [r for r in dark_rules if '.maintain-cycle-picker' in r[1]]
header_dark = [r for r in dark_rules if '.maintain-header' in r[1]]
check('dark override rules for .maintain-cycle-picker', bool(picker_dark), f'{len(picker_dark)} rules')
check('dark override rules for .maintain-header', bool(header_dark), f'{len(header_dark)} rules')
no_white = not any(re.search(r'background(-color)?\s*:\s*(#fff\b|#ffffff\b|white\b)', body, re.I) for _, _, body in picker_dark)
check('dark picker override not white background', no_white)

# 3) change-badge palette tokens in both themes + WCAG
# block-scoped scan: a token belongs to 'dark' only if its rule's selector declares the dark theme
blocks = []  # (css_text, selector, body)
for name, c in css.items():
    c_nc = re.sub(r'/\*.*?\*/', '', c, flags=re.S)  # comments may mention dark theme; strip before scanning
    for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', c_nc):
        blocks.append((name, m.group(1).strip(), m.group(2)))
tokens = {'light': {}, 'dark': {}}
for _, sel, body in blocks:
    is_dark = bool(re.search(r'data-theme=["\']?dark|theme-dark|prefers-color-scheme:\s*dark', sel, re.I))
    theme = 'dark' if is_dark else 'light'
    if not re.match(r'^\s*:root', sel) and not is_dark:
        continue  # component rules may only reference tokens, not define them (site rule)
    for var, val in re.findall(r'(--[a-z0-9-]+)\s*:\s*([^;]+);', body):
        tokens[theme][var] = val.strip()

def resolve(val, theme, depth=0):
    if depth > 5 or val is None:
        return None
    val = val.strip()
    m = re.match(r'^var\((--[a-z0-9-]+)(?:,\s*([^)]+))?\)$', val, re.I)
    if m:
        v = tokens[theme].get(m.group(1))
        if v is None and m.group(2) is not None:
            v = m.group(2)
        return resolve(v, theme, depth + 1)
    return val

def composite(color, over):
    """composite a possibly-alpha rgba color over an opaque surface color"""
    if color is None:
        return None
    m = re.match(r'^rgba?\(([^)]+)\)$', color, re.I)
    if not m:
        return parse_color(color)
    parts = [p.strip() for p in m.group(1).split(',')]
    rgb = parse_color('rgb(%s)' % ','.join(parts[:3]))
    a = float(parts[3]) if len(parts) > 3 else 1.0
    if a >= 1.0 or rgb is None or over is None:
        return rgb
    return tuple(a * c + (1 - a) * o for c, o in zip(rgb, over))

CHANGES = ['added', 'withdrawn', 'revised', 'review', 'unchanged']
for theme in ('light', 'dark'):
    surface = parse_color(resolve(tokens[theme].get('--bg-surface'), theme) or '') or \
              (parse_color('#131d31') if theme == 'dark' else parse_color('#ffffff'))
    tested, fails = 0, 0
    for stem in CHANGES:
        fg = parse_color(resolve(tokens[theme].get(f'--changes-{stem}'), theme) or '')
        bg_raw = resolve(tokens[theme].get(f'--changes-{stem}-bg'), theme)
        bg = composite(bg_raw, surface)
        if fg and bg:
            tested += 1
            ratio = wcag_ratio(fg, bg)
            if ratio < 4.5:
                fails += 1
                check(f'badge --changes-{stem} on -bg ({theme})', False, f'ratio {ratio:.2f} < 4.5')
    check(f'badge color pairs resolvable & >=4.5 ({theme})', tested == len(CHANGES) and fails == 0,
          f'{tested}/{len(CHANGES)} pairs tested')

# chart stroke colors: line-chart / slope code in js must use var( not literal hex palette
chart_snip = js[js.find('drawCityTrend') if 'drawCityTrend' in js else 0:]
seg = js[:200000]
lit = [h for h in re.findall(r'(stroke|strokeStyle|color)\s*[:=]\s*["\']?(#[0-9a-fA-F]{6})', seg)]
# only fail on the known chart families (city line 8-color palette etc.)
check('no literal 6-hex stroke palettes in js (charts tokenized)', len(lit) == 0, f'{len(lit)} hits e.g. {lit[:4]}')
finish()
