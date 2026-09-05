# -*- coding: utf-8 -*-
"""批次2续作（本机 D:\\AI\\zcode\\皖域择岗）：Q2 抽屉层级+滚动锁 / Q5 浅色对比度残留。
锚点断言：每个替换必须恰好命中预期次数，否则整体失败不落盘。"""
from pathlib import Path

SITE = Path(r"D:\AI\zcode\皖域择岗\择岗\网站\assets")
MUTED = "var(--text-muted,#5b7391)"

def patch(path, pairs):
    text = path.read_text(encoding="utf-8")
    for old, new, expect in pairs:
        n = text.count(old)
        assert n == expect, f"{path.name}: 锚点命中 {n} 次(预期 {expect}): {old[:60]}"
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print(f"OK {path.name}: {len(pairs)} 处替换")

# Q2a: 抽屉层级高于底部导航(38)/更多面板(39)/调色板(50)
patch(SITE / "maintainable-site.css", [
    (".maint-detail-backdrop{position:fixed;inset:0;z-index:30;",
     ".maint-detail-backdrop{position:fixed;inset:0;z-index:60;", 1),
    # Q5: 地图图例/来源/城市卡小字 → 自适应 muted（浅 4.54+，深由 token 接管）
    ("color:#95a5af", f"color:{MUTED}", 1),
    ("color:#8295a1", f"color:{MUTED}", 1),
    ("color:#91a1ab", f"color:{MUTED}", 1),
    (".maintain-brand small{color:#8299b8}", f".maintain-brand small{{color:{MUTED}}}", 1),
    (".maintain-cycle-picker button{color:#7189aa}", f".maintain-cycle-picker button{{color:{MUTED}}}", 1),
    (".maintain-nav a{color:#7189aa}", f".maintain-nav a{{color:{MUTED}}}", 1),
    (".maintain-status{color:#8299b8}", f".maintain-status{{color:{MUTED}}}", 1),
    ("border-top:1px solid #e7eef9;padding:8px 0 0;color:#7189aa;",
     f"border-top:1px solid #e7eef9;padding:8px 0 0;color:{MUTED};", 1),
    (".maint-major-tools>span{margin-right:2px;color:#7189aa;",
     f".maint-major-tools>span{{margin-right:2px;color:{MUTED};", 1),
])

# Q5: v17-ui-upgrade.css 浅色硬编码 → 自适应 muted；琥珀编号单独压深并补深色回退
patch(SITE / "v17-ui-upgrade.css", [
    (".maintain-brand small { color: #8299b8;", f".maintain-brand small {{ color: {MUTED};", 1),
    (".maintain-cycle-picker button { color: #7189aa;", f".maintain-cycle-picker button {{ color: {MUTED};", 1),
    (".maintain-nav a {\n  color: #7189aa;", f".maintain-nav a {{\n  color: {MUTED};", 1),
    (".maintain-status { color: #8299b8; }", f".maintain-status {{ color: {MUTED}; }}", 1),
    (".maint-eyebrow__index { color: var(--ui-amber); }",
     ".maint-eyebrow__index { color: #9a620b; }\n:root[data-theme=\"dark\"] .maint-eyebrow__index { color: var(--ui-amber); }", 1),
])

# Q5: 竞争统计三色（浅色压深达标；深色原先无覆盖，一并补齐）
patch(SITE / "v17-search.css", [
    (".maint-search-stats__fierce { color: #e74c3c; }",
     ".maint-search-stats__fierce { color: #b03227; }", 1),
    (".maint-search-stats__easy { color: #27ae60; }",
     ".maint-search-stats__easy { color: #1e7145; }\n"
     "[data-theme=\"dark\"] .maint-search-stats__fierce { color: #ff9a8c; }\n"
     "[data-theme=\"dark\"] .maint-search-stats__medium { color: #e8b15d; }\n"
     "[data-theme=\"dark\"] .maint-search-stats__easy { color: #43d17c; }", 1),
    ("  color: #1e8449;", "  color: #186f3d;", 1),
])

# Q2b: body 滚动锁（打开抽屉锁定、关闭恢复；幂等可重复进入）
js = SITE / "maintainable-site.js"
patch(js, [
    ("  const openDetail = async (recordId, options = {}) => {",
     "  const lockBodyScroll = (lock) => {\n"
     "    if (lock) {\n"
     "      if (!document.body.dataset.scrollLock) {\n"
     "        document.body.dataset.scrollLock = document.body.style.overflow || '';\n"
     "        document.body.style.overflow = 'hidden';\n"
     "      }\n"
     "    } else if (document.body.dataset.scrollLock !== undefined) {\n"
     "      document.body.style.overflow = document.body.dataset.scrollLock;\n"
     "      delete document.body.dataset.scrollLock;\n"
     "    }\n"
     "  };\n"
     "  const openDetail = async (recordId, options = {}) => {", 1),
    ("    state.detail = { recordId };\n    if (!options.fromHash) {",
     "    state.detail = { recordId };\n    lockBodyScroll(true);\n    if (!options.fromHash) {", 1),
    ("    document.querySelector('[data-maint-detail-drawer]')?.remove();\n    state.detail = null;",
     "    document.querySelector('[data-maint-detail-drawer]')?.remove();\n    state.detail = null;\n    lockBodyScroll(false);", 1),
])
print("全部补丁落盘")
