# -*- coding: utf-8 -*-
"""迭代批次：② 详情抽屉跨年走势可视化（迷你折线+扩缩招徽章）"""
from pathlib import Path

FILES = (
    "网站/assets/maintainable-site.js",
    "项目源码/tools/anhui_web/templates/maintainable-site.js",
    "网站-lite/assets/maintainable-site.js",
)
old = """        historyBlock = `<section class="maint-detail-section"><h3>跨年走势 · 同单位同职位族</h3><div class="table-scroll"><table class="maint-table maint-table--history"><thead><tr><th>年份</th><th>岗位</th><th>招录</th><th>报名</th><th>竞争比</th><th>入围线</th></tr></thead><tbody>${rowsHtml}</tbody></table></div><p class="maint-detail-footnote">按“城市+单位+职位名称”聚合的同职位族跨年数据，仅显示有数据的年份；报名与入围线在官方未公布或无法唯一匹配时保持空值，不以 0 冒充。</p></section>`;"""
new = """        const vizYears = order.filter((y) => historyEntry.cycles[y]?.lo != null);
        const vizPosts = order.map((y) => ({ year: y, posts: historyEntry.cycles[y]?.posts ?? 0 }));
        let spark = '';
        let trendBadge = '';
        if (vizYears.length >= 2) {
          const los = vizYears.map((y) => historyEntry.cycles[y].lo);
          const minV = Math.min(...los), maxV = Math.max(...los);
          const span = maxV - minV || 1;
          const W = 500, H = 88, PAD = 14;
          const pts = los.map((v, i) => [PAD + (i * (W - PAD * 2)) / (los.length - 1), H - PAD - ((v - minV) / span) * (H - PAD * 2)]);
          const poly = pts.map((pt) => `${pt[0].toFixed(1)},${pt[1].toFixed(1)}`).join(' ');
          spark = `<svg class="maint-trend-spark" viewBox="0 0 ${W} ${H}" role="img" aria-label="同职位族入围线走势：${vizYears.join('、')}年分别为 ${los.join('、')} 分"><polyline points="${poly}" fill="none" stroke="var(--accent-primary,#3a83f7)" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>${pts.map((pt, i) => `<circle cx="${pt[0].toFixed(1)}" cy="${pt[1].toFixed(1)}" r="4.5" fill="var(--accent-primary,#3a83f7)"/><text x="${pt[0].toFixed(1)}" y="${pt[1].toFixed(1) - 10}" text-anchor="middle" class="maint-trend-spark__val">${los[i]}</text>`).join('')}<text x="${PAD}" y="${H - 2}" text-anchor="start" class="maint-trend-spark__year">${vizYears[0]}</text><text x="${W - PAD}" y="${H - 2}" text-anchor="end" class="maint-trend-spark__year">${vizYears[vizYears.length - 1]}</text></svg>`;
        }
        if (vizPosts.length >= 2) {
          const p0 = vizPosts[0].posts, p1 = vizPosts[vizPosts.length - 1].posts;
          if (p1 > p0) trendBadge = `<span class="tier-badge tb1" title="同职位族招录人数 ${p0}→${p1}">扩招 ↗（${p0}→${p1}）</span>`;
          else if (p1 < p0) trendBadge = `<span class="tier-badge tb2" title="同职位族招录人数 ${p0}→${p1}">缩招 ↘（${p0}→${p1}）</span>`;
          else trendBadge = `<span class="tier-badge tb3" title="同职位族招录人数持平（${p0}）">招录持平（${p0}）</span>`;
        }
        historyBlock = `<section class="maint-detail-section"><h3>跨年走势 · 同单位同职位族 ${trendBadge}</h3>${spark}<div class="table-scroll"><table class="maint-table maint-table--history"><thead><tr><th scope="col">年份</th><th scope="col">岗位</th><th scope="col">招录</th><th scope="col">报名</th><th scope="col">竞争比</th><th scope="col">入围线</th></tr></thead><tbody>${rowsHtml}</tbody></table></div><p class="maint-detail-footnote">按“城市+单位+职位名称”聚合的同职位族跨年数据，仅显示有数据的年份；报名与入围线在官方未公布或无法唯一匹配时保持空值，不以 0 冒充。</p></section>`;"""
for f in FILES:
    p = Path(f)
    t = p.read_text(encoding="utf-8")
    assert t.count(old) == 1, f"{f}: {t.count(old)}"
    p.write_bytes(t.replace(old, new).encode("utf-8"))
    print("OK", f)

css = """
/* ② 跨年走势迷你折线 */
.maint-trend-spark{width:100%;max-width:520px;height:auto;margin:0 0 12px;display:block}
.maint-trend-spark__val{font:700 12px var(--mono,Consolas);fill:#5b7391}
.maint-trend-spark__year{font:700 11px var(--mono,Consolas);fill:#5b7391}
[data-theme="dark"] .maint-trend-spark__val,[data-theme="dark"] .maint-trend-spark__year{fill:#7e8fa9}
"""
for f in ("网站/assets/maintainable-site.css", "项目源码/tools/anhui_web/templates/maintainable-site.css", "网站-lite/assets/maintainable-site.css"):
    p = Path(f)
    p.write_bytes((p.read_text(encoding="utf-8") + css).encode("utf-8"))
print("CSS 完成")
