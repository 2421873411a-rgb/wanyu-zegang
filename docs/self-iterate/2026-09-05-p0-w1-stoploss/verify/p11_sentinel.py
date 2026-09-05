"""P11 (D1 启动): 0 分哨兵修复 — harvester 排零修复 + 离线恢复对账报告一致性"""
import os, re, sys, json, glob
sys.path.insert(0, os.path.dirname(__file__))
from common import SRC, SITE, ROOT, RUN, check, finish, read

harv = read(os.path.join(SRC, 'tools', 'anhui_web', 'harvest_syb_scores.py'))

# 1) agg() must exclude zero scores when deriving min line, and surface n_zero/all_zero
check('harvester derives lo from positive scores only',
      'pos_df = all_df[all_df["score"] > 0]' in harv and 'g_pos = pos_df.groupby' in harv)
check('harvester reports n_zero / all_zero fields',
      bool(re.search(r'n_zero', harv)) and bool(re.search(r'all_zero', harv)))
check('all-zero frames yield lo=None (no 0 landing)',
      'lo": None' in harv and '"line": v.get("lo") or r.get("lo")' in harv)

# 2) recovery report exists and its class counts sum to the sentinel total
rep = os.path.join(RUN, 'evidence', 'p11-recovery-report.json')
if os.path.exists(rep):
    j = json.load(open(rep, encoding='utf-8'))
    total = j.get('sentinel_total', 0)
    cls = (j.get('recoverable', 0), j.get('all_zero', 0), j.get('no_code', 0))
    check('report classes sum to sentinel total', sum(cls) == total, f'{cls} vs total {total}')
    check('recoverable count ~629 (audit figure)', abs(cls[0] - 629) <= 5, f'{cls[0]}')
else:
    check('recovery report present', False, rep)
finish()
