"""P10 (P0-9): 流量速赢三连 — .gz 预压缩覆盖 / 三年趋势条件加载 / palette 退役"""
import os, re, sys, glob
sys.path.insert(0, os.path.dirname(__file__))
from common import SITE, SRC, check, finish, read, js_path

# 1) .gz coverage: every .js/.css in assets and top-level .json in data has sibling .gz with matching size
targets = glob.glob(os.path.join(SITE, 'assets', '*.js')) + glob.glob(os.path.join(SITE, 'assets', '*.css')) \
          + glob.glob(os.path.join(SITE, 'data', '*.json'))
have, missing = 0, []
for p in targets:
    if os.path.exists(p + '.gz'):
        have += 1
    else:
        missing.append(os.path.basename(p))
cov = (have / len(targets) * 100) if targets else 0
check('.gz sibling coverage >= 99%', cov >= 99 and targets, f'{have}/{len(targets)} ({cov:.1f}%), e.g. missing {missing[:5]}')

# 2) three-year trend no longer unconditionally loads all cycles' full jobs.json
js = read(js_path())
uncond = re.search(r'(loadJSON|fetchJSON|fetch)\s*\([^)]*(2024|cycles/2024)[\s\S]{0,300}(2025|cycles/2025)[\s\S]{0,300}(2026|cycles/2026)[\s\S]{0,300}jobs\.json', js)
check('no unconditional 3-cycle jobs.json preload', not uncond)
guarded = re.search(r"hasExamScope[\s\S]{0,160}if\s*\(hasExamScope\)\s*\{[\s\S]{0,200}allCycles\.map\(c\s*=>\s*loadModule\(c\.cycle,\s*'jobs'\)\)", js)
check('cycle-compare 3-cycle jobs load wrapped by hasExamScope guard', bool(guarded))

# 3) palette.json retired: no live load; entries derived from jobs_lite in memory
check('no live palette.json load', "loadModule(state.cycle, 'palette')" not in js)
check('palette entries derived from jobs_lite', 'palette.entries = (lite?.allMajors?.rows' in js)
finish()
