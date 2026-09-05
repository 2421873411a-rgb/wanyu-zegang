(() => {
  /* 皖域择岗 · 岗位检索 v9：适配度评分 / 竞争修正 / 平替 / 收藏分组·笔记·风险体检 / 6 岗对比 */
  const data = window.productData || {};
  if (data.cycleRuntime?.cycle && document.querySelector('#jobs-search-table')) {
    /* v12 fast path: index every source row, render only the current result page. */
    const recordsV12 = Array.isArray(data.records) ? data.records : [];
    const tableV12 = document.querySelector('#jobs-search-table');
    const bodyV12 = tableV12?.querySelector('tbody');
    const escV12 = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
    const showV12 = (value) => value === null || value === undefined || value === '' ? '—' : String(value);
    const fieldV12 = (record, ...keys) => keys.map((key) => record.fields?.[key]).find((value) => value !== undefined && value !== '') ?? null;
    const codeOfV12 = (record) => String(record.code ?? '');
    const competitionTypeOfV12 = (record) => String(record.competition_metric_type || '');
    const ratioOfV12 = (record) => {
      if (!['examinees', 'registrations', 'interview_shortlisted'].includes(competitionTypeOfV12(record))) return -1;
      const base = Number(record.competition_base || 0);
      const recruits = Number(record.recruits || 0);
      return base > 0 && recruits > 0 ? base / recruits : -1;
    };
    const lineOfV12 = (record) => {
      const value = fieldV12(record, '最低入围/线', '最低面试线');
      const number = Number.parseFloat(String(value ?? '').replace(/[^0-9.]/g, ''));
      return Number.isFinite(number) ? number : Number.POSITIVE_INFINITY;
    };
    const indexV12 = new Map(recordsV12.map((record) => [String(record.record_id), [
      codeOfV12(record), record.city, record.exam, record.unit_position,
      fieldV12(record, '专业要求'), fieldV12(record, '其他条件'), fieldV12(record, '职位简介'),
    ].filter(Boolean).join(' ').toLowerCase()]));
    const rowHtmlV12 = (record) => {
      const fields = record.fields || {};
      const city = showV12(record.city);
      const exam = showV12(record.exam);
      const code = showV12(record.code);
      const base = Number(record.competition_base || 0);
      const ratio = ratioOfV12(record);
      const ratioText = ratio > 0 ? '1:' + ratio.toFixed(1) : '—';
      const id = String(record.record_id);
      return '<tr data-search="' + escV12(indexV12.get(id) || '') + '" data-city="' + escV12(city) + '" data-exam="' + escV12(exam) + '" data-job-id="' + escV12(id) + '" data-job-code="' + escV12(code) + '" data-tags="' + escV12((record.eligibility?.tags || record.tags || []).join(' ')) + '">' 
        + '<td>' + escV12(city) + '市</td><td>' + escV12(exam) + '</td><td>' + escV12(code) + '</td>'
        + '<th scope="row">' + escV12(showV12(record.unit_position)) + '</th>'
        + '<td>' + escV12(showV12(record.recruits)) + '<span class="row-ratio" data-base="' + escV12(base || '') + '" data-competition-type="' + escV12(competitionTypeOfV12(record)) + '" title="竞争比仅在同一分母类型内展示；当前：' + escV12(record.competition_source || '未发布') + '">' + escV12(ratioText) + '</span></td>'
        + '<td>' + escV12(showV12(fields['报名*'])) + '</td><td>' + escV12(showV12(fields['审查合格*'])) + '</td>'
        + '<td>' + escV12(showV12(fields['有效笔试/达线/规模参考'] ?? fields['有效笔试/达线'])) + '</td>'
        + '<td>' + escV12(showV12(fields['最低入围/线'] ?? fields['最低面试线'])) + '</td><td>' + escV12(showV12(fields['最高笔试'])) + '</td>'
        + '<td><div class="search-actions"><button class="detail-open" type="button" data-job-detail="' + escV12(id) + '" aria-label="查看' + escV12(city) + ' ' + escV12(code) + '详情">详情</button>'
        + '<button class="compare-add" type="button" data-job-compare="' + escV12(id) + '" aria-label="加入' + escV12(city) + ' ' + escV12(code) + '岗位对比">+ 对比</button>'
        + '<button class="save-add" type="button" data-job-save="' + escV12(id) + '" aria-label="收藏' + escV12(city) + ' ' + escV12(code) + '">☆ 收藏</button></div></td></tr>';
    };
    const keysV12 = { compare: 'compare', saved: 'saved' };
    const userStoreV12 = window.WanyuUserStore;
    const readIdsV12 = (key) => {
      const ids = key === keysV12.saved ? userStoreV12?.activeLocalSaved?.() : userStoreV12?.activeLocalCompare?.();
      return new Set((ids || []).map(String).filter((id) => recordsV12.some((record) => String(record.record_id) === id)));
    };
    const writeIdsV12 = (key, ids) => {
      const success = key === keysV12.saved ? userStoreV12?.saveActiveSaved?.(ids) : userStoreV12?.saveActiveCompare?.(ids);
      if (success === false) announceV12('本机存储写入失败，当前页面操作仍保留');
    };
    const compareV12 = readIdsV12(keysV12.compare);
    const savedV12 = readIdsV12(keysV12.saved);
    const recordByIdV12 = new Map(recordsV12.map((record) => [String(record.record_id), record]));
    const searchV12 = document.querySelector('#job-search');
    const cityV12 = document.querySelector('#city-filter');
    const examV12 = document.querySelector('#exam-filter-search');
    const natureV12 = document.querySelector('#nature-filter');
    const sortV12 = document.querySelector('#search-sort');
    const countV12 = document.querySelector('#search-count');
    const statusV12 = document.querySelector('#search-status');
    const emptyV12 = document.querySelector('#search-empty');
    const searchViewV12 = document.querySelector('.unified-view[data-view="jobs_search"]');
    const leadV12 = searchViewV12?.querySelector('.hero-lead');
    if (leadV12) leadV12.textContent = '全库 ' + recordsV12.length.toLocaleString('en-US') + ' 条岗位可检索；资格标签与数据缺口保留在源行，不从源表删除。';
    searchViewV12?.querySelector('a[href="#jobs_score_sim"]')?.setAttribute('href', '#score_sim');
    const pageSizeV12 = 120;
    const stateV12 = { page: 1 };
    let filteredV12 = recordsV12.slice();
    let pagerV12 = document.querySelector('#v12-search-pager');
    if (!pagerV12 && tableV12) { pagerV12 = document.createElement('div'); pagerV12.id = 'v12-search-pager'; pagerV12.className = 'v12-search-pager'; tableV12.insertAdjacentElement('afterend', pagerV12); }
    const announceV12 = (message) => { if (statusV12) statusV12.textContent = message; };
    const persistIdsV12 = (key, ids) => { writeIdsV12(key, ids); document.dispatchEvent(new CustomEvent(key === keysV12.saved ? 'wanyu:saved-changed' : 'wanyu:compare-changed')); };
    const searchMatchV12 = (record, query) => !query || (indexV12.get(String(record.record_id)) || '').includes(query);
    const natureMatchV12 = (record, value) => !value || (record.natures || []).some((item) => String(item.key || item.label) === value);
    const sortedV12 = (list) => {
      const mode = sortV12?.value || 'default';
      const rows = list.slice();
      if (mode === 'recruits') rows.sort((a, b) => Number(b.recruits || 0) - Number(a.recruits || 0));
      else if (mode === 'ratio' || mode === 'match') rows.sort((a, b) => ratioOfV12(b) - ratioOfV12(a) || Number(b.recruits || 0) - Number(a.recruits || 0));
      else if (mode === 'line') rows.sort((a, b) => lineOfV12(a) - lineOfV12(b));
      return rows;
    };
    const renderCompareV12 = () => {
      const list = document.querySelector('#jobs-compare-list');
      const empty = document.querySelector('#jobs-compare-empty');
      const count = document.querySelector('#jobs-compare-count');
      if (count) count.textContent = compareV12.size + ' / 6';
      const searchCount = document.querySelector('#search-compare-count');
      if (searchCount) searchCount.textContent = compareV12.size + ' / 6';
      if (empty) empty.hidden = compareV12.size > 0;
      document.querySelectorAll('#copy-job-compare, #export-job-compare, #clear-job-compare').forEach((button) => { button.disabled = compareV12.size === 0; });
      if (!list) return;
      const value = (record, ...keys) => showV12(fieldV12(record, ...keys));
      list.innerHTML = [...compareV12].map((id, index) => {
        const record = recordByIdV12.get(id); if (!record) return '';
        return '<article class="compare-position-card" data-compare-card="' + escV12(id) + '"><header><div class="compare-position-card__title"><span class="compare-index">' + String(index + 1).padStart(2, '0') + '</span><div><p>' + escV12(record.city) + '市 · ' + escV12(record.exam) + '</p><h3>' + escV12(record.code) + '</h3><strong>' + escV12(record.unit_position) + '</strong></div></div><button class="compare-remove" type="button" data-remove-job="' + escV12(id) + '">移除</button></header><dl>'
          + '<div><dt>招录人数</dt><dd>' + escV12(showV12(record.recruits)) + ' 人</dd></div><div><dt>报名</dt><dd>' + escV12(value(record, '报名*')) + '</dd></div><div><dt>有效笔试/达线</dt><dd>' + escV12(value(record, '有效笔试/达线/规模参考', '有效笔试/达线')) + '</dd></div><div><dt>最低入围/线</dt><dd>' + escV12(value(record, '最低入围/线', '最低面试线')) + '</dd></div></dl></article>';
      }).join('');
    };
    const renderSavedV12 = () => {
      const list = document.querySelector('#saved-jobs-list');
      const empty = document.querySelector('#saved-jobs-empty');
      const count = document.querySelector('#saved-jobs-count');
      if (count) count.textContent = String(savedV12.size);
      if (empty) empty.hidden = savedV12.size > 0;
      if (!list) return;
      list.innerHTML = [...savedV12].map((id, index) => {
        const record = recordByIdV12.get(id); if (!record) return '';
        return '<article class="saved-position-card" data-saved-card="' + escV12(id) + '"><header><div class="saved-position-card__title"><span class="saved-index">' + String(index + 1).padStart(2, '0') + '</span><div><p>' + escV12(record.city) + '市 · ' + escV12(record.exam) + '</p><h3>' + escV12(record.code) + '</h3><strong>' + escV12(record.unit_position) + '</strong></div></div><button class="saved-remove" type="button" data-remove-saved="' + escV12(id) + '">移除</button></header><dl><div><dt>招录人数</dt><dd>' + escV12(showV12(record.recruits)) + ' 人</dd></div><div><dt>报名</dt><dd>' + escV12(showV12(fieldV12(record, '报名*'))) + '</dd></div><div><dt>最低入围/线</dt><dd>' + escV12(showV12(fieldV12(record, '最低入围/线', '最低面试线'))) + '</dd></div></dl><a href="#jobs_search" data-job-detail="' + escV12(id) + '">查看详情 →</a></article>';
      }).join('');
    };
    const syncButtonsV12 = () => {
      bodyV12?.querySelectorAll('[data-job-compare]').forEach((button) => { const on = compareV12.has(String(button.dataset.jobCompare)); button.classList.toggle('is-added', on); button.setAttribute('aria-pressed', String(on)); button.textContent = on ? '已加入' : '+ 对比'; });
      bodyV12?.querySelectorAll('[data-job-save]').forEach((button) => { const on = savedV12.has(String(button.dataset.jobSave)); button.classList.toggle('is-saved', on); button.setAttribute('aria-pressed', String(on)); button.textContent = on ? '★ 已收藏' : '☆ 收藏'; });
    };
    const renderPagerV12 = (pages) => {
      if (!pagerV12) return;
      pagerV12.innerHTML = pages <= 1 ? '' : '<span>第 ' + stateV12.page + ' / ' + pages + ' 页</span>' + Array.from({ length: pages }, (_, index) => index + 1).filter((page) => pages <= 12 || page <= 2 || page > pages - 2 || Math.abs(page - stateV12.page) <= 1).map((page) => '<button type="button" data-v12-page="' + page + '" class="' + (page === stateV12.page ? 'is-on' : '') + '">' + page + '</button>').join('');
    };
    const renderV12 = () => {
      const query = String(searchV12?.value || '').trim().toLowerCase();
      const bulk = new Set(window.__wanyuBulkCodes || []);
      const activeTags = new Set(window.__wanyuActiveTags || []);
      filteredV12 = sortedV12(recordsV12.filter((record) => searchMatchV12(record, query)
        && (!cityV12?.value || String(record.city) === cityV12.value)
        && (!examV12?.value || String(record.exam) === examV12.value)
        && natureMatchV12(record, natureV12?.value || '')
        && (!bulk.size || bulk.has(codeOfV12(record)))
        && (!activeTags.size || [...activeTags].every((tag) => (record.eligibility?.tags || record.tags || []).includes(tag)))));
      const pages = Math.max(1, Math.ceil(filteredV12.length / pageSizeV12));
      stateV12.page = Math.min(stateV12.page, pages);
      const start = (stateV12.page - 1) * pageSizeV12;
      if (bodyV12) bodyV12.innerHTML = filteredV12.slice(start, start + pageSizeV12).map(rowHtmlV12).join('');
      if (countV12) countV12.textContent = filteredV12.length.toLocaleString('en-US');
      if (emptyV12) emptyV12.hidden = filteredV12.length > 0;
      announceV12('全库 ' + recordsV12.length.toLocaleString('en-US') + ' 条 · 当前筛选 ' + filteredV12.length.toLocaleString('en-US') + ' 条；资格标签保留在源行，不删除原始岗位。');
      renderPagerV12(pages);
      syncButtonsV12();
      renderCompareV12();
      renderSavedV12();
    };
    pagerV12?.addEventListener('click', (event) => { const button = event.target.closest('[data-v12-page]'); if (!button) return; stateV12.page = Number(button.dataset.v12Page) || 1; renderV12(); tableV12.scrollIntoView({ block: 'start' }); });
    bodyV12?.addEventListener('click', (event) => {
      const compare = event.target.closest('[data-job-compare]');
      if (compare) { const id = String(compare.dataset.jobCompare); if (compareV12.has(id)) compareV12.delete(id); else if (compareV12.size < 6) compareV12.add(id); else { announceV12('岗位对比最多保留 6 条'); return; } persistIdsV12(keysV12.compare, compareV12); renderV12(); return; }
      const save = event.target.closest('[data-job-save]');
      if (save) { const id = String(save.dataset.jobSave); if (savedV12.has(id)) savedV12.delete(id); else savedV12.add(id); persistIdsV12(keysV12.saved, savedV12); renderV12(); }
    });
    document.addEventListener('click', (event) => {
      const removeCompare = event.target.closest('[data-remove-job]');
      if (removeCompare) { compareV12.delete(String(removeCompare.dataset.removeJob)); persistIdsV12(keysV12.compare, compareV12); renderV12(); }
      const removeSaved = event.target.closest('[data-remove-saved]');
      if (removeSaved) { savedV12.delete(String(removeSaved.dataset.removeSaved)); persistIdsV12(keysV12.saved, savedV12); renderV12(); }
    });
    document.querySelector('#open-job-compare')?.addEventListener('click', () => { location.hash = '#jobs_compare'; });
    document.querySelector('#clear-job-compare')?.addEventListener('click', () => { compareV12.clear(); persistIdsV12(keysV12.compare, compareV12); renderV12(); });
    document.querySelector('#clear-saved-jobs')?.addEventListener('click', () => { savedV12.clear(); persistIdsV12(keysV12.saved, savedV12); renderV12(); });
    document.querySelector('#reset-search')?.addEventListener('click', () => { if (searchV12) searchV12.value = ''; if (cityV12) cityV12.value = ''; if (examV12) examV12.value = ''; if (natureV12) natureV12.value = ''; if (sortV12) sortV12.value = 'default'; window.__wanyuActiveTags = []; window.__wanyuBulkCodes = []; document.querySelectorAll('[data-tag-filter]').forEach((chip) => chip.classList.remove('is-active')); document.querySelector('#clear-bulk-codes')?.classList.add('is-hidden'); stateV12.page = 1; renderV12(); searchV12?.focus(); });
    [searchV12, cityV12, examV12, natureV12, sortV12].forEach((control) => control?.addEventListener(control === searchV12 ? 'input' : 'change', () => { stateV12.page = 1; renderV12(); }));
    document.querySelector('#match-settings')?.addEventListener('click', () => window.wanyuOverlay?.('适配度排序说明', '<p class="wanyu-dialog__lead">适配度排序按招录规模与竞争分母做本地归一化，仅用于岗位浏览顺序，不是录用预测。</p><p class="wanyu-dialog__note">竞争分母优先使用有效笔试/达线人数，缺失时回退报名人数；每条源行均可打开详情复核。</p>'));
    document.addEventListener('keydown', (event) => {
      const editable = event.target instanceof Element && (event.target.matches('input, textarea, select') || event.target.isContentEditable);
      if (editable || event.ctrlKey || event.altKey || event.metaKey || document.body.dataset.activeView !== 'jobs_search') return;
      const visible = [...(bodyV12?.querySelectorAll('tr') || [])];
      if (!visible.length) return;
      if (event.key === 'j' || event.key === 'k') { event.preventDefault(); const delta = event.key === 'j' ? 1 : -1; const current = visible.findIndex((row) => row.classList.contains('is-kbd')); const next = (current + delta + visible.length) % visible.length; visible.forEach((row, index) => row.classList.toggle('is-kbd', index === next)); visible[next].scrollIntoView({ block: 'nearest' }); }
      if (event.key === 's' || event.key === 'c') { const row = visible.find((item) => item.classList.contains('is-kbd')) || visible[0]; row.querySelector(event.key === 's' ? '[data-job-save]' : '[data-job-compare]')?.click(); }
    });
    document.querySelector('#copy-job-compare')?.addEventListener('click', async () => {
      const text = [...compareV12].map((id) => recordByIdV12.get(id)).filter(Boolean).map((record) => `${record.city}市 ${record.code} ${record.unit_position} 招${record.recruits}人`).join('\n');
      if (!text) return;
      try { await navigator.clipboard.writeText(text); announceV12('岗位对比摘要已复制'); } catch { announceV12('复制失败，请使用导出 CSV'); }
    });
    document.querySelector('#export-job-compare')?.addEventListener('click', () => {
      const rows = [...compareV12].map((id) => recordByIdV12.get(id)).filter(Boolean);
      if (!rows.length) return;
      const cell = (value) => '"' + String(value ?? '').replaceAll('"', '""') + '"';
      const csv = '\ufeff' + [['城市', '代码', '单位与职位', '类别', '招录人数', '报名', '最低入围/线'], ...rows.map((record) => [record.city, record.code, record.unit_position, record.exam, record.recruits, fieldV12(record, '报名*'), fieldV12(record, '最低入围/线', '最低面试线')])].map((row) => row.map(cell).join(',')).join('\r\n');
      const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })); link.download = '岗位对比.csv'; link.click(); URL.revokeObjectURL(link.href); announceV12('岗位对比 CSV 已导出');
    });
    document.addEventListener('click', (event) => {
      const trigger = event.target.closest('[data-substitute-for]');
      if (!trigger || !recordByIdV12.has(String(trigger.dataset.substituteFor))) return;
      const target = recordByIdV12.get(String(trigger.dataset.substituteFor));
      const targetLine = lineOfV12(target);
      const targetCompetitionType = competitionTypeOfV12(target);
      const options = recordsV12.filter((record) => record.exam === target.exam && targetCompetitionType && competitionTypeOfV12(record) === targetCompetitionType && String(record.code) !== String(target.code) && ratioOfV12(record) > ratioOfV12(target) && (targetLine === Number.POSITIVE_INFINITY || Math.abs(lineOfV12(record) - targetLine) <= 3)).sort((a, b) => ratioOfV12(b) - ratioOfV12(a)).slice(0, 8);
      const html = options.length ? '<p class="wanyu-dialog__lead">同类别、入围线相近且竞争分母更缓的岗位：</p>' + options.map((record) => '<p><b>' + escV12(record.code) + '</b> · ' + escV12(record.city) + '市 · ' + escV12(record.unit_position) + ' · 1:' + ratioOfV12(record).toFixed(1) + '</p>').join('') : '<p class="wanyu-dialog__lead">当前周期未找到满足同类别和入围线口径的明显平替。</p>';
      window.wanyuOverlay?.('平替推荐 · ' + escV12(target.code), html);
    });
    document.addEventListener('wanyu:compare-changed', renderCompareV12);
    document.addEventListener('wanyu:saved-changed', renderSavedV12);
    window.__wanyuV12Search = Object.freeze({ total: recordsV12.length, getFilteredCount: () => filteredV12.length });
    renderV12();
    return;
  }
  const core = window.wanyuCore || {};
  const records = Array.isArray(data.records) ? data.records : [];
  const recordById = new Map(records.map((record) => [String(record.record_id), record]));
  const selected = new Map();
  const saved = new Map();
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
  const displayValue = (value) => value === null || value === undefined || value === '' ? '—' : String(value);
  const buildSearchRow = (record) => {
    const fields = record.fields || {};
    const tags = Array.isArray(record.eligibility?.tags) ? record.eligibility.tags : (Array.isArray(record.tags) ? record.tags : []);
    const natures = Array.isArray(record.natures) ? record.natures.map((item) => item.key || item.label).filter(Boolean) : [];
    const base = Number(record.competition_base || 0);
    const recruits = Number(record.recruits || 0);
    const ratio = base > 0 && recruits > 0 ? '1:' + (base / recruits).toFixed(1) : '—';
    const city = displayValue(record.city);
    const exam = displayValue(record.exam);
    const code = displayValue(record.code);
    const position = displayValue(record.unit_position);
    const searchText = [code, city, exam, position, fields['专业要求'], fields['其他条件'], fields['职位简介']].filter(Boolean).join(' ');
    return '<tr data-search="' + escapeHtml(searchText) + '" data-city="' + escapeHtml(city) + '" data-exam="' + escapeHtml(exam) + '" data-job-id="' + escapeHtml(record.record_id) + '" data-job-code="' + escapeHtml(code) + '" data-tags="' + escapeHtml(tags.join(' ')) + '" data-natures="' + escapeHtml(natures.join(' ')) + '" data-source-row="' + escapeHtml(record.source_row) + '">' 
      + '<td>' + escapeHtml(city) + '市</td><td>' + escapeHtml(exam) + '</td><td>' + escapeHtml(code) + '</td>'
      + '<th scope="row">' + escapeHtml(position) + '</th><td>' + escapeHtml(displayValue(record.recruits))
      + '<span class="row-ratio" data-base="' + escapeHtml(base || '') + '" title="竞争比 = 招录人数 ÷ 竞争分母；分母优先有效笔试/达线人数，其次报名人数">' + escapeHtml(ratio) + '</span></td>'
      + '<td>' + escapeHtml(displayValue(fields['报名*'])) + '</td><td>' + escapeHtml(displayValue(fields['审查合格*'])) + '</td>'
      + '<td>' + escapeHtml(displayValue(fields['有效笔试/达线/规模参考'] ?? fields['有效笔试/达线'])) + '</td>'
      + '<td>' + escapeHtml(displayValue(fields['最低入围/线'] ?? fields['最低面试线'])) + '</td><td>' + escapeHtml(displayValue(fields['最高笔试'])) + '</td>'
      + '<td><div class="search-actions"><button class="detail-open" type="button" data-job-detail="' + escapeHtml(record.record_id) + '" aria-label="查看' + escapeHtml(city) + ' ' + escapeHtml(code) + '详情">详情</button>'
      + '<button class="compare-add" type="button" data-job-compare="' + escapeHtml(record.record_id) + '" aria-label="加入' + escapeHtml(city) + ' ' + escapeHtml(code) + '岗位对比">+ 对比</button>'
      + '<button class="save-add" type="button" data-job-save="' + escapeHtml(record.record_id) + '" aria-label="收藏' + escapeHtml(city) + ' ' + escapeHtml(code) + '">☆ 收藏</button></div></td></tr>';
  };
  const searchBody = document.querySelector('#jobs-search-table tbody');
  if (searchBody && records.length) searchBody.innerHTML = records.map(buildSearchRow).join('');
  const rows = [...document.querySelectorAll('#jobs-search-table tbody tr')];
  const search = document.querySelector('#job-search');
  const city = document.querySelector('#city-filter');
  const exam = document.querySelector('#exam-filter-search');
  const sortSelect = document.querySelector('#search-sort');
  const count = document.querySelector('#search-count');
  const searchStatus = document.querySelector('#search-status');
  const compareStatus = document.querySelector('#jobs-compare-status');
  const savedStatus = document.querySelector('#saved-jobs-status');
  const empty = document.querySelector('#search-empty');
  const COMPARE_LIMIT = 6;
  const KEYS = {
    compare: 'wanyu.jobCompare.v1', saved: 'wanyu.jobSaved.v1', shortlist: 'wanyu.cityShortlist.v1',
    notes: 'wanyu.jobNotes.v1', groups: 'wanyu.jobGroups.v1', overrides: 'wanyu.registrationOverrides.v1', weights: 'wanyu.matchWeights.v1',
  };
  const store = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key) || fallback); } catch { return null; } };
  const save = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch {} };
  const csvCell = (value) => { let text = String(value ?? ''); if (/^[=+\-@]/.test(text)) text = "'" + text; return '"' + text.replaceAll('"', '""') + '"'; };
  const pick = (fields, ...keys) => keys.map((key) => fields?.[key]).find((value) => value !== undefined && value !== '') ?? '—';
  const parseNum = (value) => { const num = Number.parseFloat(String(value ?? '').replace(/[^0-9.]/g, '')); return Number.isFinite(num) ? num : null; };
  const recordFromData = (record) => ({
    id: String(record.record_id), city: record.city, code: record.code, position: record.unit_position, exam: record.exam,
    recruits: record.recruits, registration: pick(record.fields, '报名*'), audit: pick(record.fields, '审查合格*'),
    effective: pick(record.fields, '有效笔试/达线/规模参考', '有效笔试/达线'), minimum: pick(record.fields, '最低入围/线', '最低面试线'), highest: pick(record.fields, '最高笔试'),
  });
  const recordFromRow = (row) => ({ id: row.dataset.jobId, city: row.dataset.city, code: row.dataset.jobCode || row.children[2].textContent.trim(), position: row.children[3].textContent.trim(), exam: row.dataset.exam, recruits: row.children[4].textContent.trim(), registration: row.children[5].textContent.trim(), audit: row.children[6].textContent.trim(), effective: row.children[7].textContent.trim(), minimum: row.children[8].textContent.trim(), highest: row.children[9].textContent.trim() });
  const announce = (message) => { if (searchStatus) searchStatus.textContent = message; if (compareStatus) compareStatus.textContent = message; if (savedStatus) savedStatus.textContent = message; };
  const persist = () => save(KEYS.compare, [...selected.keys()]);
  const persistSaved = () => save(KEYS.saved, [...saved.keys()]);
  const restore = () => { const ids = store(KEYS.compare, '[]'); if (Array.isArray(ids)) ids.slice(0, COMPARE_LIMIT).forEach((rawId) => { const record = recordById.get(String(rawId)); if (record) selected.set(String(rawId), recordFromData(record)); }); };
  const restoreSaved = () => { const ids = store(KEYS.saved, '[]'); if (Array.isArray(ids)) ids.forEach((rawId) => { const record = recordById.get(String(rawId)); if (record) saved.set(String(rawId), recordFromData(record)); }); };

  /* —— 适配度评分（机会 / 低竞争 / 待遇 / 城市偏好 加权，本地归一化） —— */
  const metrics = data.metrics || {};
  const cityRatio = new Map((metrics.cities || []).map((item) => [String(item.city), Number(item.ratio || 0)]));
  const examRatio = new Map();
  Object.entries(metrics.competition || {}).forEach(([cityName, exams]) => {
    Object.entries(exams || {}).forEach(([examName, item]) => examRatio.set(cityName + '|' + examName, Number(item.ratio || 0)));
  });
  const salarySeries = data.salary?.series || {};
  const shortlist = new Set((() => { const list = store(KEYS.shortlist, '[]'); return Array.isArray(list) ? list.map(String) : []; })());
  const weights = Object.assign({ opportunity: 30, competition: 30, salary: 25, city: 15 }, store(KEYS.weights, '{}') || {});
  const activeRows = rows.filter((row) => row.dataset.excluded !== '1');
  const factorPool = activeRows.map((row) => {
    const record = recordById.get(row.dataset.jobId);
    const ratio = examRatio.get(record.city + '|' + record.exam) ?? cityRatio.get(record.city) ?? 0;
    const salaryValue = Number((record.exam === '事业单位' ? salarySeries['事业编']?.[record.city] : salarySeries['公务员']?.[record.city])?.['3年'] || 0);
    return { id: row.dataset.jobId, recruits: Number(record.recruits || 0), ratio, salary: salaryValue };
  });
  const extent = (key) => {
    const values = factorPool.map((item) => item[key]);
    return [Math.min(...values), Math.max(...values)];
  };
  const factorExtents = { recruits: extent('recruits'), ratio: extent('ratio'), salary: extent('salary') };
  const norm = (value, [min, max]) => (core.normalize ? core.normalize(value, min, max) : (max - min <= 1e-9 ? 0.5 : Math.min(1, Math.max(0, (value - min) / (max - min)))));
  const factorsOf = (row) => {
    const item = factorPool.find((entry) => entry.id === row.dataset.jobId);
    if (!item) return null;
    return {
      opportunity: norm(item.recruits, factorExtents.recruits),
      competition: norm(item.ratio, factorExtents.ratio),
      salary: norm(item.salary, factorExtents.salary),
      city: shortlist.has(row.dataset.city) ? 1 : 0,
    };
  };
  const scoreOf = (row) => {
    const factors = factorsOf(row);
    if (!factors) return null;
    return core.matchScore ? core.matchScore(factors, weights) : Math.round(((factors.opportunity + factors.competition + factors.salary + factors.city) / 4) * 100);
  };
  let originalOrder = [...rows];
  const injectScores = () => {
    activeRows.forEach((row) => {
      const score = scoreOf(row);
      let chip = row.querySelector('.match-score');
      if (score === null) { chip?.remove(); return; }
      if (!chip) {
        chip = document.createElement('span');
        chip.className = 'match-score';
        row.children[2].appendChild(chip);
      }
      chip.textContent = String(score);
      chip.classList.toggle('is-high', score >= 70);
      chip.classList.toggle('is-low', score < 40);
      chip.title = '适配度 ' + score + '/100 = 机会·低竞争·待遇·城市偏好加权（可在 ⚙ 适配度 里调权重）';
    });
  };
  const sortRows = () => {
    const mode = sortSelect?.value || 'default';
    const tbody = rows[0]?.parentElement;
    if (!tbody) return;
    let ordered = [...rows];
    if (mode === 'default') ordered = originalOrder;
    else if (mode === 'match') ordered = [...activeRows].sort((a, b) => (scoreOf(b) ?? -1) - (scoreOf(a) ?? -1)).concat(rows.filter((row) => row.dataset.excluded === '1'));
    else if (mode === 'recruits') ordered = [...rows].sort((a, b) => Number(b.children[4].textContent) - Number(a.children[4].textContent));
    else if (mode === 'ratio') ordered = [...rows].sort((a, b) => {
      const ratioOf = (row) => { const record = recordById.get(row.dataset.jobId); const value = examRatio.get(record.city + '|' + record.exam) ?? cityRatio.get(record.city) ?? 0; return value; };
      return ratioOf(b) - ratioOf(a);
    });
    else if (mode === 'line') ordered = [...rows].sort((a, b) => (parseNum(recordById.get(a.dataset.jobId)?.fields?.['最低入围/线'] ?? recordById.get(a.dataset.jobId)?.fields?.['最低面试线']) ?? 1e9) - (parseNum(recordById.get(b.dataset.jobId)?.fields?.['最低入围/线'] ?? recordById.get(b.dataset.jobId)?.fields?.['最低面试线']) ?? 1e9));
    ordered.forEach((row) => tbody.appendChild(row));
  };
  const openMatchSettings = () => {
    const labels = [['opportunity', '机会（招录人数）'], ['competition', '低竞争（1:N 越小越好）'], ['salary', '待遇（城市 3 年参考）'], ['city', '城市偏好（短名单城市）']];
    const body = '<p class="wanyu-dialog__lead">四项各 0–100，权重自动归一化；评分只用于排序参考，不构成录用预测。</p>'
      + labels.map(([key, label]) => '<label class="match-weight"><span>' + label + '</span><output>' + weights[key] + '</output><input type="range" min="0" max="100" step="5" value="' + weights[key] + '" data-weight-key="' + key + '"></label>').join('');
    window.wanyuOverlay('适配度权重', body, {
      footer: '<button type="button" class="primary-button" id="match-weights-done">完成</button>',
      onMount(wrap, close) {
        wrap.querySelectorAll('[data-weight-key]').forEach((input) => {
          input.addEventListener('input', () => {
            weights[input.dataset.weightKey] = Number(input.value);
            input.parentElement.querySelector('output').textContent = input.value;
            save(KEYS.weights, weights);
            injectScores();
            if ((sortSelect?.value || 'default') === 'match') sortRows();
          });
        });
        wrap.querySelector('#match-weights-done').addEventListener('click', close);
      },
    });
  };
  document.querySelector('#match-settings')?.addEventListener('click', openMatchSettings);
  sortSelect?.addEventListener('change', () => { sortRows(); filter(); });

  /* —— 竞争分母修正（报名期手动更新，本地保存）+ 竞争比热力色阶 —— */
  const overrides = store(KEYS.overrides, '{}') || {};
  // 全省 1:N 分布分位数 → heat 0(缓)…4(紧)，用于行内徽标配色
  const ratioExtent = (() => {
    const values = activeRows.map((row) => {
      const record = recordById.get(row.dataset.jobId);
      const base = Number(record?.competition_base || 0);
      const recruits = Number(record?.recruits || 0);
      return base > 0 && recruits > 0 ? base / recruits : null;
    }).filter((value) => value !== null).sort((a, b) => a - b);
    const pick = (p) => (values.length ? values[Math.min(values.length - 1, Math.floor(values.length * p))] : 0);
    return [pick(0.15), pick(0.4), pick(0.65), pick(0.88)];
  })();
  const heatOf = (value) => {
    for (let index = 0; index < ratioExtent.length; index += 1) { if (value <= ratioExtent[index]) return index; }
    return ratioExtent.length;
  };
  const applyOverride = (row) => {
    const chip = row.querySelector('.row-ratio');
    if (!chip) return;
    const record = recordById.get(row.dataset.jobId);
    const base = Number(overrides[row.dataset.jobId] || record.competition_base || 0);
    const recruits = Number(record.recruits || 0);
    if (base > 0 && recruits > 0) {
      const multiple = base / recruits;
      chip.textContent = '1:' + multiple.toFixed(1);
      chip.dataset.heat = String(heatOf(multiple));
      chip.classList.toggle('is-edited', Boolean(overrides[row.dataset.jobId]));
      chip.title = '竞争比 = 招录 ' + recruits + ' ÷ 分母 ' + base + (overrides[row.dataset.jobId] ? '（已手动修正，原值 ' + record.competition_base + '）' : '（来源：' + (record.competition_source || '源表') + '）') + '。颜色越红＝竞争越紧（按全省分布）。点击可按最新报名人数修正。';
    }
  };
  rows.forEach(applyOverride);
  document.querySelector('#jobs-search-table')?.addEventListener('click', (event) => {
    const chip = event.target.closest('.row-ratio');
    if (!chip) return;
    const row = chip.closest('tr');
    const record = recordById.get(row.dataset.jobId);
    window.wanyuOverlay('修正竞争分母', '<p class="wanyu-dialog__lead">报名期人数会变。输入该岗最新分母（优先“有效笔试/达线人数”，其次报名人数），页面即时重算 1:N。</p>'
      + '<label class="sim-control--meta"><span>最新分母（' + escapeHtml(record.competition_source || '源表') + ' 原值 ' + (record.competition_base || '—') + '）</span>'
      + '<input id="override-base" type="number" min="0" step="1" value="' + (overrides[row.dataset.jobId] || record.competition_base || '') + '"></label>'
      + '<p class="wanyu-dialog__note">修正只保存在本机浏览器，可随时清除。</p>', {
      footer: '<button type="button" class="text-button" id="override-clear">恢复原值</button><button type="button" class="primary-button" id="override-apply">应用</button>',
      onMount(wrap, close) {
        wrap.querySelector('#override-apply').addEventListener('click', () => {
          const value = Number(wrap.querySelector('#override-base').value);
          if (Number.isFinite(value) && value > 0) { overrides[row.dataset.jobId] = value; save(KEYS.overrides, overrides); applyOverride(row); announce('已修正 ' + record.code + ' 竞争分母为 ' + value); }
          close();
        });
        wrap.querySelector('#override-clear').addEventListener('click', () => { delete overrides[row.dataset.jobId]; save(KEYS.overrides, overrides); applyOverride(row); close(); });
      },
    });
  });

  /* —— 平替推荐 —— */
  const openSubstitutes = (record) => {
    if (!record) return;
    const activeRecords = records.filter((item) => !item.exclusion);
    const subs = core.findSubstitutes ? core.findSubstitutes(record, activeRecords, 12) : [];
    const body = subs.length
      ? '<p class="wanyu-dialog__lead">与 <b>' + escapeHtml(record.code) + '</b> 同类别、入围线相近且竞争更缓的替代岗位：</p><div class="substitute-list">'
        + subs.map((item) => {
          const base = Number(item.competition_base || 0);
          const ratioText = base > 0 ? '1:' + (base / Number(item.recruits || 1)).toFixed(1) : '—';
          const line = parseNum(item.fields?.['最低入围/线'] ?? item.fields?.['最低面试线']);
          return '<div class="substitute-item"><div><strong>' + escapeHtml(item.code) + '</strong><span>' + escapeHtml(item.city) + '市 · ' + escapeHtml(item.unit_position) + '</span></div>'
            + '<small>竞争 ' + ratioText + ' · 入围 ' + (line !== null ? line.toFixed(1) : '—') + ' · 招' + item.recruits + '</small>'
            + '<button type="button" class="text-button" data-sub-code="' + escapeHtml(item.code) + '">加入限定 →</button></div>';
        }).join('') + '</div>'
      : '<p class="wanyu-dialog__lead">没有找到明显更优的同口径平替——该岗位在“同类别 + 入围线 ±3 分”范围内已算竞争较缓的选择。</p>';
    window.wanyuOverlay('平替推荐 · ' + record.code, body, {
      onMount(wrap) {
        wrap.querySelectorAll('[data-sub-code]').forEach((button) => button.addEventListener('click', () => {
          window.__wanyuBulkCodes = [button.dataset.subCode];
          document.getElementById('clear-bulk-codes')?.classList.remove('is-hidden');
          location.hash = '#jobs_search';
          search?.dispatchEvent(new Event('input', { bubbles: false }));
          wrap.remove();
        }));
      },
    });
  };
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-substitute-for]');
    if (!button) return;
    openSubstitutes(recordById.get(button.dataset.substituteFor));
  });

  /* —— 检索过滤 —— */
  const eligibilityOf = (row) => (window.wanyuEligibility ? window.wanyuEligibility.evaluate(row.dataset.tags) : { ok: true, reasons: [] });
  const natureFilter = document.querySelector('#nature-filter');
  const filter = () => {
    const q = (search?.value || '').trim().toLowerCase();
    const activeTags = window.__wanyuActiveTags || [];
    const codes = window.__wanyuBulkCodes || [];
    const nature = natureFilter?.value || '';
    let visible = 0;
    rows.forEach((row) => {
      const base = (!q || row.dataset.search.toLowerCase().includes(q)) && (!city?.value || row.dataset.city === city.value) && (!exam?.value || row.dataset.exam === exam.value)
        && (!nature || String(row.dataset.natures || '').split(/\s+/).includes(nature));
      const tagHit = !activeTags.length || activeTags.some((tag) => String(row.dataset.tags || '').split(/\s+/).includes(tag));
      const codeHit = !codes.length || codes.includes(String(row.dataset.jobCode || ''));
      const verdict = eligibilityOf(row);
      const hit = base && tagHit && codeHit && verdict.ok;
      row.hidden = !hit;
      row.classList.toggle('is-blocked', Boolean(base && !verdict.ok));
      if (hit) visible += 1;
    });
    if (count) count.textContent = visible.toLocaleString('en-US');
    if (empty) empty.hidden = visible !== 0;
    announce('当前显示 ' + visible.toLocaleString('en-US') + ' 条岗位' + (codes.length ? '（已限定代码）' : '') + (activeTags.length ? '（标签筛选）' : ''));
  };
  document.addEventListener('wanyu:profile-changed', () => { filter(); });
  let kbdIndex = -1;
  const visibleRows = () => rows.filter((row) => !row.hidden);
  const moveKbd = (delta) => {
    const pool = visibleRows();
    if (!pool.length) return;
    kbdIndex = (kbdIndex + delta + pool.length) % pool.length;
    pool.forEach((row, index) => row.classList.toggle('is-kbd', index === kbdIndex));
    pool[kbdIndex].scrollIntoView({ block: 'nearest' });
  };
  const actOnKbd = (selector) => {
    const pool = visibleRows();
    const row = pool[kbdIndex];
    if (!row) return;
    row.querySelector(selector)?.click();
  };
  document.addEventListener('keydown', (event) => {
    const editable = event.target && typeof event.target.matches === 'function' && (event.target.matches('input, textarea, select') || event.target.isContentEditable);
    if (editable || event.ctrlKey || event.altKey || event.metaKey) return;
    const inSearchView = document.body.dataset.activeView === 'jobs_search' || document.querySelector('#jobs-search-table');
    if (!inSearchView) return;
    if (event.key === 'j') { event.preventDefault(); moveKbd(1); }
    else if (event.key === 'k') { event.preventDefault(); moveKbd(-1); }
    else if (event.key === 's') { event.preventDefault(); actOnKbd('[data-job-save]'); }
    else if (event.key === 'c') { event.preventDefault(); actOnKbd('[data-job-compare]'); }
  });

  /* —— 对比与收藏 —— */
  const renderCompare = () => {
    const list = document.querySelector('#jobs-compare-list');
    const emptyState = document.querySelector('#jobs-compare-empty');
    const countNode = document.querySelector('#jobs-compare-count');
    const searchCount = document.querySelector('#search-compare-count');
    if (countNode) countNode.textContent = selected.size + ' / ' + COMPARE_LIMIT;
    if (searchCount) searchCount.textContent = selected.size + ' / ' + COMPARE_LIMIT;
    if (emptyState) emptyState.hidden = selected.size > 0;
    document.querySelectorAll('#copy-job-compare, #export-job-compare, #clear-job-compare').forEach((button) => { button.disabled = selected.size === 0; });
    if (!list) return;
    const parseCell = (value) => { const num = Number.parseFloat(String(value ?? '').replace(/[^0-9.]/g, '')); return Number.isFinite(num) ? num : null; };
    const items = [...selected.values()];
    const bestOf = (key, mode) => {
      if (items.length < 2) return null;
      let best = null;
      items.forEach((item) => {
        const num = parseCell(item[key]);
        if (num === null) return;
        if (!best || (mode === 'max' ? num > best.num : num < best.num)) best = { id: item.id, num };
      });
      return best?.id || null;
    };
    // 每列相对更优者标绿：招录更高、其余（报名/审核/有效/入围线/最高分）更低
    const best = {
      recruits: bestOf('recruits', 'max'), registration: bestOf('registration', 'min'), audit: bestOf('audit', 'min'),
      effective: bestOf('effective', 'min'), minimum: bestOf('minimum', 'min'), highest: bestOf('highest', 'min'),
    };
    const field = (label, value, bestId) => '<div><dt>' + label + '</dt><dd' + (bestId ? ' class="is-best" title="本列相对更优"' : '') + '>' + escapeHtml(String(value)) + '</dd></div>';
    list.innerHTML = items.map((record, index) => '<article class="compare-position-card" data-compare-card="' + escapeHtml(record.id) + '"><header><div class="compare-position-card__title"><span class="compare-index">' + String(index + 1).padStart(2, '0') + '</span><div><p>' + escapeHtml(record.city) + '市 · ' + escapeHtml(record.exam) + '</p><h3>' + escapeHtml(record.code) + '</h3><strong>' + escapeHtml(record.position) + '</strong></div></div><button class="compare-remove" type="button" data-remove-job="' + escapeHtml(record.id) + '">移除</button></header><dl>'
      + field('招录人数', record.recruits + ' 人', best.recruits === record.id)
      + field('报名', record.registration, best.registration === record.id)
      + field('审核合格', record.audit, best.audit === record.id)
      + field('有效笔试/达线', record.effective, best.effective === record.id)
      + field('最低入围/线', record.minimum, best.minimum === record.id)
      + field('最高笔试', record.highest, best.highest === record.id)
      + '</dl></article>').join('');
    list.querySelectorAll('[data-remove-job]').forEach((button) => button.addEventListener('click', () => { selected.delete(button.dataset.removeJob); persist(); renderCompare(); syncButtons(); announce('已移除岗位，当前选择 ' + selected.size + ' 条'); }));
  };
  /* —— 模拟↔收藏联动：读取 wanyu.simState.v1，给收藏卡标档位、体检报稳档数 —— */
  const EXAM_COMPOSE = { 事业单位: (a, b) => a + b, 省考: (a, b) => (a + b) / 2 };
  const BAND_TEXT = { safe: '稳', hit: '达线', near: '贴线', miss: '差分' };
  const simSnapshot = () => {
    const state = store('wanyu.simState.v1', 'null');
    if (!state || !EXAM_COMPOSE[state.exam]) return null;
    const pair = Array.isArray(state.scores) ? state.scores.map(Number) : [];
    if (pair.length !== 2 || !pair.every((value) => Number.isFinite(value))) return null;
    return { exam: state.exam, composite: EXAM_COMPOSE[state.exam](pair[0], pair[1]), vol: Number(state.vol) || 0 };
  };
  const bandKeyOf = (score, line) => (core.bandOf ? core.bandOf(score, line) : (score >= line + 5 ? 'safe' : score >= line ? 'hit' : score >= line - 3 ? 'near' : 'miss'));
  const savedBandOf = (record, sim) => {
    if (!sim || record.exam !== sim.exam) return null;
    // 兼容两种形态：检索页扁平 record.minimum / payload 完整 record.fields
    const line = parseNum(record.minimum ?? record.fields?.['最低入围/线'] ?? record.fields?.['最低面试线']);
    if (line === null) return null;
    return bandKeyOf(sim.composite, line);
  };
  const groupState = () => {
    const state = store(KEYS.groups, '{}') || {};
    if (!Array.isArray(state.list)) state.list = [];
    if (!state.byJob || typeof state.byJob !== 'object') state.byJob = {};
    return state;
  };
  const notesState = () => store(KEYS.notes, '{}') || {};
  const renderSaved = () => {
    const list = document.querySelector('#saved-jobs-list');
    const emptyState = document.querySelector('#saved-jobs-empty');
    const countNode = document.querySelector('#saved-jobs-count');
    if (countNode) countNode.textContent = String(saved.size);
    if (emptyState) emptyState.hidden = saved.size > 0;
    if (!list) return;
    const groups = groupState();
    const notes = notesState();
    const sim = simSnapshot();
    const field = (label, value) => '<div><dt>' + label + '</dt><dd>' + escapeHtml(value) + '</dd></div>';
    const groupOptions = (current) => ['<option value="">未分组</option>']
      .concat(groups.list.map((name) => '<option value="' + escapeHtml(name) + '"' + (current === name ? ' selected' : '') + '>' + escapeHtml(name) + '</option>'))
      .concat(['<option value="__new">＋ 新建分组…</option>']).join('');
    list.innerHTML = [...saved.values()].map((record, index) => {
      const band = savedBandOf(record, sim);
      const bandBadge = band ? '<span class="sim-band sim-band--' + band + '" title="按当前模拟分 ' + sim.composite.toFixed(1) + ' 对照该岗入围线' + (sim.vol ? '（波动±' + sim.vol + '）' : '') + '">' + BAND_TEXT[band] + '</span>' : '';
      return '<article class="saved-position-card" data-saved-card="' + escapeHtml(record.id) + '" data-group="' + escapeHtml(groups.byJob[record.id] || '') + '"><header><div class="saved-position-card__title"><span class="saved-index">' + String(index + 1).padStart(2, '0') + '</span><div><p>' + escapeHtml(record.city) + '市 · ' + escapeHtml(record.exam) + '</p><h3>' + escapeHtml(record.code) + '</h3>' + bandBadge + '<strong>' + escapeHtml(record.position) + '</strong></div></div><button class="saved-remove" type="button" data-remove-saved="' + escapeHtml(record.id) + '">移除</button></header>'
      + '<dl>' + field('招录人数', record.recruits + ' 人') + field('报名', record.registration) + field('有效笔试/达线', record.effective) + field('最低入围/线', record.minimum) + '</dl>'
      + '<div class="saved-card-tools"><select data-saved-group aria-label="收藏分组">' + groupOptions(groups.byJob[record.id] || '') + '</select>'
      + '<button type="button" class="text-button" data-job-detail="' + escapeHtml(record.id) + '">详情</button>'
      + '<button type="button" class="text-button" data-substitute-for="' + escapeHtml(record.id) + '">找平替</button></div>'
      + '<textarea class="saved-note" data-saved-note rows="1" placeholder="写点笔记：电话、顾虑、复核事项…（自动保存）">' + escapeHtml(notes[record.id] || '') + '</textarea>'
      + '<a href="#jobs_search" data-open-saved="' + escapeHtml(record.id) + '">回到检索定位 →</a></article>';
    }).join('');
    list.querySelectorAll('[data-remove-saved]').forEach((button) => button.addEventListener('click', () => { saved.delete(button.dataset.removeSaved); persistSaved(); renderSaved(); syncSaveButtons(); announce('已移除收藏，当前收藏 ' + saved.size + ' 条'); }));
    list.querySelectorAll('[data-saved-group]').forEach((select) => select.addEventListener('change', () => {
      if (select.value === '__new') { renderSaved(); window.wanyuOverlay('新建收藏分组', '<label class="sim-control--meta"><span>分组名称</span><input id="new-group-name" type="text" placeholder="例如：家乡保底"></label>', { footer: '<button type="button" class="primary-button" id="new-group-save">保存</button>', onMount(wrap, close) { wrap.querySelector('#new-group-save').addEventListener('click', () => { const name = String(wrap.querySelector('#new-group-name').value || '').trim(); if (name) { const state = groupState(); if (!state.list.includes(name)) state.list.push(name); save(KEYS.groups, state); } close(); renderSaved(); }); } }); return; }
      const id = select.closest('[data-saved-card]').dataset.savedCard;
      const state = groupState();
      if (select.value) state.byJob[id] = select.value; else delete state.byJob[id];
      save(KEYS.groups, state);
      renderSaved();
      renderGroupBar();
    }));
    list.querySelectorAll('[data-saved-note]').forEach((area) => area.addEventListener('change', () => {
      const notes2 = notesState();
      const id = area.closest('[data-saved-card]').dataset.savedCard;
      if (area.value.trim()) notes2[id] = area.value; else delete notes2[id];
      save(KEYS.notes, notes2);
      announce('笔记已保存');
    }));
    renderGroupBar();
    renderAudit();
  };
  const renderGroupBar = () => {
    const bar = document.querySelector('#saved-group-bar');
    if (!bar) return;
    const groups = groupState();
    const counts = { '': saved.size };
    groups.list.forEach((name) => { counts[name] = [...saved.keys()].filter((id) => groups.byJob[id] === name).length; });
    counts[''] = saved.size - Object.values(groups.byJob).filter((id) => saved.has(id)).length;
    const active = bar.dataset.activeGroup || '';
    bar.innerHTML = Object.entries(counts).filter(([, value]) => value > 0 || !bar.childElementCount).map(([name, value]) => '<button type="button" class="tag-chip' + (active === name ? ' is-active' : '') + '" data-group-chip="' + escapeHtml(name) + '">' + (name ? escapeHtml(name) : '未分组') + ' <b>' + value + '</b></button>').join('');
    bar.querySelectorAll('[data-group-chip]').forEach((chip) => chip.addEventListener('click', () => {
      bar.dataset.activeGroup = bar.dataset.activeGroup === chip.dataset.groupChip ? '' : chip.dataset.groupChip;
      const current = bar.dataset.activeGroup;
      list.querySelectorAll('[data-saved-card]').forEach((card) => { card.hidden = Boolean(current) && (groups.byJob[card.dataset.savedCard] || '') !== current; });
      bar.querySelectorAll('[data-group-chip]').forEach((item) => item.classList.toggle('is-active', item.dataset.groupChip === current));
    }));
  };
  const renderAudit = () => {
    const board = document.querySelector('#saved-audit');
    if (!board) return;
    const listNode = document.querySelector('#saved-audit-list');
    if (!saved.size) { board.hidden = true; if (listNode) listNode.innerHTML = ''; return; }
    board.hidden = false;
    const items = [];
    const records2 = [...saved.keys()].map((id) => recordById.get(id)).filter(Boolean);
    const ratios = records2.map((record) => { const base = Number(record.competition_base || 0); return base > 0 ? Number(record.recruits || 0) / base : null; }).filter((value) => value !== null);
    const poolRatios = factorPool.map((item) => item.ratio).filter((value) => value > 0).sort((a, b) => a - b);
    const poolMedian = poolRatios.length ? poolRatios[Math.floor(poolRatios.length / 2)] : 0;
    const multi = records2.filter((record) => Number(record.recruits || 0) >= 2).length;
    items.push(['info', '共收藏 ' + records2.length + ' 条岗位，其中多人岗 ' + multi + ' 条（' + Math.round(multi / records2.length * 100) + '%）' + (multi / records2.length < 0.3 ? '——多人岗容错更高，可再补几条' : '')]);
    const sim = simSnapshot();
    const safeNode = document.querySelector('#saved-sim-safe');
    if (sim) {
      const bands = { safe: 0, hit: 0, near: 0, miss: 0, other: 0 };
      records2.forEach((record) => {
        const band = savedBandOf(record, sim);
        if (band) bands[band] += 1; else bands.other += 1;
      });
      items.push(['info', '按当前模拟分（' + sim.exam + ' ' + sim.composite.toFixed(1) + ' 分）：稳 ' + bands.safe + ' · 达线 ' + bands.hit + ' · 贴线 ' + bands.near + ' · 差分 ' + bands.miss + (bands.other ? '（另有 ' + bands.other + ' 条非' + sim.exam + '类别或无入围线，不参与对照）' : '')]);
      if (safeNode) safeNode.textContent = bands.safe + ' 条';
    } else if (safeNode) {
      safeNode.textContent = '—';
    }
    if (ratios.length) {
      const max = Math.max(...ratios);
      const min = Math.min(...ratios);
      // ratios 值 = 招录 ÷ 分母，越大越缓：max 对应最缓（N 最小），min 对应最紧
      items.push(max >= poolMedian ? ['ok', '竞争跨度健康：最缓 1:' + (1 / max).toFixed(1) + '，最紧 1:' + (1 / min).toFixed(1) + '，已含低于全省中位数的保底选项'] : ['warn', '全是高竞争岗位：最缓的 1:' + (1 / max).toFixed(1) + ' 仍高于全省中位竞争，建议补 1–2 条低竞争保底岗']);
    }
    const conflicts = records2.filter((record) => window.wanyuEligibility && !window.wanyuEligibility.evaluate((record.eligibility?.tags || []).join(' ')).ok);
    items.push(conflicts.length ? ['warn', '有 ' + conflicts.length + ' 条与你的身份条件冲突（' + conflicts.map((record) => record.code).slice(0, 4).join('、') + '），报名前务必复核'] : ['ok', '全部收藏岗位与你的身份条件相符']);
    const noLine = records2.filter((record) => parseNum(record.fields?.['最低入围/线'] ?? record.fields?.['最低面试线']) === null).length;
    if (noLine) items.push(['info', noLine + ' 条岗位源表未提供入围线，分数模拟中不参与对照']);
    const groups = groupState();
    const ungrouped = [...saved.keys()].filter((id) => !groups.byJob[id]).length;
    if (ungrouped && groups.list.length) items.push(['info', ungrouped + ' 条未分组，可用卡片上的分组下拉整理']);
    if (listNode) listNode.innerHTML = items.map(([kind, text]) => '<li class="audit-item audit-item--' + kind + '"><span aria-hidden="true">' + (kind === 'ok' ? '✓' : kind === 'warn' ? '⚠' : '·') + '</span>' + text + '</li>').join('');
  };
  const openCompare = () => { location.hash = '#jobs_compare'; };
  rows.forEach((row) => row.querySelector('[data-job-compare]')?.addEventListener('click', () => { const id = row.dataset.jobId; const srcRecord = recordById.get(String(id)); if (selected.has(id)) { selected.delete(id); announce('已移除岗位，当前选择 ' + selected.size + ' 条'); } else if (selected.size < COMPARE_LIMIT) { selected.set(id, srcRecord ? recordFromData(srcRecord) : recordFromRow(row)); announce('已加入岗位对比，当前选择 ' + selected.size + ' 条'); } else { announce('最多选择 ' + COMPARE_LIMIT + ' 条岗位'); return; } persist(); renderCompare(); syncButtons(); }));
  rows.forEach((row) => row.querySelector('[data-job-save]')?.addEventListener('click', () => { const id = row.dataset.jobId; const srcRecord = recordById.get(String(id)); if (saved.has(id)) { saved.delete(id); announce('已取消收藏，当前收藏 ' + saved.size + ' 条'); } else { saved.set(id, srcRecord ? recordFromData(srcRecord) : recordFromRow(row)); announce('已收藏岗位，当前收藏 ' + saved.size + ' 条'); } persistSaved(); renderSaved(); syncSaveButtons(); }));
  document.querySelector('#open-job-compare')?.addEventListener('click', openCompare);
  search?.addEventListener('input', filter); city?.addEventListener('change', filter); exam?.addEventListener('change', filter); natureFilter?.addEventListener('change', filter);
  document.addEventListener('keydown', (event) => { const target = event.target; const editable = target && typeof target.matches === 'function' && (target.matches('input, textarea, select') || target.isContentEditable); if (event.key === '/' && !editable) { event.preventDefault(); search?.focus(); search?.select(); } else if (event.key === 'Escape' && document.activeElement === search) { search.value = ''; filter(); search.focus(); } });
  document.querySelector('#reset-search')?.addEventListener('click', () => { search.value = ''; city.value = ''; exam.value = ''; if (natureFilter) natureFilter.value = ''; if (window.__wanyuBulkCodes && window.__wanyuBulkCodes.length) { window.__wanyuBulkCodes = []; document.getElementById('clear-bulk-codes')?.classList.add('is-hidden'); announce('批量代码限定已解除'); } filter(); search.focus(); });
  document.querySelector('#clear-job-compare')?.addEventListener('click', () => { selected.clear(); persist(); renderCompare(); syncButtons(); announce('已清空岗位对比'); });
  document.querySelector('#clear-saved-jobs')?.addEventListener('click', () => { saved.clear(); persistSaved(); renderSaved(); syncSaveButtons(); announce('已清空收藏'); });
  document.querySelector('#copy-job-compare')?.addEventListener('click', async () => { if (!selected.size) { announce('暂无可复制的岗位'); return; } const text = [...selected.values()].map((item) => item.city + '市 ' + item.code + ' ' + item.position + ' ' + item.recruits + '人').join('\n'); try { await navigator.clipboard.writeText(text); announce('岗位对比摘要已复制'); } catch { announce('复制失败，请改用导出 CSV'); } });
  document.querySelector('#export-job-compare')?.addEventListener('click', () => { if (!selected.size) { announce('暂无可导出的岗位'); return; } const header = ['城市', '代码', '单位与职位', '类别', '招录人数', '报名', '审核合格', '有效笔试/达线', '最低入围/线', '最高笔试'].map(csvCell).join(','); const lines = [...selected.values()].map((item) => [item.city, item.code, item.position, item.exam, item.recruits, item.registration, item.audit, item.effective, item.minimum, item.highest].map(csvCell).join(',')); const csv = '\ufeff' + [header, ...lines].join('\n'); const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })); link.download = '岗位对比.csv'; link.click(); URL.revokeObjectURL(link.href); announce('岗位对比 CSV 已导出'); });
  const syncButtons = () => rows.forEach((row) => { const button = row.querySelector('[data-job-compare]'); if (!button) return; const added = selected.has(row.dataset.jobId); button.classList.toggle('is-added', added); button.setAttribute('aria-pressed', String(added)); button.textContent = added ? '已加入' : '+ 加入对比'; });
  const syncSaveButtons = () => rows.forEach((row) => { const button = row.querySelector('[data-job-save]'); if (!button) return; const added = saved.has(row.dataset.jobId); button.classList.toggle('is-saved', added); button.setAttribute('aria-pressed', String(added)); button.textContent = added ? '★ 已收藏' : '☆ 收藏'; });
  // 详情浮层 / 模拟页直接改 localStorage 后广播，这里同步检索页状态
  document.addEventListener('wanyu:saved-changed', () => { restoreSaved(); renderSaved(); syncSaveButtons(); });
  document.addEventListener('wanyu:compare-changed', () => { restore(); renderCompare(); syncButtons(); });
  restore(); restoreSaved(); injectScores(); sortRows(); filter(); renderCompare(); renderSaved(); syncButtons(); syncSaveButtons();
})();
