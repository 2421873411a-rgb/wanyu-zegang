# -*- coding: utf-8 -*-
"""用户视角数据批次：①导航去工程页 ②幽灵重复行全视图剔除 ③CTA 计数校正"""
import json
from pathlib import Path

PHANTOM_NOTE = "// D2(2026-09-05): 马鞍山 110 个疑似重复收录岗位（华图源跨市复制，成绩公告全部来自六安，见 tools/anhui_web/d2_resolution_report_20260905.txt）——用户视图剔除，数据文件保留审计痕迹"
codes = sorted({str(r["code"]) for r in json.loads(Path("网站/data/cycles/2026/jobs.json").read_text(encoding="utf-8"))["allMajors"]["rows"] if "疑似重复收录" in str(r.get("source_note") or "")})
assert len(codes) == 110, len(codes)
phantom_js = f"""{PHANTOM_NOTE}
  const PHANTOM_CODES = new Set({json.dumps(codes)});
  const isPhantomRow = (row) => Boolean(row) && String(row.city || '') === '马鞍山' && PHANTOM_CODES.has(String(row.code || ''));"""

FILES = (
    "网站/assets/maintainable-site.js",
    "项目源码/tools/anhui_web/templates/maintainable-site.js",
    "网站-lite/assets/maintainable-site.js",
)
edits = [
    # ② rowsFor 全局剔除（检索/榜单/地图/匹配/收藏/面板全走此口）
    ("""  const rowsFor = (payload) => Array.isArray(payload?.allMajors?.rows) ? payload.allMajors.rows : [];""",
     f"""{phantom_js}
  const rowsFor = (payload) => Array.isArray(payload?.allMajors?.rows) ? payload.allMajors.rows.filter((row) => !isPhantomRow(row)) : [];"""),
    # ② palette 同口径
    ("""        palette.entries = (lite?.allMajors?.rows || []).map((row) => ({ id: row.job_id || row.code || '', code: row.code || '', title: row.zw || row.display_title || '', unit: row.unit || '', city: row.city || row.reg || '', exam: row.exam || '' }));""",
     """        palette.entries = (lite?.allMajors?.rows || []).filter((row) => !isPhantomRow(row)).map((row) => ({ id: row.job_id || row.code || '', code: row.code || '', title: row.zw || row.display_title || '', unit: row.unit || '', city: row.city || row.reg || '', exam: row.exam || '' }));"""),
    # ① 移动端更多面板去掉数据说明/变更通报（视图保留，收藏提醒卡可直达）
    ("""${['match', 'cycle_compare', 'salary_map', 'jobs_ranking', 'changes', 'calendar', 'data_boundary', 'help', 'changelog'].map""",
     """${['match', 'cycle_compare', 'salary_map', 'jobs_ranking', 'calendar', 'help', 'changelog'].map"""),
]
for f in FILES:
    p = Path(f)
    t = p.read_text(encoding="utf-8")
    for old, new in edits:
        n = t.count(old)
        assert n == 1, f"{f}: 锚点 {n}!=1 → {old[:60]}"
        t = t.replace(old, new)
    p.write_bytes(t.encode("utf-8"))
    print("OK", f)

# ① index.html：桌面导航移除两入口；CTA ghost 改指报考日历；计数校正；og 描述去掉"变更通报"
p = Path("网站/index.html")
t = p.read_text(encoding="utf-8")
pairs = [
    ('          <a href="#changes" data-maintain-view="changes">变更通报</a>\n', ""),
    ('          <a href="#data_boundary" data-maintain-view="data_boundary">数据说明</a>\n', ""),
    ('<a class="maint-cta__ghost" href="#data_boundary" data-maintain-view="data_boundary">看数据说明</a>',
     '<a class="maint-cta__ghost" href="#calendar" data-maintain-view="calendar">查看报考日历</a>'),
    ('2024—2026 · 28,678 岗 · 42,058 人 · 来源均可本地核对', '2024—2026 · 28,568 岗 · 来源均可本地核对'),
    ('三年 28,678 岗逐岗可溯源：专业匹配亮依据、官方竞争与入围线、变更通报盯招录调整。未公布不显示，推导亮明依据。',
     '三年 28,568 岗逐岗可溯源：专业匹配亮依据、官方竞争与入围线、报考日历盯节点。未公布不显示，推导亮明依据。'),
]
for old, new in pairs:
    n = t.count(old)
    assert n == 1, f"index: 锚点 {n}!=1 → {old[:50]}"
    t = t.replace(old, new)
# 页脚保留数据说明深链（信任入口不灭，只是不占导航）
old_footer = '<span>数据来自官方公告，来源可核对</span>'
assert t.count(old_footer) == 1
t = t.replace(old_footer, old_footer.replace('</span>', ' · <a href="#data_boundary" data-maintain-view="data_boundary">数据说明</a></span>'))
p.write_bytes(t.encode("utf-8"))
print("OK index.html")

# ② build_major_index.py 同口径剔除
p = Path("项目源码/tools/anhui_web/build_major_index.py")
t = p.read_text(encoding="utf-8")
old = '''    jobs_path = SITE / "data" / "cycles" / str(args.cycle) / "jobs.json"
    rows = load_json(jobs_path)["allMajors"]["rows"]'''
new = '''    jobs_path = SITE / "data" / "cycles" / str(args.cycle) / "jobs.json"
    rows = load_json(jobs_path)["allMajors"]["rows"]
    # D2 幽灵重复行剔除口径与前端 rowsFor 一致（马鞍山 110 行，见 d2_resolution_report_20260905.txt）
    phantom = load_json(HERE / "data" / "phantom_codes_2026.json")
    rows = [r for r in rows if not (str(r.get("city")) == "马鞍山" and str(r.get("code")) in set(phantom))]'''
assert t.count(old) == 1
p.write_bytes(t.replace(old, new).encode("utf-8"))
Path("项目源码/tools/anhui_web/data/phantom_codes_2026.json").write_text(json.dumps(codes, ensure_ascii=False, indent=1), encoding="utf-8")
print("OK build_major_index.py + phantom 代码表")
print("补丁完成")
