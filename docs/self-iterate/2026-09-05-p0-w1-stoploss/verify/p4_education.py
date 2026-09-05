"""P4 (P0-3): 学历筛选方向性 — '用户学历等级 >= 岗位最低要求'
校准（round4 执行前）：实现采用 EDU_TIER_KEYWORDS 等级表 + educationAllows（<= 等级比较）；
数据仿真用同一口径镜像在 python 侧复核 jobs_lite 行集。
"""
import re, sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import check, finish, read, js_path, SITE

js = read(js_path())

check('educationAllows helper defined (tier map + <= comparison)',
      'const educationAllows' in js and 'xlMinTier(xl) <= xlMinTier(userLevel)' in js and 'EDU_TIER_KEYWORDS' in js)
check('old includes() education filter removed (0 occurrences)',
      'includes(state.education)' not in js)
check('both filter sites use educationAllows', js.count('educationAllows(state.education, row.xl)') >= 2,
      f"{js.count('educationAllows(state.education, row.xl)')} sites")

lite = os.path.join(SITE, 'data', 'cycles', '2026', 'jobs_lite.json')
data = json.load(open(lite, encoding='utf-8'))
rows = data['allMajors']['rows'] if isinstance(data, dict) and 'allMajors' in data else data

KW = [('博士', 5), ('硕士', 4), ('研究生', 4), ('本科', 3), ('学士', 3), ('大专', 2), ('专科', 2), ('中专', 1), ('高中', 1), ('中师', 1)]
def min_tier(xl):
    text = xl or ''
    if not text or '不限' in text or '无' in text: return 0
    tiers = [t for kw, t in KW if kw in text]
    return min(tiers) if tiers else 0

grad_visible = sum(1 for r in rows if min_tier(r.get('xl')) <= 4)
college_visible = sum(1 for r in rows if min_tier(r.get('xl')) <= 2)
check('sim: 研究生 user sees >7000 rows (old bug: 858)', grad_visible > 7000, f'visible={grad_visible}/{len(rows)}')
check('sim: 大专 user strictly narrower than 研究生', 0 < college_visible < grad_visible, f'college={college_visible}')
finish()
