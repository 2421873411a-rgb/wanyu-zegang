(() => {
  const dataNode = document.querySelector('#page-data');
  const data = dataNode ? JSON.parse(dataNode.textContent || '{}') : {};
  const cities = data.cities || [];
  const metrics = data.metrics || { totals: { jobs: 0, recruits: 0 }, exam: {}, cities: [] };
  const records = data.records || [];
  const recordById = new Map(records.map(record => [record.record_id, record]));
  const cityByName = new Map((metrics.cities || []).map(city => [city.city, city]));
  const cityFilter = document.querySelector('#city-filter');
  const examFilter = document.querySelector('#exam-filter');
  const finderCityFilter = document.querySelector('#finder-city-filter');
  const finderExamFilter = document.querySelector('#finder-exam-filter');
  const search = document.querySelector('#job-search');
  const countLabel = document.querySelector('#result-count');
  const emptyState = document.querySelector('#job-empty');
  const groups = [...document.querySelectorAll('.job-group')];
  const sections = [...document.querySelectorAll('.city-section')];
  const allRows = [...document.querySelectorAll('tr[data-job-id]')];
  const normalize = value => String(value || '').trim().toLocaleLowerCase('zh-CN').replace(/\s+/g, ' ');
  let debounceTimer = 0;
  let metric = 'jobs';
  let selectedCity = '';
  let compared = ['合肥', '滁州', '马鞍山'];
  let savedJobs = [];

  function syncUrl() {
    const params = new URLSearchParams(location.search);
    if (selectedCity) params.set('city', selectedCity); else params.delete('city');
    if (metric !== 'jobs') params.set('metric', metric); else params.delete('metric');
    history.replaceState(null, '', `${location.pathname}?${params.toString()}${location.hash}`);
  }

  function metricValue(city, key = metric) {
    if (!city) return metrics.totals[key === 'ratio' ? 'jobs' : key] || 0;
    if (key === 'ratio') return Number(city.recruits || 0) / Math.max(Number(city.jobs || 0), 1);
    return Number(city[key] || 0);
  }

  function formatMetric(value, key = metric) {
    if (key === 'ratio') return Number(value).toFixed(2);
    return Number(value).toLocaleString('zh-CN');
  }

  function updateMap() {
    const values = cities.map(item => metricValue(cityByName.get(item.city)));
    const min = Math.min(...values, 0);
    const max = Math.max(...values, 1);
    document.querySelectorAll('.jobs-map__region').forEach(region => {
      const item = cityByName.get(region.dataset.city);
      const ratio = (metricValue(item) - min) / Math.max(max - min, 1);
      const hue = 210 - Math.round(ratio * 13);
      const lightness = 91 - Math.round(ratio * 37);
      region.style.fill = `hsl(${hue} 78% ${lightness}%)`;
      region.style.setProperty('--job-ratio', ratio.toFixed(3));
    });
  }

  function updateInspector(cityName = selectedCity) {
    const city = cityName ? cityByName.get(cityName) : null;
    const value = metricValue(city);
    const unit = metric === 'ratio' ? '人/岗' : metric === 'recruits' ? '人' : '岗';
    const label = document.querySelector('#inspector-city');
    const valueNode = document.querySelector('#job-metric-value');
    const unitNode = document.querySelector('#job-metric-unit');
    const context = document.querySelector('#job-metric-context');
    if (label) label.textContent = city ? `${city.city}市` : '安徽省';
    if (valueNode) animateJobNumber(valueNode, value, metric === 'ratio' ? 2 : 0);
    if (unitNode) unitNode.textContent = unit;
    if (context) context.textContent = city ? `${metric === 'jobs' ? '岗位总数' : metric === 'recruits' ? '招录人数' : '单岗平均招录人数'} · ${city.city}市` : '全省岗位总数';
    const exam = city?.exam || metrics.exam || {};
    const totalJobs = city ? Number(city.jobs || 0) : Number(metrics.totals.jobs || 0);
    const pct = key => totalJobs ? Number(exam[key]?.jobs || 0) / totalJobs * 100 : 0;
    const p1 = pct('省考'), p2 = pct('事业单位'), p3 = pct('国考');
    const donut = document.querySelector('#inspector-donut');
    if (donut) { donut.style.setProperty('--p1', `${p1}%`); donut.style.setProperty('--p2', `${p2}%`); donut.style.setProperty('--p3', `${p3}%`); }
    const setText = (id, key) => { const node = document.querySelector(id); if (node) node.textContent = `${Number(exam[key]?.jobs || 0).toLocaleString('zh-CN')} · ${pct(key).toFixed(1)}%`; };
    setText('#inspector-provincial', '省考'); setText('#inspector-institution', '事业单位'); setText('#inspector-national', '国考');
    const rank = city ? [...cities].sort((a, b) => metricValue(cityByName.get(b.city)) - metricValue(cityByName.get(a.city))).findIndex(item => item.city === city.city) + 1 : '—';
    const rankNode = document.querySelector('#inspector-rank'); if (rankNode) rankNode.textContent = city ? `${rank} / 16` : '—';
  }

  function setCity(city, shouldScroll = false) {
    selectedCity = city || '';
    document.querySelectorAll('[data-job-region], [data-map-city]').forEach(trigger => trigger.classList.toggle('is-active', Boolean(city) && trigger.dataset.jobRegion === city || trigger.dataset.mapCity === city));
    document.querySelectorAll('[data-job-region]').forEach(region => region.setAttribute('aria-pressed', String(Boolean(city) && region.dataset.jobRegion === city)));
    if (cityFilter) cityFilter.value = city || '';
    updateInspector(city);
    syncUrl();
    if (shouldScroll) document.querySelector('#job-finder')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function applyFilters() {
    const query = normalize(search?.value);
    const city = finderCityFilter?.value || '';
    const exam = finderExamFilter?.value || '';
    let visibleRows = 0;
    const visibleCities = new Set();
    groups.forEach(group => {
      const groupRows = [...group.querySelectorAll('tr[data-job-id]')];
      let matches = 0;
      groupRows.forEach(row => {
        const rowMatch = (!query || normalize(row.dataset.search).includes(query)) && (!city || row.dataset.jobCity === city) && (!exam || row.dataset.jobExam === exam);
        row.hidden = !rowMatch; if (rowMatch) matches += 1;
      });
      group.hidden = matches === 0; if (matches) visibleCities.add(group.dataset.city);
      const label = group.querySelector('.job-group__summary b'); if (label) label.textContent = query || city || exam ? `${matches}/${groupRows.length} 条记录` : `${groupRows.length} 条记录`;
      if (matches && (query || city || exam)) group.open = true;
    });
    sections.forEach(section => { section.hidden = !visibleCities.has(section.dataset.city); });
    visibleRows = allRows.filter(row => !row.hidden).length;
    if (countLabel) countLabel.textContent = `显示 ${visibleRows} 条岗位记录 · ${visibleCities.size} 座城市`;
    if (emptyState) emptyState.hidden = visibleRows !== 0;
  }

  function renderCompare() {
    const cardHost = document.querySelector('#compare-cards');
    const chartHost = document.querySelector('#city-compare-chart');
    const tableHost = document.querySelector('#city-compare-table');
    const chosen = compared.map(name => cityByName.get(name)).filter(Boolean);
    if (cardHost) cardHost.innerHTML = chosen.map((city, index) => `<article class="compare-card"><header><span>${String(index + 1).padStart(2, '0')}</span><h3>${city.city}市</h3></header><dl><div><dt>岗位数</dt><dd>${Number(city.jobs).toLocaleString('zh-CN')}</dd></div><div><dt>招录人数</dt><dd>${Number(city.recruits).toLocaleString('zh-CN')}</dd></div><div><dt>单岗平均</dt><dd>${(Number(city.recruits) / Math.max(Number(city.jobs), 1)).toFixed(2)}</dd></div></dl><div class="compare-stack"><i style="--segment:${(Number(city.exam?.省考?.jobs || 0) / city.jobs * 100).toFixed(2)}%"></i><i style="--segment:${(Number(city.exam?.事业单位?.jobs || 0) / city.jobs * 100).toFixed(2)}%"></i><i style="--segment:${(Number(city.exam?.国考?.jobs || 0) / city.jobs * 100).toFixed(2)}%"></i></div></article>`).join('');
    const max = Math.max(...chosen.map(city => city.jobs), 1);
    if (chartHost) chartHost.innerHTML = chosen.map(city => `<div><div class="chart-group"><span class="chart-bar" style="--height:${city.jobs / max * 100}%"><b>${city.jobs}</b></span><span class="chart-bar" style="--height:${city.recruits / max * 100}%"><b>${city.recruits}</b></span><span class="chart-bar" style="--height:${(city.exam?.事业单位?.jobs || 0) / max * 100}%"><b>${city.exam?.事业单位?.jobs || 0}</b></span></div><span class="chart-label">${city.city}市</span></div>`).join('');
    if (tableHost) tableHost.innerHTML = `<table><thead><tr><th>指标</th>${chosen.map(city => `<th>${city.city}市</th>`).join('')}</tr></thead><tbody><tr><td>岗位数</td>${chosen.map(city => `<td>${city.jobs}</td>`).join('')}</tr><tr><td>招录人数</td>${chosen.map(city => `<td>${city.recruits}</td>`).join('')}</tr><tr><td>事业单位岗位</td>${chosen.map(city => `<td>${city.exam?.事业单位?.jobs || 0}</td>`).join('')}</tr></tbody></table>`;
    const caption = document.querySelector('#compare-caption'); if (caption) caption.textContent = `当前选择：${compared.join(' · ')}`;
  }

  function renderTray() {
    const tray = document.querySelector('#job-compare-tray'); if (!tray) return;
    tray.hidden = savedJobs.length === 0;
    if (!savedJobs.length) { tray.innerHTML = ''; return; }
    tray.innerHTML = `<div class="job-compare-tray__items"><strong>岗位对比篮 · ${savedJobs.length}/5</strong>${savedJobs.map(id => { const job = recordById.get(id); return `<span class="job-compare-tray__item">${job.city} · ${job.code} · ${job.unit_position}</span>`; }).join('')}</div><div class="job-compare-tray__actions"><button type="button" data-tray-copy>复制摘要</button><button type="button" data-tray-export>导出 CSV</button><button type="button" data-tray-clear>清空</button></div>`;
    tray.querySelector('[data-tray-copy]')?.addEventListener('click', async () => { const text = savedJobs.map(id => { const job = recordById.get(id); return `${job.city} ${job.exam} ${job.code} ${job.unit_position} 招录${job.recruits}人`; }).join('\n'); try { await navigator.clipboard.writeText(text); } catch { window.prompt('复制岗位摘要', text); } });
    tray.querySelector('[data-tray-export]')?.addEventListener('click', () => exportJobs(savedJobs));
    tray.querySelector('[data-tray-clear]')?.addEventListener('click', () => { savedJobs = []; document.querySelectorAll('.job-compare-button.is-added').forEach(button => { button.classList.remove('is-added'); button.textContent = 'Add to compare'; }); renderTray(); });
  }

  function toggleSavedJob(button) {
    const id = button.closest('tr')?.dataset.jobId; if (!id) return;
    if (savedJobs.includes(id)) { savedJobs = savedJobs.filter(item => item !== id); button.classList.remove('is-added'); button.textContent = 'Add to compare'; }
    else if (savedJobs.length < 5) { savedJobs.push(id); button.classList.add('is-added'); button.textContent = 'Added'; }
    renderTray();
  }

  function exportJobs(ids = allRows.filter(row => !row.hidden).map(row => row.dataset.jobId)) {
    const header = ['城市', '考试类别', '代码', '单位与职位', '招录人数'];
    const lines = [header, ...ids.map(id => { const job = recordById.get(id); return [job.city, job.exam, job.code, job.unit_position, job.recruits]; })].map(row => row.map(value => `"${String(value ?? '').replaceAll('"', '""')}"`).join(','));
    const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = '皖域择岗岗位对比.csv'; link.click(); URL.revokeObjectURL(url);
  }

  function animateJobNumber(node, target, decimals = 0) {
    const value = Number(target) || 0; const start = Number(node.dataset.value || 0); node.dataset.value = String(value); if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) { node.textContent = decimals ? value.toFixed(decimals) : formatMetric(value); return; }
    const startTime = performance.now(); const duration = 420; const frame = now => { const progress = Math.min((now - startTime) / duration, 1); const eased = 1 - Math.pow(1 - progress, 3); const current = start + (value - start) * eased; node.textContent = decimals ? current.toFixed(decimals) : formatMetric(current); if (progress < 1) requestAnimationFrame(frame); }; requestAnimationFrame(frame);
  }

  document.querySelectorAll('[data-job-metric]').forEach(button => button.addEventListener('click', () => { metric = button.dataset.jobMetric; document.querySelectorAll('[data-job-metric]').forEach(item => item.setAttribute('aria-pressed', String(item === button))); document.querySelector('#ranking-title').textContent = metric === 'jobs' ? '按岗位数' : metric === 'recruits' ? '按招录人数' : '按单岗平均'; updateMap(); updateInspector(); syncUrl(); }));
  document.querySelectorAll('[data-job-region], [data-map-city]').forEach(trigger => { trigger.addEventListener('click', () => setCity(trigger.dataset.jobRegion || trigger.dataset.mapCity)); trigger.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setCity(trigger.dataset.jobRegion || trigger.dataset.mapCity); } }); });
  document.querySelectorAll('[data-ranking-city]').forEach(button => button.addEventListener('click', () => { setCity(button.dataset.rankingCity); cityFilter && (cityFilter.value = button.dataset.rankingCity); document.querySelector('#jobs-workbench')?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }));
  document.querySelectorAll('[data-compare-city]').forEach(button => button.addEventListener('click', () => { const city = button.dataset.compareCity; if (compared.includes(city)) { if (compared.length > 1) compared = compared.filter(item => item !== city); } else if (compared.length < 3) compared.push(city); else return; button.classList.toggle('is-selected', compared.includes(city)); button.setAttribute('aria-pressed', String(compared.includes(city))); renderCompare(); }));
  document.querySelectorAll('[data-job-compare]').forEach(button => button.addEventListener('click', () => toggleSavedJob(button)));
  finderCityFilter?.addEventListener('change', applyFilters); finderExamFilter?.addEventListener('change', applyFilters); search?.addEventListener('input', () => { clearTimeout(debounceTimer); debounceTimer = setTimeout(applyFilters, 80); });
  cityFilter?.addEventListener('change', () => setCity(cityFilter.value)); examFilter?.addEventListener('change', () => { if (finderExamFilter) finderExamFilter.value = examFilter.value; applyFilters(); });
  document.querySelector('#finder-clear')?.addEventListener('click', () => { if (search) search.value = ''; if (finderCityFilter) finderCityFilter.value = ''; if (finderExamFilter) finderExamFilter.value = ''; applyFilters(); search?.focus(); });
  document.querySelector('#clear-filters')?.addEventListener('click', () => { if (cityFilter) cityFilter.value = ''; if (examFilter) examFilter.value = ''; if (finderCityFilter) finderCityFilter.value = ''; if (finderExamFilter) finderExamFilter.value = ''; if (search) search.value = ''; setCity(''); applyFilters(); });
  document.querySelector('#toggle-groups')?.addEventListener('click', event => { const open = groups.some(group => !group.hidden && !group.open); groups.filter(group => !group.hidden).forEach(group => { group.open = open; }); event.currentTarget.textContent = open ? '收起分类' : '展开分类'; });
  document.querySelector('#inspector-action')?.addEventListener('click', () => { if (selectedCity && finderCityFilter) { finderCityFilter.value = selectedCity; applyFilters(); } });

  const params = new URLSearchParams(location.search); const linkedMetric = params.get('metric'); if (['jobs', 'recruits', 'ratio'].includes(linkedMetric)) { metric = linkedMetric; document.querySelectorAll('[data-job-metric]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.jobMetric === metric))); } const hashCity = decodeURIComponent(location.hash.replace(/^#city-/, '')); const linkedCity = params.get('city') || (cityByName.has(hashCity) ? hashCity : ''); if (linkedCity) setCity(linkedCity);
  updateMap(); updateInspector(); renderCompare(); renderTray(); applyFilters();
  if ('IntersectionObserver' in window) { const observer = new IntersectionObserver(entries => entries.forEach(entry => { if (entry.isIntersecting) entry.target.classList.add('is-revealed'); }), { threshold: .08 }); document.querySelectorAll('[data-reveal]').forEach(node => observer.observe(node)); }
})();
