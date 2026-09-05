(() => {
  const data = window.productData || {};
  const jobsData = data.jobs || data;
  const cities = jobsData.cities || [];
  const metrics = jobsData.metrics || {};
  const query = new URLSearchParams(location.search);
  const labels = { jobs: ['岗位数', '岗'], recruits: ['招录人数', '人'], ratio: ['竞争比', '1:N'] };
  const metricButtons = [...document.querySelectorAll('[data-metric]')];
  const examButtons = [...document.querySelectorAll('[data-exam]')];
  const cityMap = Object.fromEntries(cities.map((item) => [item.city, item]));
  const validMetrics = new Set(Object.keys(labels));
  const validExams = new Set(['全部', ...Object.keys(metrics.exam || {})]);
  const validCities = new Set(cities.map((item) => item.city));
  const fallbackCity = validCities.has('合肥') ? '合肥' : cities[0]?.city;
  const motion = window.wanyuMotion || {};
  const ratioIsComparable = (item) => Boolean(item && (item.ratio_comparable === true || item.ratio_status === 'single_denominator'));
  let metric = validMetrics.has(query.get('metric')) ? query.get('metric') : 'jobs';
  let exam = validExams.has(query.get('exam')) ? query.get('exam') : '全部';
  let selected = validCities.has(query.get('city')) ? query.get('city') : fallbackCity;
  const metricFor = (item) => {
    if (!item) return 0;
    if (majorAgg) {
      const row = majorAgg[item.city] || { jobs: 0, recruits: 0 };
      return metric === 'ratio' ? 0 : Number(metric === 'recruits' ? row.recruits : row.jobs);
    }
    if (exam === '全部') return metric === 'ratio' ? Number(ratioIsComparable(item) ? item.ratio || 0 : 0) : Number(item[metric] || 0);
    const row = (item.exam || {})[exam] || { jobs: 0, recruits: 0 };
    const competition = (item.competition || {})[exam] || {};
    return metric === 'ratio' ? Number(ratioIsComparable(competition) ? competition.ratio || 0 : 0) : Number(row[metric] || 0);
  };
  /* —— 总览“按专业匹配”口径联动：按市重算可报岗位/招录人数（本站考试类别筛选可叠加） —— */
  let majorAgg = null;
  const majorAggFor = () => {
    const mc = window.wanyuMasterCaliber || {};
    if (mc.caliber !== 'major' || !mc.major) return null;
    const am = window.wanyuAllMatch;
    if (!am) return null;
    const key = exam === '全部' ? null : ({ '省考': '省考', '事业单位': '事业编', '国考': '国考' })[exam];
    const agg = {};
    const rows2 = ((window.productData || {}).allMajors || {}).rows || [];
    rows2.forEach((r) => {
      if (key && r.exam !== key) return;
      if (!am.floorOk(r) || !am.match(r, mc.major)) return;
      const c = String(r.city);
      agg[c] = agg[c] || { jobs: 0, recruits: 0 };
      agg[c].jobs += 1;
      agg[c].recruits += Number(r.num || 0);
    });
    return agg;
  };
  document.addEventListener('wanyu:caliber-changed', () => { majorAgg = majorAggFor(); render(); });
  const competitionFor = (item) => exam === '全部'
    ? (ratioIsComparable(item) ? Number(item.ratio || 0) : 0)
    : (ratioIsComparable(item.competition?.[exam]) ? Number(item.competition?.[exam]?.ratio || 0) : 0);
  const format = (value, key) => { const numeric = Number(value || 0); return key === 'ratio' ? (numeric > 0 ? `1:${(1 / numeric).toFixed(1)}` : '—') : numeric.toLocaleString('en-US'); };
  const display = (value, key) => key === 'ratio' ? format(value, key) : `${format(value, key)} ${labels[key][1]}`;
  const average = () => { const values = cities.map(metricFor).filter((value) => Number.isFinite(value)); return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0; };
  const showTooltip = (city) => { const item = cityMap[city]; if (!item) return; const value = metricFor(item); const tooltip = document.querySelector('#jobs-map-tooltip'); if (tooltip) tooltip.textContent = `${city} · ${labels[metric][0]} ${display(value, metric)}`; };
  const previewCity = (city) => {
    if (!cityMap[city]) return;
    document.querySelectorAll('.jobs-map__region, .jobs-map__label').forEach((node) => node.classList.toggle('is-preview', node.dataset.city === city));
    showTooltip(city);
  };
  const clearPreview = () => document.querySelectorAll('.jobs-map__region.is-preview, .jobs-map__label.is-preview').forEach((node) => node.classList.remove('is-preview'));
  const openMobileDrawer = () => document.querySelector('#jobs-inspector')?.classList.add('is-mobile-open');
  const closeMobileDrawer = () => document.querySelector('#jobs-inspector')?.classList.remove('is-mobile-open');
  const decisionPresets = {
    steady: { label: '稳妥参考', weights: { opportunity: 20, recruits: 25, competition: 55 } },
    balanced: { label: '平衡参考', weights: { opportunity: 35, recruits: 35, competition: 30 } },
    opportunity: { label: '机会优先', weights: { opportunity: 50, recruits: 35, competition: 15 } },
  };
  let decisionPreset = 'balanced';
  const decisionState = { opportunity: 35, recruits: 35, competition: 30 };
  const decisionValueFor = (item) => {
    if (majorAgg) {
      const aggRow = majorAgg[item.city] || { jobs: 0, recruits: 0 };
      return { city: String(item.city), jobs: aggRow.jobs, recruits: aggRow.recruits, ratio: 0 };
    }
    const row = exam === '全部' ? item : ((item.exam || {})[exam] || {});
    const competition = competitionFor(item);
    return { city: String(item.city), jobs: Number(row.jobs ?? item.jobs ?? 0), recruits: Number(row.recruits ?? item.recruits ?? 0), ratio: competition };
  };
  const decisionRank = () => {
    const rows = cities.map(decisionValueFor);
    const range = (key) => {
      const values = rows.map((row) => row[key]);
      return { min: Math.min(...values), max: Math.max(...values) };
    };
    const jobsRange = range('jobs'); const recruitsRange = range('recruits'); const ratioRange = range('ratio');
    const normalize = (value, bounds) => bounds.max === bounds.min ? 100 : ((value - bounds.min) / (bounds.max - bounds.min)) * 100;
    const total = Math.max(Object.values(decisionState).reduce((sum, value) => sum + Number(value || 0), 0), 1);
    return rows.map((row) => {
      const scores = { opportunity: normalize(row.jobs, jobsRange), recruits: normalize(row.recruits, recruitsRange), competition: normalize(row.ratio, ratioRange) };
      const score = (scores.opportunity * decisionState.opportunity + scores.recruits * decisionState.recruits + scores.competition * decisionState.competition) / total;
      return { ...row, scores, score };
    }).sort((a, b) => b.score - a.score || b.jobs - a.jobs || b.recruits - a.recruits || a.city.localeCompare(b.city, 'zh-CN'));
  };
  const renderDecision = () => {
    const ranked = decisionRank();
    const top = ranked[0];
    if (!top) return;
    const total = Math.max(Object.values(decisionState).reduce((sum, value) => sum + Number(value || 0), 0), 1);
    const context = document.querySelector('#decision-context');
    if (context) context.textContent = `${exam === '全部' ? '全部类别' : exam} · ${cities.length} 座城市`;
    const presetLabel = decisionPresets[decisionPreset]?.label || '自定义参考';
    document.querySelector('#decision-strategy-label')?.replaceChildren(document.createTextNode(presetLabel));
    const topCity = document.querySelector('#decision-top-city'); if (topCity) topCity.textContent = `${top.city}市`;
    const topScore = document.querySelector('#decision-top-score'); if (topScore) topScore.textContent = `综合得分 ${top.score.toFixed(1)} / 100`;
    const topReason = document.querySelector('#decision-top-reason');
    if (topReason) topReason.textContent = `${presetLabel}：岗位 ${format(top.jobs, 'jobs')}、招录 ${format(top.recruits, 'recruits')}，竞争比 ${format(top.ratio, 'ratio')}；低竞争权重 ${Math.round(Number(decisionState.competition || 0) / total * 100)}%。`;
    const caption = document.querySelector('#decision-result-caption');
    if (caption) caption.textContent = `按${exam === '全部' ? '全部类别' : exam}计算 · 岗位 ${Math.round(Number(decisionState.opportunity || 0) / total * 100)}% · 招录 ${Math.round(Number(decisionState.recruits || 0) / total * 100)}% · 低竞争 ${Math.round(Number(decisionState.competition || 0) / total * 100)}%`;
    document.querySelectorAll('[data-decision-preset]').forEach((button) => { const active = button.dataset.decisionPreset === decisionPreset; button.classList.toggle('is-selected', active); button.setAttribute('aria-selected', String(active)); });
    document.querySelectorAll('[data-decision-weight]').forEach((input) => { const key = input.dataset.decisionWeight; input.value = String(decisionState[key]); });
    Object.entries(decisionState).forEach(([key, value]) => { const output = document.querySelector(`#decision-${key}-output`); if (output) output.textContent = String(value); });
    const weightTotal = document.querySelector('#decision-weight-total'); if (weightTotal) weightTotal.textContent = String(Object.values(decisionState).reduce((sum, value) => sum + Number(value || 0), 0));
    const list = document.querySelector('#decision-list');
    if (list) {
      const maxScore = Math.max(top.score, 1);
      list.innerHTML = ranked.slice(0, 3).map((row, index) => `<button type="button" class="decision-city-card" data-decision-city="${row.city}" aria-label="查看${row.city}市决策详情"><span class="decision-card__rank">${String(index + 1).padStart(2, '0')}</span><span class="decision-card__main"><strong>${row.city}市</strong><small>综合得分 ${row.score.toFixed(1)} · 岗位 ${format(row.jobs, 'jobs')}</small><span class="decision-card__bar"><i style="--decision-score:${Math.max(12, row.score / maxScore * 100)}%"></i></span><span class="decision-card__facts"><em>${format(row.jobs, 'jobs')} 岗</em><em>${format(row.recruits, 'recruits')} 人</em><em>${format(row.ratio, 'ratio')}</em></span></span><span class="decision-card__arrow" aria-hidden="true">→</span></button>`).join('');
    }
    document.body.dataset.decisionPreset = decisionPreset;
  };
  const updateFacts = (city, value) => {
    const avg = average();
    motion.animateNumber?.(document.querySelector('#jobs-fact-value'), value, { format: (next) => format(next, metric), duration: 360 });
    motion.animateNumber?.(document.querySelector('#jobs-fact-average'), avg, { format: (next) => format(next, metric), duration: 360 });
    const cityNode = document.querySelector('#jobs-fact-city'); if (cityNode) cityNode.textContent = city;
    const unitNode = document.querySelector('#jobs-fact-unit'); if (unitNode) unitNode.textContent = labels[metric][1];
    const avgUnit = document.querySelector('#jobs-fact-average-unit'); if (avgUnit) avgUnit.textContent = labels[metric][1];
    const context = document.querySelector('#jobs-fact-context'); if (context) context.textContent = `${city} · ${exam}`;
    const note = document.querySelector('#jobs-fact-note'); if (note) note.textContent = metric === 'ratio' ? '竞争比仅在同一分母且覆盖完整时呈现；报名、参考、达线和进面人数不混合。' : `${labels[metric][0]}已同步到地图与排名`;
  };
  const setUrl = () => { const url = new URL(location.href); url.searchParams.set('metric', metric); exam === '全部' ? url.searchParams.delete('exam') : url.searchParams.set('exam', exam); selected === '合肥' ? url.searchParams.delete('city') : url.searchParams.set('city', selected); history.replaceState({}, '', url); };
  const selectCity = (city) => {
    if (!cityMap[city]) return;
    selected = city;
    document.querySelectorAll('.jobs-map__region').forEach((node) => { const active = node.dataset.city === city; node.setAttribute('aria-pressed', String(active)); node.classList.toggle('is-selected', active); });
    document.querySelectorAll('.jobs-map__label').forEach((node) => node.classList.toggle('is-selected', node.dataset.city === city));
    const item = cityMap[city];
    const value = metricFor(item);
    const aggRow = majorAgg ? (majorAgg[item.city] || { jobs: 0, recruits: 0 }) : null;
    motion.transition?.(document.querySelector('#jobs-inspector'), 'is-changing', 300);
    const inspectorCity = document.querySelector('#inspector-city'); if (inspectorCity) inspectorCity.textContent = `${city}市`;
    motion.animateNumber?.(document.querySelector('#inspector-value'), value, { format: (next) => format(next, metric), duration: 360 });
    const inspectorUnit = document.querySelector('#inspector-unit'); if (inspectorUnit) inspectorUnit.textContent = labels[metric][1];
    motion.animateNumber?.(document.querySelector('#inspector-recruits'), aggRow ? aggRow.recruits : Number(item.recruits), { format: (next) => `${Number(next).toLocaleString('en-US')} 人`, duration: 360 });
    motion.animateNumber?.(document.querySelector('#inspector-ratio'), aggRow ? 0 : competitionFor(item), { format: (next) => format(next, 'ratio'), duration: 360 });
    const ranked = [...cities].sort((a, b) => metricFor(b) - metricFor(a));
    const rankNode = document.querySelector('#inspector-rank'); if (rankNode) rankNode.textContent = `${String(ranked.findIndex((row) => row.city === city) + 1).padStart(2, '0')} / 16`;
    const link = document.querySelector('#inspector-link'); if (link) { link.href = '#jobs_archive'; link.textContent = `查看${city}岗位档案 →`; }
    const selectionNode = document.querySelector('#jobs-selection'); if (selectionNode) selectionNode.textContent = `${city}市 · ${exam}`;
    const toast = document.querySelector('#map-toast'); if (toast) toast.textContent = `${city} · ${labels[metric][0]} ${display(value, metric)}`;
    showTooltip(city); updateFacts(city, value);
    motion.pulse?.(document.querySelector(`.jobs-map__region[data-city="${CSS.escape(city)}"]`));
    motion.pulse?.(document.querySelector(`.jobs-map__label[data-city="${CSS.escape(city)}"]`));
    document.body.dataset.jobsMetric = metric;
    clearPreview();
    setUrl();
  };
  const render = () => {
    majorAgg = majorAggFor();
    const values = cities.map(metricFor).filter((value) => value > 0);
    const min = Math.min(...values), max = Math.max(...values);
    document.querySelectorAll('.jobs-map__region').forEach((node) => {
      const value = metricFor(cityMap[node.dataset.city]);
      const t = max === min ? .7 : (value - min) / (max - min);
      node.style.fill = value ? `rgba(${Math.round(44 + t * 20)}, ${Math.round(125 + t * 60)}, ${Math.round(224 - t * 125)}, ${(.18 + t * .65).toFixed(2)})` : 'rgba(213,225,239,.45)';
      const label = document.querySelector(`.jobs-map__label[data-city="${CSS.escape(node.dataset.city)}"] .jobs-map__value`);
      if (label) motion.animateNumber?.(label, value, { format: (next) => display(next, metric), duration: 420 });
      const title = node.querySelector('title'); if (title) title.textContent = `${node.dataset.city} · ${labels[metric][0]} ${display(value, metric)}`;
    });
    metricButtons.forEach((button) => { const active = button.dataset.metric === metric; button.classList.toggle('is-selected', active); button.setAttribute('aria-pressed', String(active)); });
    examButtons.forEach((button) => { const active = button.dataset.exam === exam; button.classList.toggle('is-selected', active); button.setAttribute('aria-pressed', String(active)); });
    const mc = window.wanyuMasterCaliber || {};
    const majorSuffix = mc.caliber === 'major' && mc.major ? ` · 专业「${mc.major}」可报` : '';
    /* v9.9.3：历史周期页无主站地图 DOM（#map-caption 缺失），此前的裸写入会抛 TypeError 并中断整页脚本 */
    const captionNode = document.querySelector('#map-caption'); if (captionNode) captionNode.textContent = `当前显示：${labels[metric][0]}${exam === '全部' ? '' : ` · ${exam}`}${majorSuffix}`;
    document.body.dataset.jobsMetric = metric;
    selectCity(selected);
    renderDecision();
  };
  const transitionMap = () => motion.transition?.(document.querySelector('#jobs-observatory .map-stage'), 'is-metric-transitioning', 420);
  metricButtons.forEach((button) => button.addEventListener('click', () => { transitionMap(); metric = button.dataset.metric; render(); }));
  examButtons.forEach((button) => button.addEventListener('click', () => { transitionMap(); exam = button.dataset.exam; render(); }));
  document.querySelectorAll('[data-decision-preset]').forEach((button) => button.addEventListener('click', () => { decisionPreset = button.dataset.decisionPreset; Object.assign(decisionState, decisionPresets[decisionPreset].weights); renderDecision(); }));
  document.querySelectorAll('[data-decision-weight]').forEach((input) => input.addEventListener('input', () => { decisionPreset = 'custom'; decisionState[input.dataset.decisionWeight] = Number(input.value || 0); renderDecision(); }));
  document.querySelector('#decision-list')?.addEventListener('click', (event) => { const card = event.target.closest('[data-decision-city]'); if (!card) return; selectCity(card.dataset.decisionCity); openMobileDrawer(); });
  document.querySelector('[data-inspector-close]')?.addEventListener('click', closeMobileDrawer);
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeMobileDrawer(); });
  document.querySelectorAll('.jobs-map__region, .jobs-map__label').forEach((node) => { node.addEventListener('click', () => { selectCity(node.dataset.city); openMobileDrawer(); }); node.addEventListener('mouseenter', () => previewCity(node.dataset.city)); node.addEventListener('mouseleave', clearPreview); node.addEventListener('focus', () => previewCity(node.dataset.city)); node.addEventListener('blur', clearPreview); node.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectCity(node.dataset.city); openMobileDrawer(); } }); });
  document.querySelector('#reset-jobs')?.addEventListener('click', () => { metric = 'jobs'; exam = '全部'; selected = '合肥'; render(); });
  render();
})();
