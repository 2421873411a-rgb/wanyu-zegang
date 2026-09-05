(() => {
  const data = window.productData || {}; const jobsData = data.jobs || data; const cities = jobsData.cities || []; const motion = window.wanyuMotion || {};
  const metricNames = { jobs: '岗位数', recruits: '招录人数', ratio: '竞争比' };
  const ratioIsComparable = (item) => Boolean(item && (item.ratio_comparable === true || item.ratio_status === 'single_denominator'));
  const metricValue = (item, key) => key === 'ratio' ? (ratioIsComparable(item) ? Number(item?.ratio || 0) : 0) : Number(item?.[key] || 0);
  const formatRatio = (value) => { const numeric = Number(value || 0); return numeric > 0 ? `1:${(1 / numeric).toFixed(1)}` : '—'; };
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
  const cleanMajorOption = (value) => String(value || '').trim().replace(/^[^\u4e00-\u9fffA-Za-z]+/, '').trim();
  const isHumanMajor = (value) => { const text = cleanMajorOption(value); return text.length >= 2 && /[\u4e00-\u9fffA-Za-z]/.test(text) && text.replace(/[\d\s()[\]{}._（）【】+\-*\/、，,;；:.：?？]/g, '').length > 0; };
  const normalizeMajor = (value) => String(value || '').replace(/\s+/g, '').toLocaleLowerCase();
  const rankingRows = Array.isArray(data.records) && data.records.length ? data.records : ((data.allMajors || {}).rows || []);
  const sourceRowsByCity = new Map();
  rankingRows.filter((row) => row && typeof row === 'object').forEach((row) => {
    const city = String(row.city || '');
    if (!city) return;
    if (!sourceRowsByCity.has(city)) sourceRowsByCity.set(city, []);
    sourceRowsByCity.get(city).push(row);
  });
  const majorSourceText = rankingRows.map((row) => String(row?.zy || '')).filter(Boolean).join('\n');
  const metadata = data.allMajors?.meta || {};
  const candidateMajors = [...(Array.isArray(metadata.cats) ? metadata.cats : []), ...(Array.isArray(metadata.majors) ? metadata.majors : [])]
    .map(cleanMajorOption)
    .filter((value, index, values) => isHumanMajor(value) && value.length <= 40 && values.indexOf(value) === index && majorSourceText.includes(value))
    .sort((a, b) => a.localeCompare(b, 'zh'));
  const rowMajorText = (city) => (sourceRowsByCity.get(city) || []).map((row) => String(row.zy || '')).filter(Boolean).join('；');
  const validMetrics = new Set(Object.keys(metricNames)); const query = new URLSearchParams(location.search); const queryMetric = query.get('metric'); let metric = validMetrics.has(queryMetric) ? queryMetric : 'jobs'; let majorName = String(query.get('major') || '').trim(); const selected = new Set();
  const hydrateMajorControls = () => {
    const input = document.querySelector('#ranking-major-input'); const list = document.querySelector('#ranking-major-options');
    if (input && document.activeElement !== input) input.value = majorName;
    if (list && !list.childElementCount) {
      const fallback = rankingRows.map((row) => cleanMajorOption(row?.zy)).filter(isHumanMajor);
      const options = candidateMajors.length ? candidateMajors : [...new Set(fallback)].sort((a, b) => a.localeCompare(b, 'zh'));
      list.innerHTML = options.map((value) => `<option value="${escapeHtml(value)}"></option>`).join('');
    }
    document.querySelectorAll('[data-ranking-row]').forEach((row) => { row.dataset.rankingMajor = rowMajorText(row.dataset.city); });
  };
  const majorMatches = (row) => !normalizeMajor(majorName) || normalizeMajor(row.dataset.rankingMajor).includes(normalizeMajor(majorName));
  const renderSummary = () => {
    const wrap = document.querySelector('#jobs-compare-bars'); const note = document.querySelector('#jobs-compare-summary-note');
    if (!wrap) return;
    if (!selected.size) { wrap.innerHTML = '<p class="compare-summary__empty">从排名表选择城市，查看同口径数据。</p>'; if (note) note.textContent = '选择 1–4 个城市查看'; return; }
    const values = [...selected].map((city) => metricValue(cities.find((entry) => entry.city === city), metric)); const max = Math.max(...values, 1);
    wrap.innerHTML = [...selected].map((city) => { const item = cities.find((entry) => entry.city === city); const value = metricValue(item, metric); const unit = metric === 'ratio' ? '1:N' : metric === 'jobs' ? '岗' : '人'; const ratioNote = ratioIsComparable(item) ? formatRatio(item?.ratio) : '不可比'; return `<div class="compare-bar" data-compare-bar data-city="${city}"><span class="compare-bar__label">${city}市</span><span class="compare-bar__track"><i class="compare-bar__fill" style="--bar-width:${Math.max(5, value / max * 100).toFixed(1)}%"></i></span><strong class="compare-bar__value">${metric === 'ratio' ? formatRatio(value) : value.toLocaleString('en-US')} ${unit}</strong><small class="compare-bar__sub">岗位 ${item?.jobs ?? '—'} · 招录 ${item?.recruits ?? '—'} · 竞争比 ${ratioNote}</small></div>`; }).join('');
    if (note) note.textContent = `${selected.size} 个城市 · 当前按${metricNames[metric]}排序`;
  };
  const render = () => {
    const rows = [...document.querySelectorAll('[data-ranking-row]')];
    if (!rows.length) return; /* v9.9.3：历史周期页无排名表 DOM，直接返回避免后续裸写入抛错 */
    hydrateMajorControls();
    const visibleRows = rows.filter(majorMatches);
    rows.forEach((row) => { row.hidden = !majorMatches(row); if (row.hidden) row.querySelector('.rank-cell').textContent = '—'; });
    rows.forEach((row) => motion.transition?.(row, 'is-rank-shifting', 480));
    visibleRows.sort((a, b) => (metric === 'ratio' ? Number(b.dataset.ratioComparable === 'true' ? b.dataset.ratio : 0) - Number(a.dataset.ratioComparable === 'true' ? a.dataset.ratio : 0) : Number(b.dataset[metric]) - Number(a.dataset[metric])) || a.dataset.city.localeCompare(b.dataset.city, 'zh'));
    const body = document.querySelector('#jobs-ranking-table tbody'); visibleRows.forEach((row, index) => { row.querySelector('.rank-cell').textContent = String(index + 1).padStart(2, '0'); body.appendChild(row); }); rows.filter((row) => row.hidden).forEach((row) => body.appendChild(row));
    const rankNote = document.querySelector('#ranking-note'); if (rankNote) rankNote.textContent = `按${metricNames[metric]}降序`; const filterCount = document.querySelector('#ranking-filter-count'); if (filterCount) filterCount.textContent = majorName ? `专业“${majorName}” · ${visibleRows.length} / ${rows.length} 城市` : `全部城市 · ${rows.length} 个`; renderSummary();
    document.querySelectorAll('#ranking-metric [data-metric]').forEach((button) => button.classList.toggle('is-selected', button.dataset.metric === metric));
    const url = new URL(location.href); url.searchParams.set('metric', metric); majorName ? url.searchParams.set('major', majorName) : url.searchParams.delete('major'); history.replaceState({}, '', url);
  };
  const renderCompare = () => {
    const wrap = document.querySelector('#compare-cards');
    if (!wrap) return; /* v9.9.3：历史周期页无对比停靠 DOM */
    wrap.innerHTML = [...selected].map((city) => { const item = cities.find((entry) => entry.city === city); return `<div class="compare-card"><strong>${city}市</strong><span>${item.jobs} 岗 · ${item.recruits} 人 · 竞争比 ${ratioIsComparable(item) ? formatRatio(item.ratio) : '不可比'} <button data-remove-city="${city}" type="button">×</button></span></div>`; }).join('');
    const countNode = document.querySelector('#compare-count'); if (countNode) countNode.textContent = `${selected.size} / 4`;
    const emptyNode = document.querySelector('#compare-empty'); if (emptyNode) emptyNode.hidden = selected.size > 0;
    document.querySelector('#jobs-compare-guide')?.toggleAttribute('hidden', selected.size > 0); renderSummary();
    wrap.querySelectorAll('[data-remove-city]').forEach((button) => button.addEventListener('click', () => { selected.delete(button.dataset.removeCity); renderCompare(); }));
  };
  document.querySelectorAll('#ranking-metric [data-metric]').forEach((button) => button.addEventListener('click', () => { metric = button.dataset.metric; render(); }));
  document.querySelector('#ranking-major-input')?.addEventListener('input', (event) => { majorName = String(event.target.value || '').trim(); render(); });
  document.querySelector('#ranking-major-clear')?.addEventListener('click', () => { majorName = ''; const input = document.querySelector('#ranking-major-input'); if (input) input.value = ''; render(); });
  document.querySelectorAll('[data-city-compare]').forEach((button) => button.addEventListener('click', () => { if (selected.size < 4 || selected.has(button.dataset.cityCompare)) selected.add(button.dataset.cityCompare); renderCompare(); }));
  document.querySelectorAll('[data-ranking-city]').forEach((button) => button.addEventListener('click', () => { selected.add(button.dataset.rankingCity); if (selected.size > 4) selected.delete([...selected][0]); renderCompare(); }));
  document.querySelector('#clear-compare')?.addEventListener('click', () => { selected.clear(); renderCompare(); }); hydrateMajorControls(); render(); renderCompare();
})();
