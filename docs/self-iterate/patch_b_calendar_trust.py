# -*- coding: utf-8 -*-
"""P1/P2 大批次补丁 B：index.html（导航+铁律行）、calendar.json、manifest、CSS"""
import hashlib
import json
from pathlib import Path

# 1) index.html：桌面导航加报考日历 + CTA 铁律行
p = Path("网站/index.html")
t = p.read_text(encoding="utf-8")
old_nav = '<a href="#cycle_compare" data-maintain-view="cycle_compare">三年趋势</a>'
assert t.count(old_nav) == 1, "nav 锚点"
t = t.replace(old_nav, old_nav + '\n          <a href="#calendar" data-maintain-view="calendar">报考日历</a>')
old_cta = '<p class="maint-cta__stats">'
assert t.count(old_cta) == 1, "cta 锚点"
t = t.replace(old_cta, '<p class="maint-cta__trust">本站三条铁律：未公布不显示 · 推导亮明依据 · 来源可核对</p>\n        <p class="maint-cta__stats">')
p.write_bytes(t.encode("utf-8"))
print("OK index.html")

# 2) calendar.json + manifest 全局登记
cal = {
    "schema": "wanyu-calendar/v1", "updated": "2026-09-05",
    "note": "未公布节点不填具体日期，只给预计窗口与依据；一切以官方公告为准。",
    "items": [
        {"stage": "2027 国考公告", "date": None, "status": "expected", "expect": "预计 2026 年 10 月中旬发布", "basis": "近三年国考公告均在 10 月中旬发布；以国家公务员局官方公告为准"},
        {"stage": "2027 国考报名", "date": None, "status": "expected", "expect": "公告后约一周内开启，窗口约 10 天", "basis": "近三年国考报名窗口约 10 天"},
        {"stage": "2027 国考笔试", "date": None, "status": "expected", "expect": "预计 2026 年 11 月下旬的周末", "basis": "近三年国考笔试在 11 月最后一个周日前后"},
        {"stage": "2027 国考安徽职位表 · 本站数据", "date": None, "status": "expected", "expect": "官方职位表发布后尽快更新上线", "basis": "本站「构建→校验→发布」管线就绪，首页将同步预告"},
        {"stage": "2026 安徽职位表（当前在库数据）", "date": "2026-08-28", "status": "done", "expect": "快照 2026-08-28，三年（2024-2026）可对照", "basis": "site-manifest 快照日期"},
    ],
}
cal_path = Path("网站/data/calendar.json")
cal_path.write_bytes(json.dumps(cal, ensure_ascii=False, indent=1).encode("utf-8"))
mp = Path("网站/data/site-manifest.json")
m = json.loads(mp.read_text(encoding="utf-8"))
m["calendar"] = {"bytes": cal_path.stat().st_size, "data": "data/calendar.json", "schema": "wanyu-calendar/v1", "sha256": hashlib.sha256(cal_path.read_bytes()).hexdigest()}
mp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
print("OK calendar.json + manifest")

# 3) CSS 三副本
css = """
/* T2 我的条件面板 + P3 收藏提醒 + P10 证据 chip + 铁律行 */
.maint-profile-panel{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;align-items:end;margin-top:12px;padding:12px;border:1px solid var(--line,#d5e4ed);border-radius:10px;background:var(--card,#fff)}
.maint-profile-panel__title{grid-column:1/-1;color:#5b7391;font-weight:700;font-size:11px}
[data-theme="dark"] .maint-profile-panel{border-color:rgba(126,143,169,.4);background:rgba(15,24,41,.6)}
[data-theme="dark"] .maint-profile-panel__title{color:#7e8fa9}
.maint-saved-alert{border-left:3px solid #c99643;margin-bottom:16px}
.maint-saved-alert__list{margin:8px 0 0;padding-left:18px;color:#5b7391;font-size:12px;line-height:1.7}
[data-theme="dark"] .maint-saved-alert__list{color:#7e8fa9}
.maint-evidence-chip{display:inline-block;margin-top:6px;padding:3px 9px;border-radius:999px;color:#267b78;background:rgba(38,123,120,.1);font-size:10px;font-weight:700}
[data-theme="dark"] .maint-evidence-chip{color:#43d17c;background:rgba(67,209,124,.12)}
.maint-cta__trust{margin:0 0 10px;color:#5b7391;font-size:12px;font-weight:700;letter-spacing:.04em}
[data-theme="dark"] .maint-cta__trust{color:#7e8fa9}
"""
for f in ("网站/assets/maintainable-site.css", "项目源码/tools/anhui_web/templates/maintainable-site.css", "网站-lite/assets/maintainable-site.css"):
    p = Path(f)
    p.write_bytes((p.read_text(encoding="utf-8") + css).encode("utf-8"))
print("OK CSS")
print("补丁 B 完成")
