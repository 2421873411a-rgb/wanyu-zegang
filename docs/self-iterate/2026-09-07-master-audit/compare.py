# -*- coding: utf-8 -*-
"""期望 vs UI 实测比对。用法: python compare.py actual.json"""
import json, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BASE = r'E:\zcode\择岗\docs\self-iterate\2026-09-07-master-audit'
expected = json.load(open(f'{BASE}/expected.json', encoding='utf-8'))
actual = json.load(open(f'{BASE}/{sys.argv[1] if len(sys.argv) > 1 else "actual.json"}', encoding='utf-8'))

def num(s):
    m = re.search(r'([\d,]+)', str(s or ''))
    return int(m.group(1).replace(',', '')) if m else 0

mismatches = 0
rows_out = []
for pid, exp in expected.items():
    act = actual.get(pid)
    if not act:
        rows_out.append(f'{pid} MISSING in actual')
        mismatches += 1
        continue
    diffs = []
    if act.get('error'):
        diffs.append(f'页面错误: {act["error"]}')
    ui_total = num(act.get('total'))
    if ui_total != exp['total']:
        diffs.append(f"total UI={ui_total} 期望={exp['total']}")
    if exp['tier_active']:
        for key, cls, label in (('t1', 't1', '明确含'), ('t2', 't2', '类内'), ('t3', 't3', '不限')):
            ui_v = num(act.get(key))
            if ui_v != exp[key]:
                diffs.append(f'{label} UI={ui_v} 期望={exp[key]}')
    for key, label in (('fierce', '激烈'), ('medium', '适中'), ('easy', '较小')):
        ui_v = num(act.get(key))
        if ui_v != exp[key]:
            diffs.append(f'竞争{label} UI={ui_v} 期望={exp[key]}')
    if act.get('page_rows') is not None and exp['total'] > 0 and int(act['page_rows']) == 0:
        diffs.append('首页 0 行但有结果')
    if diffs:
        mismatches += 1
        rows_out.append(f'{pid} ✗ ' + ' | '.join(diffs))
    else:
        rows_out.append(f'{pid} ✓ total={exp["total"]}')
print('\n'.join(rows_out))
print(f'\n===== 比对完成: {len(expected)} 人中 {mismatches} 人存在差异 =====')
