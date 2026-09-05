# -*- coding: utf-8 -*-
"""P1/P2 大批次补丁 A：site.js 三副本（T2 接线 + P3 收藏提醒 + P5 日历视图 + P10 抽屉证据 chip）"""
from pathlib import Path

FILES = (
    "网站/assets/maintainable-site.js",
    "项目源码/tools/anhui_web/templates/maintainable-site.js",
    "网站-lite/assets/maintainable-site.js",
)
edits = [
    ("""        const views = { overview: () => renderOverview(overview, scopedJobs, derived), jobs_ranking: () => renderRanking(scopedJobs, catalog), jobs_search: () => renderSearch(scopedJobs, catalog, majorIndex) };""",
     """        let reqFields = null;
        if (state.view === 'jobs_search') {
          const activeProfile = readProfile();
          if (profileActive(activeProfile)) {
            reqFields = state.modules.get(`${state.cycle}:req_fields`) || null;
            if (!reqFields) {
              void loadModule(state.cycle, 'req_fields').then(() => { if (state.view === 'jobs_search') render(); }).catch(() => {});
            }
          }
        }
        const views = { overview: () => renderOverview(overview, scopedJobs, derived), jobs_ranking: () => renderRanking(scopedJobs, catalog), jobs_search: () => renderSearch(scopedJobs, catalog, majorIndex, reqFields) };"""),
    ("""      case 'maint-profile-gender':
      case 'maint-profile-fresh':""",
     """      case 'maint-profile-age':
      case 'maint-profile-gender':
      case 'maint-profile-fresh':"""),
    ("""      } else if (state.view === 'saved') {
        await loadModule(state.cycle, 'jobs_lite');
        markup = renderSaved();""",
     """      } else if (state.view === 'saved') {
        await loadModule(state.cycle, 'jobs_lite');
        let savedChanges = null;
        try {
          const store0 = window.WanyuUserStore;
          if ((store0?.loadPositions?.() || []).length && moduleUrl(state.cycle, 'changes')) savedChanges = await loadModule(state.cycle, 'changes');
        } catch (error) { savedChanges = null; }
        markup = renderSaved(savedChanges);"""),
    ("""  const renderSaved = () => {
    const store = window.WanyuUserStore;""",
     """  const renderSaved = (savedChanges = null) => {
    const store = window.WanyuUserStore;"""),
    ("""    return `${notice}<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('saved', '我的收藏')}<h1>把筛选和重点岗位留在手边。</h1>""",
     """    const changeAlert = (() => {
      if (!savedChanges?.changes || !positions.length) return '';
      const ids = new Set(positions.map((item) => String(item.recordId)));
      const hit = savedChanges.changes.filter((item) => item.target_record_id && ids.has(String(item.target_record_id)));
      if (!hit.length) return '';
      const substantiveStatus = { withdrawn: '停招', needs_review: '待人工复核' };
      const substantiveFields = ['recruits', 'major', 'xl', 'exam', 'code'];
      const substantive = hit.filter((item) => substantiveStatus[item.status] || (item.changed_fields || []).some((f) => substantiveFields.includes(String(f))));
      const items = hit.slice(0, 5).map((item) => {
        const row = rowFor(String(item.target_record_id));
        const name = row ? `${row.unit || ''} ${row.zw || row.display_title || ''}`.trim() : String(item.target_record_id);
        const what = substantiveStatus[item.status] || (item.changed_fields || []).map((f) => ({ recruits: '招录人数', major: '专业', xl: '学历', exam: '考试类别', code: '职位代码', unit: '单位', post_name: '职位名称' }[String(f)] || f)).join('、') || '信息修订';
        return `<li><strong>${escapeHtml(name)}</strong> — ${escapeHtml(what)}</li>`;
      }).join('');
      return `<section class="maint-panel maint-saved-alert"><header><div><p class="maint-eyebrow">我的岗位动态</p><h2>你收藏的岗位有 ${number(hit.length)} 条年度变化</h2></div><a class="maint-action" href="#changes" data-maintain-view="changes">查看变更通报 →</a></header><p>其中 <strong>${number(substantive.length)}</strong> 条为实质变化（招录人数 / 专业 / 学历 / 停招 / 待复核）。以下为最近示例，逐岗依据以变更通报原文为准：</p><ul class="maint-saved-alert__list">${items}</ul></section>`;
    })();
    return `${notice}${changeAlert}<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('saved', '我的收藏')}<h1>把筛选和重点岗位留在手边。</h1>"""),
    ("""    cycle_compare: { full: '三年趋势', short: '三年' },""",
     """    cycle_compare: { full: '三年趋势', short: '三年' },
    calendar: { full: '报考日历', short: '日历' },"""),
    ("""  const VIEW_NUMBERS = { overview: '01', cycle_compare: '02', jobs_map: '03', salary_map: '04', jobs_ranking: '05', jobs_search: '06', saved: '07', data_boundary: '08', help: '09', changelog: '10', changes: '11' };""",
     """  const VIEW_NUMBERS = { overview: '01', cycle_compare: '02', jobs_map: '03', salary_map: '04', jobs_ranking: '05', jobs_search: '06', saved: '07', data_boundary: '08', help: '09', changelog: '10', changes: '11', calendar: '12' };"""),
    ("""${['cycle_compare', 'salary_map', 'jobs_ranking', 'changes', 'data_boundary', 'help', 'changelog'].map""",
     """${['cycle_compare', 'salary_map', 'jobs_ranking', 'changes', 'calendar', 'data_boundary', 'help', 'changelog'].map"""),
    ("""      } else {
        const overview = await loadModule(state.cycle, 'overview');""",
     """      } else if (state.view === 'calendar') {
        let cal = null;
        try { cal = await loadGlobal('calendar'); } catch (error) { cal = null; }
        markup = renderCalendar(cal);
      } else {
        const overview = await loadModule(state.cycle, 'overview');"""),
    ("""  const renderSaved = (savedChanges = null) => {""",
     """  const renderCalendar = (cal) => {
    const items = Array.isArray(cal?.items) ? cal.items : [];
    const statusLabel = { expected: '预计', live: '进行中', done: '已发生' };
    const rows = items.map((item) => `<tr><th scope="row">${escapeHtml(item.stage || '')}</th><td>${item.date ? escapeHtml(item.date) : `<span class="tier-badge tb2">${escapeHtml(statusLabel[item.status] || '预计')}</span>`}</td><td>${escapeHtml(item.expect || '—')}</td><td class="major-cell">${escapeHtml(item.basis || '')}</td></tr>`).join('');
    return `<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('calendar', '报考日历')}<h1>关键时间，一眼看清。</h1><p>未公布的节点不填具体日期，只给预计窗口与依据；一切以官方公告为准。本页与职位表数据同步更新。</p></div><div class="maint-hero__stamp"><span>窗口提醒</span><strong>2027 国考</strong><small>预计 10 月中旬出公告 · 报名约 10 天</small></div></section><section class="maint-panel"><header><div><p class="maint-eyebrow">节点清单</p><h2>报名前后的关键节点</h2></div><span class="maint-audit-date">${escapeHtml(cal?.updated || '')} 更新</span></header><div class="table-scroll"><table class="maint-table"><thead><tr><th>节点</th><th>日期</th><th>窗口</th><th>依据 / 口径</th></tr></thead><tbody>${rows || '<tr><td colspan="4" class="empty">日历数据待更新</td></tr>'}</tbody></table></div><p class="maint-callout" style="margin-top:14px"><strong>数据同步承诺</strong><span>2027 官方职位表发布后，本站按「构建 → 校验 → 发布」管线尽快上线新周期数据，并在首页同步预告；发布前本站数据仍为 2026 快照，报前参考请以官方公告为准。</span></p></section><section class="maint-callout"><strong>现在能做什么</strong><span>先用 <a href="#jobs_search" data-maintain-view="jobs_search">找岗位</a> 熟悉三年职位表与竞争行情，收藏目标岗并关注 <a href="#changes" data-maintain-view="changes">变更通报</a>；新公告发布后回到同一收藏夹即可对照新表。</span></section>`;
  };
  const renderSaved = (savedChanges = null) => {"""),
    ("""<p>${escapeHtml(row.unit || '未提供单位')} · ${escapeHtml(row.code || '')} · ${escapeHtml(row.city || row.reg || '')} · ${escapeHtml(row.exam || '')}</p>""",
     """<p>${escapeHtml(row.unit || '未提供单位')} · ${escapeHtml(row.code || '')} · ${escapeHtml(row.city || row.reg || '')} · ${escapeHtml(row.exam || '')}</p><p class="maint-evidence-chip">✔ 来源可核对${source.observed_at ? ` · 材料取得 ${escapeHtml(source.observed_at)}` : ''}</p>"""),
]

for f in FILES:
    p = Path(f)
    t = p.read_text(encoding="utf-8")
    for old, new in edits:
        n = t.count(old)
        assert n == 1, f"{f}: 锚点 {n}!=1 → {old[:70]}"
        t = t.replace(old, new)
    p.write_bytes(t.encode("utf-8"))
    print("OK", f)
print("补丁 A 完成")
