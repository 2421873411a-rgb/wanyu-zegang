# -*- coding: utf-8 -*-
"""P3 数据完整度/科学性/闭环深研（v2，路径全部 join）。"""
import json, gzip, hashlib, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
R = r'E:\zcode\择岗'
WEB = os.path.join(R, '网站')
DATA = os.path.join(WEB, 'data')
CAN = os.path.join(R, '项目源码', 'canonical', 'cycles')

def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

print('=== 1) site-manifest 哈希链 vs 磁盘文件 ===')
man = json.load(open(os.path.join(DATA, 'site-manifest.json'), encoding='utf-8'))
bad = checked = 0
for c in man['cycles']:
    for name, m in (c.get('modules') or {}).items():
        p = os.path.join(WEB, *str(m['data']).split('/'))
        checked += 1
        if not os.path.exists(p):
            print(f'  缺文件: {p}'); bad += 1; continue
        if sha(p) != m.get('sha256'):
            print(f'  哈希不符: {m["data"]}'); bad += 1
print(f'  {checked} 模块 / {bad} 异常')

print('=== 2) .gz 与 .json 内容同步性 ===')
badz = checkedz = 0
for c in man['cycles']:
    for name, m in (c.get('modules') or {}).items():
        p = os.path.join(WEB, *str(m['data']).split('/'))
        gz = p + '.gz'
        if not os.path.exists(gz):
            print(f'  缺 .gz: {m["data"]}'); badz += 1; continue
        checkedz += 1
        raw = open(p, 'rb').read()
        if gzip.decompress(open(gz, 'rb').read()) != raw:
            print(f'  .gz 内容不一致: {m["data"]}'); badz += 1
print(f'  {checkedz} 对 / {badz} 不一致')

print('=== 3) canonical → site 闭环（2026）===')
can = json.load(open(os.path.join(CAN, '2026.json'), encoding='utf-8'))
jl = json.load(open(os.path.join(DATA, 'cycles', '2026', 'jobs_lite.json'), encoding='utf-8'))
can_rows = can.get('allMajors', {}).get('rows') or can.get('rows') or []
lite_rows = jl['allMajors']['rows']
active_lite = [r for r in lite_rows if not r.get('record_status') or r.get('record_status') == 'active']
can_ids = {r.get('job_id') for r in can_rows}
lite_ids = {r.get('job_id') for r in lite_rows}
print(f'  canonical={len(can_rows)} lite总={len(lite_rows)} lite active={len(active_lite)} id集相等={can_ids == lite_ids}')

print('=== 4) overview 口径 vs lite 复算 ===')
ov = json.load(open(os.path.join(DATA, 'cycles', '2026', 'overview.json'), encoding='utf-8'))
posts = len(active_lite)
rec = sum(int(r.get('num') or 0) for r in active_lite)
ovm = ov.get('allMajors', {}).get('meta', {})
print(f'  复算 active={posts} recruits={rec} | overview posts={ovm.get("posts")} recruits={ovm.get("recruits")} match={posts == ovm.get("posts") and rec == ovm.get("recruits")}')

print('=== 5) 「仅限」学历语义量化 ===')
def xl_min_tier(xl):
    text = str(xl or '')
    if not text or '不限' in text or '无' in text: return 0
    tiers = [t for kw, t in [('博士',5),('硕士',4),('研究生',4),('本科',3),('学士',3),('大专',2),('专科',2),('中专',1),('高中',1),('中师',1)] if kw in text]
    return min(tiers) if tiers else 0
jx = [r for r in active_lite if '仅限' in str(r.get('xl') or '')]
dist = {}
for r in jx:
    dist[r.get('xl')] = dist.get(r.get('xl'), 0) + 1
print(f'  「仅限」行数={len(jx)} 分布={dist}')
jx_bk = [r for r in jx if xl_min_tier(r.get('xl')) == 3]
print(f'  「仅限本科」={len(jx_bk)} 行：当前实现下 硕士/博士用户 会被 educationAllows 放行看到')

print('=== 6) req_fields 置信度 ===')
rf = json.load(open(os.path.join(DATA, 'req-fields-2026.json'), encoding='utf-8'))
fields = {k: v for k, v in rf.items() if str(k).startswith('job-')}
conf = {}
for v in fields.values():
    conf[v.get('confidence')] = conf.get(v.get('confidence'), 0) + 1
print(f'  条目={len(fields)} schema={rf.get("schema")} 置信度={conf}')

print('=== 7) 日历日期合理性（今天 2026-09-07）===')
cal = json.load(open(os.path.join(DATA, 'calendar.json'), encoding='utf-8'))
events = cal.get('events') or cal.get('items') or []
past = [e for e in events if str(e.get('date', '')) < '2026-09-07']
future = [e for e in events if str(e.get('date', '')) >= '2026-09-07']
print(f'  事件={len(events)} 过期={len(past)} 未来={len(future)}')
for e in sorted(future, key=lambda x: str(x.get('date', '')))[:3]:
    print('  ', e.get('date'), e.get('title') or e.get('name'))

print('=== 8) major_city 溯源哈希 ===')
for cyc in ('2024', '2025', '2026'):
    mc = json.load(open(os.path.join(DATA, 'cycles', cyc, 'major_city.json'), encoding='utf-8'))
    jl_sha = sha(os.path.join(DATA, 'cycles', cyc, 'jobs_lite.json'))
    print(f'  {cyc}: source_sha256==lite.sha256 ? {str(mc.get("source_sha256", "")) == jl_sha}')
