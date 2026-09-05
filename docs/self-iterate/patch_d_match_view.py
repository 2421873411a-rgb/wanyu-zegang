# -*- coding: utf-8 -*-
"""迭代批次：① #match「为我匹配」视图（T1 专业三级 × T2 资格画像 → 个人可报榜）"""
from pathlib import Path

FILES = (
    "网站/assets/maintainable-site.js",
    "项目源码/tools/anhui_web/templates/maintainable-site.js",
    "网站-lite/assets/maintainable-site.js",
)
edits = [
    # 1) 注册：VIEW_META / VIEW_NUMBERS / validViews / 移动端更多
    ("""    calendar: { full: '报考日历', short: '日历' },""",
     """    calendar: { full: '报考日历', short: '日历' },
    match: { full: '为我匹配', short: '匹配' },"""),
    ("""changelog: '10', changes: '11', calendar: '12' };""",
     """changelog: '10', changes: '11', calendar: '12', match: '13' };"""),
    ("""'changelog', 'calendar']);""",
     """'changelog', 'calendar', 'match']);"""),
    ("""${['cycle_compare', 'salary_map', 'jobs_ranking', 'changes', 'calendar', 'data_boundary', 'help', 'changelog'].map""",
     """${['match', 'cycle_compare', 'salary_map', 'jobs_ranking', 'changes', 'calendar', 'data_boundary', 'help', 'changelog'].map"""),
    # 2) 渲染分支（放在 calendar 分支后）
    ("""      } else if (state.view === 'calendar') {""",
     """      } else if (state.view === 'match') {
        await loadModule(state.cycle, 'jobs_lite');
        const matchCatalog = await loadModule(state.cycle, 'catalog');
        let matchIndex = null;
        try { matchIndex = await loadModule(state.cycle, 'major_index'); } catch (error) { matchIndex = null; }
        let matchReq = null;
        const mp = readProfile();
        if (profileActive(mp)) {
          matchReq = state.modules.get(`${state.cycle}:req_fields`) || null;
          if (!matchReq) void loadModule(state.cycle, 'req_fields').then(() => { if (state.view === 'match') render(); }).catch(() => {});
        }
        markup = renderMatch(scopeExamPayload(state.modules.get(`${state.cycle}:jobs_lite`)), matchCatalog, matchIndex, matchReq);
      } else if (state.view === 'calendar') {"""),
    # 3) renderMatch 函数（挂在 renderCalendar 前）
    ("""  const renderCalendar = (cal) => {""",
     """  const renderMatch = (payload, catalog, majorIndex, reqFields) => {
    if (!state.matchMajor) state.matchMajor = normalize(state.searchMajor || '');
    const all = rowsFor(payload);
    const majorQuery = normalize(state.matchMajor);
    const profile = readProfile();
    const profileOn = profileActive(profile) && Boolean(reqFields);
    const p = majorIndex?.postings || null;
    const explicitSet = new Set(p && majorQuery ? p.explicit[majorQuery] || [] : []);
    const classSet = new Set();
    let clsName = '';
    if (p && majorQuery) {
      (majorIndex.classes || []).forEach((c) => {
        if ((c.members || []).includes(majorQuery) && Array.isArray(p.by_class[c.key])) {
          if (!clsName) clsName = c.key;
          p.by_class[c.key].forEach((id) => classSet.add(id));
        }
      });
      if (Array.isArray(p.by_class[majorQuery])) {
        if (!clsName) clsName = majorQuery;
        p.by_class[majorQuery].forEach((id) => classSet.add(id));
      }
    }
    const unlimitSet = new Set(p ? p.unlimited || [] : []);
    const tierOf = (row) => {
      const id = String(row.job_id || row.row_id || row.code || '');
      if (explicitSet.has(id)) return 1;
      if (classSet.has(id)) return 2;
      if (unlimitSet.has(id)) return 3;
      return 9;
    };
    const profileFail = (row) => {
      if (!profileOn) return false;
      const rf = reqFields[String(row.job_id || '')];
      if (!rf || rf.confidence !== 'high') return false;
      if (rf.fresh_only && profile.fresh === 'no') return true;
      if (rf.party_only && profile.party === 'no') return true;
      if (rf.cert_legal && profile.legal === 'no') return true;
      if (rf.gender === 'male' && profile.gender === 'female') return true;
      if (rf.gender === 'female' && profile.gender === 'male') return true;
      if (rf.age_max != null && profile.age && Number(profile.age) > Number(rf.age_max)) return true;
      return false;
    };
    const matched = majorQuery && p
      ? all.filter((row) => tierOf(row) !== 9 && !profileFail(row))
      : [];
    const n1 = matched.filter((row) => tierOf(row) === 1).length;
    const n2 = matched.filter((row) => tierOf(row) === 2).length;
    const n3 = matched.filter((row) => tierOf(row) === 3).length;
    const ratioOf = (row) => {
      const num = Number(row.num ?? row.recruits ?? 0);
      const examinees = Number(row.competition_observations?.examinees?.value ?? row.bm ?? 0);
      return num > 0 && examinees > 0 ? examinees / num : Number.POSITIVE_INFINITY;
    };
    const top = [...matched].sort((a, b) => (tierOf(a) - tierOf(b)) || (ratioOf(a) - ratioOf(b))).slice(0, 30);
    const majorOptions = curateMajorOptions(catalog, all);
    const input = `<div class="maint-match-input"><input id="maint-match-major" list="maint-match-major-options" value="${escapeHtml(state.matchMajor)}" placeholder="输入你的专业，如：知识产权、软件工程、会计学"><datalist id="maint-match-major-options">${majorOptions.slice(0, 500).map(([value]) => `<option value="${escapeHtml(value)}"></option>`).join('')}</datalist><button type="button" class="maint-action" data-maint-match-go>生成我的可报榜</button>${profileOn ? '<span class="tier-badge tb1">👤 条件已启用</span>' : `<a class="maint-filter-hint" href="#jobs_search" data-maintain-view="jobs_search">先去「我的条件」填应届/性别/党员/法考，结果更准 →</a>`}</div>`;
    if (!majorQuery) {
      return `<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('match', '为我匹配')}<h1>一步得到你的可报榜。</h1><p>输入专业 + 可选的个人条件，本页把「明确含你的专业」「专业类可报（推导）」「不限专业」三类岗位一次性排好，每条亮明依据。</p></div></section><section class="maint-panel">${input}<p class="maint-filter-hint">数据：${escapeHtml(String(state.cycle))} 周期 · 匹配口径与「找岗位」一致，依据均可展开原文核对。</p></section>`;
    }
    const tiersBar = `<div class="maint-search-stats"><span class="maint-search-stats__tier t1">✔ 明确可报 ${number(n1)}</span><span class="maint-search-stats__tier t2">🔁 类内可报·推导 ${number(n2)}</span><span class="maint-search-stats__tier t3">➖ 不限专业 ${number(n3)}</span>${profileOn ? `<span class="maint-search-stats__tier t1">👤 已按我的条件过滤</span>` : ''}</div>`;
    const tableRows = top.map((row) => {
      const t = tierOf(row);
      const num = Number(row.num ?? row.recruits ?? 0);
      const examinees = Number(row.competition_observations?.examinees?.value ?? row.bm ?? 0);
      const ratio = num > 0 && examinees > 0 ? `${(examinees / num).toFixed(1)}:1` : '暂无数据';
      const tierBadge = t === 1 ? '<span class="tier-badge tb1">✔ 明确含</span>' : (t === 2 ? `<span class="tier-badge tb2" title="依据：该岗要求『${escapeHtml(clsName)}』，「${escapeHtml(majorQuery)}」属该专业类（推导）">类内可报·推导</span>` : '<span class="tier-badge tb3">不限专业</span>');
      return `<tr data-maint-search-row data-record-id="${escapeHtml(row.job_id || row.code)}"><td>${escapeHtml(row.city)}</td><td>${escapeHtml(row.unit)}</td><td>${escapeHtml(row.zw || row.display_title || '—')}</td><td class="major-cell" title="${escapeHtml(row.zy)}">${tierBadge}</td><td>${escapeHtml(row.xl || '—')}</td><td>${escapeHtml(num || '—')}</td><td>${escapeHtml(ratio)}</td><td><button type="button" class="maint-row-action" data-maint-position-detail data-record-id="${escapeHtml(row.job_id || row.code)}">查看详情</button></td></tr>`;
    }).join('');
    const result = majorQuery && !p
      ? `<p class="empty">匹配索引尚未加载完成，请稍候自动刷新；或回到<a href="#jobs_search" data-maintain-view="jobs_search">找岗位</a>先行检索。</p>`
      : `${tiersBar}<div class="table-scroll"><table class="maint-table"><thead><tr><th scope="col">城市</th><th scope="col">单位</th><th scope="col">职位</th><th scope="col">匹配依据</th><th scope="col">学历</th><th scope="col">招录</th><th scope="col">竞争</th><th scope="col">操作</th></tr></thead><tbody>${tableRows || '<tr><td colspan="8" class="empty">没有匹配的岗位：可清空部分条件，或确认专业名在目录内（回找岗位页可按原文检索）</td></tr>'}</tbody></table></div><p class="maint-filter-hint">显示竞争最友好的前 30 岗（命中档优先，再按竞争比升序）；完整清单用「找岗位」按同条件导出。</p>`;
    return `<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('match', '为我匹配')}<h1>${escapeHtml(majorQuery)} · 你的可报榜。</h1><p>三类命中一次排开，每条亮明匹配依据；个人条件只做硬性一票否决，存疑岗位不否决。</p></div></section><section class="maint-panel">${input}${result}</section>`;
  };
  const renderCalendar = (cal) => {"""),
    # 4) 交互：match 输入与按钮
    ("""      case 'maint-profile-age':""",
     """      case 'maint-match-major': state.matchMajor = normalize(value); return true;
      case 'maint-profile-age':"""),
    ("""    if (event.target.closest('[data-maint-profile-toggle]')) {""",
     """    if (event.target.closest('[data-maint-match-go]')) {
      const input = document.getElementById('maint-match-major');
      state.matchMajor = normalize(input?.value || '');
      render();
      return;
    }
    if (event.target.closest('[data-maint-profile-toggle]')) {"""),
    # 5) 检索工具栏入口按钮
    ("""<button type="button" data-maint-profile-toggle class="${profileOn ? 'is-active' : ''}" aria-expanded="${state.profileOpen ? 'true' : 'false'}" title="填写学历/应届/性别/党员/法考/年龄，全站自动标注可报">👤 我的条件</button>""",
     """<button type="button" data-maint-profile-toggle class="${profileOn ? 'is-active' : ''}" aria-expanded="${state.profileOpen ? 'true' : 'false'}" title="填写学历/应届/性别/党员/法考/年龄，全站自动标注可报">👤 我的条件</button><a class="maint-row-action" href="#match" data-maintain-view="match" title="专业+条件一次生成可报榜">⚡ 为我匹配</a>"""),
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

css = """
/* ① 为我匹配 */
.maint-match-input{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:14px}
.maint-match-input input{flex:1 1 260px;min-width:220px;height:42px;padding:0 12px;border:1px solid var(--ui-line,#cbdde8);border-radius:9px;background:var(--bg-surface-soft,#fbfdff);color:inherit}
.maint-match-input .maint-action{white-space:nowrap}
"""
for f in ("网站/assets/maintainable-site.css", "项目源码/tools/anhui_web/templates/maintainable-site.css", "网站-lite/assets/maintainable-site.css"):
    p = Path(f)
    p.write_bytes((p.read_text(encoding="utf-8") + css).encode("utf-8"))
print("CSS 完成")
