# -*- coding: utf-8 -*-
"""50人画像期望值计算器（独立于站点 JS 实现，按 DOCUMENTED 语义复算）。

语义来源：项目源码/tools/anhui_web/templates/maintainable-site.js
  - normalize: 去空白 + lower
  - 行过滤: keyword(srcText includes) / major(tier or substring) / city(==) / exam / education / steal / profileFail
  - tier: major-index.postings explicit / by_class(经 classes.members) / unlimited；三者皆空才回退 substring
  - educationAllows: xlMinTier(xl) <= xlMinTier(user)
  - profileFail: 仅 req_fields confidence==high 才参与；fresh_only/party_only/cert_legal/gender/age_max 一票否决
输出: expected.json  {pid: {total, t1, t2, t3, fierce, medium, easy, major_path, dropped_by_profile, first_ids}}
"""
import json, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os as _os; ROOT = _os.environ.get('WANYU_DATA_ROOT', r'E:\zcode\择岗\网站\data')
CYCLE = '2026'

def normalize(v):
    return re.sub(r'\s+', '', str(v or '')).lower()

def clean_major_option(value):
    text = str(value or '').strip()
    if not re.search(r'[\u4e00-\u9fffA-Za-z]', text):
        return ''
    text = re.sub(r'^[A-Za-z](?=[\u4e00-\u9fff])', '', text)
    text = re.sub(r'(?<![A-Za-z0-9])[A-Za-z]?\d{4,8}(?![A-Za-z0-9])', '', text)
    text = re.sub(r'\s*[/\\|,，;；]+\s*', '、', text)
    text = re.sub(r'、{2,}', '、', text)
    text = re.sub(r'^[\s/\\|,，;；:：._\-—()（）\[\]【】、]+|[\s/\\|,，;；:：._\-—()（）\[\]【】、]+$', '', text)
    return text.strip()

EDU_TIER = [('博士', 5), ('硕士', 4), ('研究生', 4), ('本科', 3), ('学士', 3), ('大专', 2), ('专科', 2), ('中专', 1), ('高中', 1), ('中师', 1)]

def xl_min_tier(xl):
    text = str(xl or '')
    if not text or '不限' in text or '无' in text:
        return 0
    tiers = [t for kw, t in EDU_TIER if kw in text]
    return min(tiers) if tiers else 0

def education_allows(user_level, xl):
    if not user_level or user_level == '不限':
        return True
    xl_tier = xl_min_tier(xl)
    if not xl_tier:
        return True
    # F-EDU-1 修复后的语义：「仅限X」= 精确档位
    if '仅限' in str(xl or ''):
        return xl_tier == xl_min_tier(user_level)
    return xl_tier <= xl_min_tier(user_level)

def exam_row_matches(row, exam):
    if not exam or exam == '全部':
        return True
    value = str(row.get('exam') or '')
    if exam == '公务员':
        return ('省考' in value) or ('国考' in value)
    if exam == '事业编':
        return '事业' in value
    return exam in value

def source_text(row):
    return ' '.join(str(row.get(k) or '') for k in ('code', 'city', 'exam', 'unit', 'zw', 'zy', 'bz', 'lb'))

def main():
    jl = json.load(open(f'{ROOT}/cycles/{CYCLE}/jobs_lite.json', encoding='utf-8'))
    rows_all = jl['allMajors']['rows']
    rows = [r for r in rows_all if not r.get('record_status') or r.get('record_status') == 'active']
    mi = json.load(open(f'{ROOT}/cycles/{CYCLE}/major-index.json', encoding='utf-8'))
    postings = mi.get('postings', {})
    classes = mi.get('classes', [])
    rf_doc = json.load(open(f'{ROOT}/req-fields-2026.json', encoding='utf-8'))
    rf_fields = {k: v for k, v in rf_doc.items() if k.startswith('job-')}
    personas = json.load(open(r'E:\zcode\择岗\docs\self-iterate\2026-09-07-master-audit\personas.json', encoding='utf-8'))['personas']

    out = {}
    for p in personas:
        major = p.get('major', '')
        major_q = normalize(major)
        keyword = normalize(p.get('keyword', ''))
        city = p.get('city', '')
        education = p.get('education', '')
        exam = p.get('exam', '')
        steal = bool(p.get('steal'))
        prof = p.get('profile', {}) or {}
        prof_active = any(prof.get(k) for k in ('gender', 'fresh', 'party', 'legal', 'age'))

        # tier 构建（同语义：unlimited 恒非空 → 只要 major 非空 tier 即激活）
        tier = None
        path = 'none'
        if major_q:
            explicit = set(postings.get('explicit', {}).get(major_q, []))
            by_class = set()
            for c in classes:
                if major_q in (c.get('members') or []):
                    for jid in postings.get('by_class', {}).get(c.get('key'), []) or []:
                        by_class.add(jid)
            if major_q in postings.get('by_class', {}):
                by_class.update(postings['by_class'][major_q])
            unlimit = set(postings.get('unlimited', []))
            if explicit or by_class or unlimit:
                tier = {'explicit': explicit, 'byClass': by_class, 'unlimit': unlimit}
                if explicit:
                    path = 'explicit'
                elif by_class:
                    path = 'class'
                else:
                    path = 'unlimit-only'

        def row_tier(row):
            if not tier:
                return 0
            jid = str(row.get('job_id') or row.get('row_id') or row.get('code') or '')
            if jid in tier['explicit']:
                return 1
            if jid in tier['byClass']:
                return 2
            if jid in tier['unlimit']:
                return 3
            return 9

        # JS ?? 语义的忠实移植：仅 null/None 触发回退，0/'' 不回退
        def recruits_of(row):
            v = row.get('num')
            if v is None:
                v = row.get('recruits')
            if v is None:
                v = 0
            return v

        def examinees_of(row):
            co = row.get('competition_observations')
            if isinstance(co, dict):
                ev = co.get('examinees')
                if isinstance(ev, dict) and ev.get('value') is not None:
                    return ev.get('value')
            bm = row.get('bm')
            if bm is not None:
                return bm
            return 0

        kept = []
        dropped_by_profile = 0
        for row in rows:
            raw_major = normalize(row.get('zy'))
            readable = normalize(clean_major_option(row.get('zy')))
            if keyword and keyword not in normalize(source_text(row)):
                continue
            if major_q:
                if tier:
                    if row_tier(row) == 9:
                        continue
                elif major_q not in raw_major and major_q not in readable:
                    continue
            if city and str(row.get('city') or row.get('reg') or '') != city:
                continue
            if not exam_row_matches(row, exam):
                continue
            if education and not education_allows(education, row.get('xl')):
                continue
            if steal:
                if not (recruits_of(row) >= 3 and examinees_of(row) > 0):
                    continue
            if prof_active:
                rf = rf_fields.get(str(row.get('job_id') or ''))
                if rf and rf.get('confidence') == 'high':
                    fail = False
                    if rf.get('fresh_only') and prof.get('fresh') == 'no':
                        fail = True
                    if rf.get('party_only') and prof.get('party') == 'no':
                        fail = True
                    if rf.get('cert_legal') and prof.get('legal') == 'no':
                        fail = True
                    if rf.get('gender') == 'male' and prof.get('gender') == 'female':
                        fail = True
                    if rf.get('gender') == 'female' and prof.get('gender') == 'male':
                        fail = True
                    if rf.get('age_max') is not None and prof.get('age') and int(prof['age']) > int(rf['age_max']):
                        fail = True
                    if fail:
                        dropped_by_profile += 1
                        continue
            kept.append(row)

        t1 = sum(1 for r in kept if row_tier(r) == 1)
        t2 = sum(1 for r in kept if row_tier(r) == 2)
        t3 = sum(1 for r in kept if row_tier(r) == 3)
        fierce = medium = easy = 0
        for r in kept:
            num = recruits_of(r)
            bm = examinees_of(r)
            if bm > 0 and num > 0:
                ratio = bm / num
                if ratio >= 5:
                    fierce += 1
                elif ratio >= 2:
                    medium += 1
                else:
                    easy += 1
        out[p['id']] = {
            'desc': p.get('desc', ''),
            'total': len(kept),
            't1': t1, 't2': t2, 't3': t3,
            'fierce': fierce, 'medium': medium, 'easy': easy,
            'major_path': path,
            'dropped_by_profile': dropped_by_profile,
            'tier_active': bool(tier),
        }

    with open(r'E:\zcode\择岗\docs\self-iterate\2026-09-07-master-audit\expected.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f'{"pid":4} {"total":>6} {"t1":>5} {"t2":>5} {"t3":>5} {"profDrop":>8}  path           desc')
    for pid, e in out.items():
        print(f'{pid:4} {e["total"]:>6} {e["t1"]:>5} {e["t2"]:>5} {e["t3"]:>5} {e["dropped_by_profile"]:>8}  {e["major_path"]:14} {e["desc"][:38]}')

if __name__ == '__main__':
    main()
