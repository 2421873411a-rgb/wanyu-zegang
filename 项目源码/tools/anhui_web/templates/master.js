(() => {
  const data = window.productData || {};
  const jobs = data.jobs || {};
  const salary = data.salary || {};
  const cities = Array.isArray(jobs.cities) ? jobs.cities : [];
  const cityNames = cities.map((item) => String(item.city));
  const citySet = new Set(cityNames);
  const cityByName = new Map(cities.map((item) => [String(item.city), item]));
  const metrics = jobs.metrics || {};
  const examMetrics = metrics.exam || {};
  const allCities = Array.isArray(jobs.all_cities) ? jobs.all_cities : [];
  const ALL_EXAM_KEY = { '省考': '省考', '事业单位': '事业编', '国考': '国考' };
  const series = salary.series || {};
  const stages = Array.isArray(salary.stages) && salary.stages.length ? salary.stages : ['刚入职', '1年', '3年', '5年', '10年'];
  const validExams = new Set(['全部', ...Object.keys(examMetrics)]);
  const validTypes = new Set(Object.keys(series));
  const fallbackCity = citySet.has('合肥') ? '合肥' : cityNames[0];
  const query = new URLSearchParams(location.search);
  const motion = window.wanyuMotion || {};
  const threeYearAudit = data.threeYearAudit || {};
  const auditCycles = new Map((threeYearAudit.cycles || []).map((item) => [String(item.cycle), item]));
  const shortlistKey = 'wanyu.cityShortlist.v1';
  const formatNumber = (value, digits = 0) => Number(value || 0).toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits });
  const formatCompetition = (value) => { const numeric = Number(value || 0); return numeric > 0 ? `1:${(1 / numeric).toFixed(1)}` : '—'; };
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
  const readNumber = (value) => { const numeric = Number(value); return Number.isFinite(numeric) ? numeric : 0; };
  const hydrateCycleCompare = () => {
    document.querySelectorAll('[data-audit-value]').forEach((node) => {
      const [cycle, field] = String(node.dataset.auditValue || '').split(':');
      const item = auditCycles.get(cycle) || {};
      if (Object.prototype.hasOwnProperty.call(item, field)) node.textContent = formatNumber(item[field]);
    });
    document.querySelectorAll('[data-audit-status-total]').forEach((node) => {
      const key = node.dataset.auditStatusTotal;
      const total = [...auditCycles.values()].reduce((sum, item) => sum + readNumber((item.statuses || {})[key]), 0);
      node.textContent = formatNumber(total);
    });
    document.querySelectorAll('[data-audit-total-checks]').forEach((node) => {
      node.textContent = formatNumber((threeYearAudit.checks || {}).passed);
    });
    document.querySelectorAll('[data-audit-trend]').forEach((node) => {
      const [cycle, field] = String(node.dataset.auditTrend || '').split(':');
      const values = [...auditCycles.values()].map((item) => readNumber(item[field]));
      const max = Math.max(...values, 1);
      node.style.setProperty('--trend-pct', `${(readNumber((auditCycles.get(cycle) || {})[field]) / max) * 100}%`);
    });
  };
  const defaultType = validTypes.has('公务员') ? '公务员' : [...validTypes][0];
  let exam = validExams.has(query.get('exam')) ? query.get('exam') : '全部';
  let type = validTypes.has(query.get('type')) ? query.get('type') : defaultType;
  let stage = stages.includes(query.get('stage')) ? query.get('stage') : (stages.includes('3年') ? '3年' : stages[0]);
  let selected = citySet.has(query.get('city')) ? query.get('city') : fallbackCity;
  let caliber = query.get('caliber') === 'all' ? 'all' : query.get('caliber') === 'major' ? 'major' : 'archive';
  let majorName = String(query.get('major') || '').trim();
  const shortlist = new Set();

  const restoreShortlist = () => {
    try {
      const stored = JSON.parse(localStorage.getItem(shortlistKey) || '[]');
      if (Array.isArray(stored)) stored.filter((city) => citySet.has(String(city))).slice(0, 8).forEach((city) => shortlist.add(String(city)));
    } catch {}
  };
  const persistShortlist = () => { try { localStorage.setItem(shortlistKey, JSON.stringify([...shortlist])); } catch {} };
  const jobValueFor = (item, key) => {
    if (exam === '全部') return readNumber(item[key]);
    return readNumber(item.exam?.[exam]?.[key]);
  };
  const allTotals = () => {
    const key = exam === '全部' ? null : ALL_EXAM_KEY[exam];
    return allCities.reduce((acc, item) => {
      if (key) {
        const e = item.exam?.[key] || {};
        acc.jobs += readNumber(e.jobs); acc.recruits += readNumber(e.recruits);
      } else { acc.jobs += readNumber(item.jobs); acc.recruits += readNumber(item.recruits); }
      return acc;
    }, { jobs: 0, recruits: 0 });
  };
  const allRowsLib = () => { const am2 = (window.productData || {}).allMajors || {}; return Array.isArray(am2.rows) ? am2.rows : []; };
  const majorMatched = () => {
    const am = window.wanyuAllMatch;
    const key = exam === '全部' ? null : ALL_EXAM_KEY[exam];
    if (!am || !majorName) return allRowsLib().filter((r) => !key || r.exam === key);
    return allRowsLib().filter((r) => (!key || r.exam === key) && am.floorOk(r) && am.match(r, majorName));
  };
  const majorTotals = () => {
    const m = majorMatched();
    return { jobs: m.length, recruits: m.reduce((sum, r) => sum + readNumber(r.num), 0) };
  };
  const majorPerCity = () => {
    const map = {};
    majorMatched().forEach((r) => { const c = String(r.city); map[c] = map[c] || { jobs: 0, recruits: 0 }; map[c].jobs += 1; map[c].recruits += readNumber(r.num); });
    return map;
  };
  const competitionFor = (item) => exam === '全部' ? readNumber(item.ratio) : readNumber(item.competition?.[exam]?.ratio);
  const salaryFor = (city) => readNumber(series[type]?.[city]?.[stage]);
  const normalize = (value, values) => {
    const min = Math.min(...values);
    const max = Math.max(...values);
    if (!Number.isFinite(min) || !Number.isFinite(max) || max === min) return 50;
    return ((value - min) / (max - min)) * 100;
  };
  const rows = () => {
    const perCity = caliber === 'major' ? majorPerCity() : null;
    const base = cities.map((item) => ({
      city: String(item.city),
      jobs: caliber === 'major' ? readNumber((perCity[String(item.city)] || {}).jobs) : jobValueFor(item, 'jobs'),
      recruits: caliber === 'major' ? readNumber((perCity[String(item.city)] || {}).recruits) : jobValueFor(item, 'recruits'),
      ratio: competitionFor(item),
      salary: salaryFor(String(item.city)),
      sourceRank: readNumber(item.rank),
    }));
    const jobValues = base.map((row) => row.jobs);
    const salaryValues = base.map((row) => row.salary);
    return base.map((row) => ({ ...row, opportunityScore: normalize(row.jobs, jobValues), salaryScore: normalize(row.salary, salaryValues) }));
  };
  const rowFor = (city) => rows().find((row) => row.city === city) || rows()[0];
  const setText = (selector, value) => { const node = document.querySelector(selector); if (node) node.textContent = String(value); };
  const animateText = (selector, value, formatter = (next) => String(next)) => {
    const node = document.querySelector(selector);
    if (!node) return;
    if (motion.animateNumber) motion.animateNumber(node, Number(value || 0), { format: formatter, duration: 330 });
    else node.textContent = formatter(Number(value || 0));
  };
  const updateUrl = () => {
    const url = new URL(location.href);
    exam === '全部' ? url.searchParams.delete('exam') : url.searchParams.set('exam', exam);
    caliber === 'archive' ? url.searchParams.delete('caliber') : url.searchParams.set('caliber', caliber);
    caliber === 'major' && majorName ? url.searchParams.set('major', majorName) : url.searchParams.delete('major');
    type === defaultType ? url.searchParams.delete('type') : url.searchParams.set('type', type);
    stage === (stages.includes('3年') ? '3年' : stages[0]) ? url.searchParams.delete('stage') : url.searchParams.set('stage', stage);
    selected === fallbackCity ? url.searchParams.delete('city') : url.searchParams.set('city', selected);
    url.hash = location.hash || '#overview';
    history.replaceState({}, '', url);
  };
  const setControls = () => {
    const examNode = document.querySelector('#master-exam-filter'); if (examNode) examNode.value = exam;
    const typeNode = document.querySelector('#master-type-filter'); if (typeNode) typeNode.value = type;
    const cityNode = document.querySelector('#master-city-select'); if (cityNode) cityNode.value = selected;
document.querySelectorAll('[data-master-stage]').forEach((button) => { const active = button.dataset.masterStage === stage; button.classList.toggle('is-selected', active); button.setAttribute('aria-pressed', String(active)); });
document.querySelectorAll('[data-master-caliber]').forEach((button) => { const active = button.dataset.masterCaliber === caliber; button.classList.toggle('is-selected', active); button.setAttribute('aria-pressed', String(active)); });
const majorWrap = document.querySelector('#master-major-wrap');
if (majorWrap) majorWrap.hidden = caliber !== 'major';
const majorInputNode = document.querySelector('#master-major-input');
if (majorInputNode && document.activeElement !== majorInputNode) majorInputNode.value = majorName;
};
  const renderKpis = (dataRows) => {
    const examLabel = exam === '全部' ? '全部类别' : exam;
    if (caliber === 'all') {
      const totals = allTotals();
      animateText('#master-kpi-jobs', totals.jobs, (next) => formatNumber(next));
      animateText('#master-kpi-recruits', totals.recruits, (next) => formatNumber(next));
    } else if (caliber === 'major') {
      /* 专业匹配口径：全岗位库逐行合计（含省直），与岗位地图专业过滤同源 */
      const totals = majorTotals();
      animateText('#master-kpi-jobs', totals.jobs, (next) => formatNumber(next));
      animateText('#master-kpi-recruits', totals.recruits, (next) => formatNumber(next));
    } else {
      const totalJobs = dataRows.reduce((sum, row) => sum + row.jobs, 0);
      const totalRecruits = dataRows.reduce((sum, row) => sum + row.recruits, 0);
      animateText('#master-kpi-jobs', totalJobs, (next) => formatNumber(next));
      animateText('#master-kpi-recruits', totalRecruits, (next) => formatNumber(next));
    }
    const salaryValues = dataRows.map((row) => row.salary).filter((value) => value > 0);
    const salaryAverage = salaryValues.length ? salaryValues.reduce((sum, value) => sum + value, 0) / salaryValues.length : 0;
    animateText('#master-kpi-salary', salaryAverage, (next) => formatNumber(next, 1));
    if (caliber === 'major') {
      setText('.master-kpi--jobs small', `${examLabel} · 专业「${majorName || '未填'}」可报（本科及以上 · 含省直）`);
      setText('.master-kpi--recruits small', `${examLabel} · 专业「${majorName || '未填'}」可报（本科及以上 · 含省直）`);
      const jobsCard = document.querySelector('.master-kpi--jobs');
      const recruitsCard = document.querySelector('.master-kpi--recruits');
      if (jobsCard) jobsCard.title = '专业匹配口径：全岗位库（含省直）按条目级专业匹配 + 本科及以上；矩阵横轴为各市可报数（省直不计入 16 市）';
      if (recruitsCard) recruitsCard.title = '专业匹配口径：可报岗位的招录人数合计（含省直）；匹配规则与全岗位库、岗位地图一致';
    } else if (caliber === 'all') {
      setText('.master-kpi--jobs small', `${examLabel} · 全岗位库合计（含省直）`);
      setText('.master-kpi--recruits small', `${examLabel} · 全岗位库合计（含省直）`);
      const jobsCard = document.querySelector('.master-kpi--jobs');
      const recruitsCard = document.querySelector('.master-kpi--recruits');
      if (jobsCard) jobsCard.title = '全岗位库口径：省考官方表 3784 + 事业编联考全量 4345（华图职位库快照 2026-08-29）+ 国考 3；矩阵与城市画像仍为档案口径';
      if (recruitsCard) recruitsCard.title = '全岗位库口径：按市逐行合计招录人数；报名/成绩为快照值，随官方发布更新';
    } else {
      setText('.master-kpi--jobs small', `${examLabel} · 城市合计`);
      setText('.master-kpi--recruits small', `${examLabel} · 城市合计`);
      const jobsCard = document.querySelector('.master-kpi--jobs');
      const recruitsCard = document.querySelector('.master-kpi--recruits');
      if (jobsCard) jobsCard.title = '来源：106 张源表逐行合计，身份定向岗已核除';
      if (recruitsCard) recruitsCard.title = '来源：逐市岗位表招录人数合计（可报口径）';
    }
    setText('.master-kpi--salary small', `全省均值 · ${type}${stage}`);
    setText('#master-filter-summary', `${examLabel} · ${type} · ${stage} · ${caliber === 'all' ? '全岗位库' : caliber === 'major' ? `专业匹配「${majorName || '未填'}」` : '档案口径'}`);
    setText('#master-matrix-context', `${type} · ${stage}`);
  };
  const renderMatrix = (dataRows) => {
    const target = document.querySelector('#master-matrix-points');
    if (!target) return;
    const ordered = [...dataRows].sort((a, b) => b.opportunityScore - a.opportunityScore || b.salaryScore - a.salaryScore);
    target.innerHTML = dataRows.map((row) => {
      const x = 8 + row.opportunityScore * .84;
      const y = 92 - row.salaryScore * .84;
      const isTop = ordered.slice(0, 3).some((item) => item.city === row.city);
      const active = row.city === selected;
      return `<button type="button" class="master-dot${active ? ' is-active' : ''}${isTop ? ' is-top' : ''}${active || isTop ? ' is-labeled' : ''}" data-master-city="${escapeHtml(row.city)}" style="--dot-x:${x.toFixed(2)}%;--dot-y:${y.toFixed(2)}%" aria-label="查看${escapeHtml(row.city)}市，岗位${formatNumber(row.jobs)}，待遇${formatNumber(row.salary, 1)}万元/年" title="${escapeHtml(row.city)}市 · ${formatNumber(row.jobs)}岗 · ${formatNumber(row.salary, 1)}万元/年"><span>${escapeHtml(row.city)}</span></button>`;
    }).join('');
  };
  const renderProfile = (dataRows) => {
    const current = dataRows.find((row) => row.city === selected) || dataRows[0];
    if (!current) return;
    selected = current.city;
    const opportunityRank = [...dataRows].sort((a, b) => b.jobs - a.jobs || b.recruits - a.recruits).findIndex((row) => row.city === current.city) + 1;
    const salaryRank = [...dataRows].sort((a, b) => b.salary - a.salary).findIndex((row) => row.city === current.city) + 1;
    setText('#master-selected-city', `${current.city}市`);
    setText('#master-selection-status', `${exam === '全部' ? '全部类别' : exam} · ${type} · ${stage}`);
    setText('#master-city-name', `${current.city}市`);
    setText('#master-city-meta', `${exam === '全部' ? '全部类别' : exam} · ${type} · ${stage}`);
    setText('#master-profile-rank', `机会 #${String(opportunityRank).padStart(2, '0')} / 16`);
    const salaryLabel = current.salary > 0 ? `${formatNumber(current.salary, 1)} 万元/年` : '暂无待遇值';
    setText('#master-profile-summary', `${current.city}在当前口径下有 ${formatNumber(current.jobs)} 个岗位、${formatNumber(current.recruits)} 个招录名额；${type}${stage}待遇参考 ${salaryLabel}。机会位于全省第 ${opportunityRank}，待遇位于第 ${salaryRank}。`);
    animateText('#master-profile-jobs', current.jobs, (next) => formatNumber(next));
    animateText('#master-profile-recruits', current.recruits, (next) => formatNumber(next));
    setText('#master-profile-ratio', formatCompetition(current.ratio));
    animateText('#master-profile-salary', current.salary, (next) => formatNumber(next, 1));
    setText('#master-profile-score', `机会 ${Math.round(current.opportunityScore)} · 待遇 ${Math.round(current.salaryScore)}`);
    setText('#master-profile-score-note', `全省相对位置 · 机会第${opportunityRank} / 待遇第${salaryRank}`);
    const shortlistButton = document.querySelector('#master-shortlist-toggle');
    if (shortlistButton) { const added = shortlist.has(current.city); shortlistButton.innerHTML = added ? '移出城市短名单 <span>×</span>' : '加入城市短名单 <span>＋</span>'; shortlistButton.setAttribute('aria-pressed', String(added)); shortlistButton.classList.toggle('is-added', added); }
    const citySelect = document.querySelector('#master-city-select'); if (citySelect) citySelect.value = current.city;
  };
  const renderShortlist = (dataRows) => {
    const ordered = [...shortlist].map((city) => dataRows.find((row) => row.city === city)).filter(Boolean);
    const preview = document.querySelector('#master-shortlist-preview-list');
    const full = document.querySelector('#master-city-shortlist-list');
    const previewEmpty = '<div class="master-empty-state"><strong>还没有城市短名单</strong><span>点选城市画像里的“加入城市短名单”。</span></div>';
    const fullEmpty = '<div class="master-empty-state"><strong>还没有城市</strong><span>回到总览，点选城市后加入短名单。</span><button type="button" data-master-view="overview">去总览选择 →</button></div>';
    if (preview) preview.innerHTML = ordered.length ? `<div class="master-shortlist-items">${ordered.map((row) => `<article class="master-shortlist-item"><button type="button" class="master-shortlist-item__city" data-master-select-city="${escapeHtml(row.city)}"><strong>${escapeHtml(row.city)}市</strong><small>${formatNumber(row.jobs)}岗 · ${formatNumber(row.salary, 1)}万</small></button><button type="button" data-master-remove-city="${escapeHtml(row.city)}" aria-label="移除${escapeHtml(row.city)}市">×</button></article>`).join('')}</div>` : previewEmpty;
    if (full) full.innerHTML = ordered.length ? `<div class="master-city-shortlist-items">${ordered.map((row, index) => `<article class="master-city-shortlist-card"><span class="master-city-shortlist-card__index">${String(index + 1).padStart(2, '0')}</span><div class="master-city-shortlist-card__main"><button type="button" class="master-city-name" data-master-select-city="${escapeHtml(row.city)}">${escapeHtml(row.city)}市</button><small>${exam === '全部' ? '全部类别' : exam} · ${formatNumber(row.jobs)}岗 · ${formatNumber(row.recruits)}人 · ${formatNumber(row.salary, 1)}万/年</small></div><button type="button" data-master-remove-city="${escapeHtml(row.city)}">移除</button></article>`).join('')}</div>` : fullEmpty;
    setText('#master-shortlist-status', ordered.length ? `已保留 ${ordered.length} 座城市；选择状态只保存在当前浏览器。` : '城市短名单只保存在当前浏览器。');
  };
  const renderAll = () => {
    const dataRows = rows();
    setControls();
    renderKpis(dataRows);
    renderMatrix(dataRows);
    renderProfile(dataRows);
    renderShortlist(dataRows);
    /* 暴露当前口径给机会地图（product-jobs.js），专业匹配时地图同步重着色 */
    window.wanyuMasterCaliber = { caliber, major: majorName, exam };
    document.dispatchEvent(new CustomEvent('wanyu:caliber-changed'));
  };
  const selectCity = (city, write = true) => {
    if (!citySet.has(city)) return;
    selected = city;
    renderAll();
    if (write) updateUrl();
  };
  const toggleShortlist = () => {
    if (shortlist.has(selected)) shortlist.delete(selected); else shortlist.add(selected);
    persistShortlist();
    renderAll();
  };
  const activateNode = (node) => {
    if (!node) return;
    if (typeof node.click === 'function') node.click();
    else node.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
  };
  const syncLegacyView = (view) => {
    if (view === 'cycle_compare') hydrateCycleCompare();
    if (new Set(['jobs_dashboard', 'jobs_ranking', 'jobs_search', 'jobs_compare']).has(view)) {
      const examButton = [...document.querySelectorAll('#exam-filter [data-exam]')].find((button) => button.dataset.exam === exam);
      activateNode(examButton);
      const cityNode = document.querySelector(`.jobs-map__region[data-city="${CSS.escape(selected)}"]`);
      activateNode(cityNode);
      return;
    }
    if (new Set(['salary_dashboard', 'salary_ranking']).has(view)) {
      const typeButton = [...document.querySelectorAll('#employment-type [data-type]')].find((button) => button.dataset.type === type);
      activateNode(typeButton);
      const stageButton = [...document.querySelectorAll('#career-stage [data-stage]')].find((button) => button.dataset.stage === stage);
      activateNode(stageButton);
      const citySelect = document.querySelector('#salary-city-search');
      if (citySelect) { citySelect.value = selected; citySelect.dispatchEvent(new Event('change', { bubbles: true })); }
    }
  };
  const goView = (view) => {
    const url = new URL(location.href);
    if (view === 'jobs_dashboard' || view === 'jobs_ranking' || view === 'jobs_search' || view === 'jobs_compare') {
      selected === fallbackCity ? url.searchParams.delete('city') : url.searchParams.set('city', selected);
      exam === '全部' ? url.searchParams.delete('exam') : url.searchParams.set('exam', exam);
    }
    if (view === 'salary_dashboard' || view === 'salary_ranking') {
      selected === fallbackCity ? url.searchParams.delete('city') : url.searchParams.set('city', selected);
      type === defaultType ? url.searchParams.delete('type') : url.searchParams.set('type', type);
      stage === (stages.includes('3年') ? '3年' : stages[0]) ? url.searchParams.delete('stage') : url.searchParams.set('stage', stage);
    }
    url.hash = `#${view}`;
    history.replaceState({}, '', url);
    syncLegacyView(view);
    dispatchEvent(new HashChangeEvent('hashchange'));
  };
  const switchArchiveTab = (tab) => {
    document.querySelectorAll('[data-master-archive-tab]').forEach((button) => { const active = button.dataset.masterArchiveTab === tab; button.classList.toggle('is-selected', active); button.setAttribute('aria-selected', String(active)); });
    document.querySelectorAll('[data-master-archive-part]').forEach((part) => part.classList.toggle('is-active', part.dataset.masterArchivePart === tab));
  };
  const redirectArchiveAlias = () => { if (location.hash === '#jobs_archive' || location.hash === '#salary_archive') goView('archives'); };

  restoreShortlist();
  document.querySelector('#master-exam-filter')?.addEventListener('change', (event) => { exam = validExams.has(event.target.value) ? event.target.value : '全部'; renderAll(); updateUrl(); });
  document.querySelector('#master-type-filter')?.addEventListener('change', (event) => { type = validTypes.has(event.target.value) ? event.target.value : defaultType; renderAll(); updateUrl(); });
  document.querySelector('#master-city-select')?.addEventListener('change', (event) => selectCity(event.target.value));
  document.querySelectorAll('[data-master-stage]').forEach((button) => button.addEventListener('click', () => { stage = stages.includes(button.dataset.masterStage) ? button.dataset.masterStage : stage; renderAll(); updateUrl(); }));
document.querySelectorAll('[data-master-caliber]').forEach((button) => button.addEventListener('click', () => { caliber = button.dataset.masterCaliber === 'all' ? 'all' : button.dataset.masterCaliber === 'major' ? 'major' : 'archive'; renderAll(); updateUrl(); }));
const majorInput = document.querySelector('#master-major-input');
const applyMajorName = () => { majorName = String(majorInput.value || '').trim(); renderAll(); updateUrl(); };
let majorDebounce = 0;
majorInput?.addEventListener('change', applyMajorName);
majorInput?.addEventListener('input', () => { clearTimeout(majorDebounce); majorDebounce = setTimeout(applyMajorName, 300); });
majorInput?.addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); clearTimeout(majorDebounce); applyMajorName(); } });
const majorDatalist = document.querySelector('#master-major-options');
if (majorDatalist && window.wanyuAllMatch) { majorDatalist.innerHTML = [].concat(window.wanyuAllMatch.cats || [], window.wanyuAllMatch.majors || []).map((m) => `<option value="${String(m).replace(/"/g, '')}"></option>`).join(''); }
  document.querySelector('#master-shortlist-toggle')?.addEventListener('click', toggleShortlist);
  document.querySelector('#master-clear-shortlist')?.addEventListener('click', () => { shortlist.clear(); persistShortlist(); renderAll(); });
document.querySelectorAll('[data-view-link]').forEach((button) => button.addEventListener('click', () => syncLegacyView(button.dataset.viewLink)));
  document.querySelector('#master-matrix-points')?.addEventListener('click', (event) => { const button = event.target.closest('[data-master-city]'); if (button) selectCity(button.dataset.masterCity); });
document.addEventListener('click', (event) => {
const viewBtn = event.target.closest('[data-master-view]');
if (viewBtn) { goView(viewBtn.dataset.masterView); return; }
const remove = event.target.closest('[data-master-remove-city]');
    if (remove) { shortlist.delete(remove.dataset.masterRemoveCity); persistShortlist(); renderAll(); return; }
    const pick = event.target.closest('[data-master-select-city]');
    if (pick) { selectCity(pick.dataset.masterSelectCity); goView('overview'); }
    const archiveTab = event.target.closest('[data-master-archive-tab]');
    if (archiveTab) switchArchiveTab(archiveTab.dataset.masterArchiveTab);
  });
  addEventListener('hashchange', () => { syncLegacyView(location.hash.slice(1)); redirectArchiveAlias(); });
  /* —— 期望年薪下限：矩阵中未达标城市变暗，画像给出达标提示 —— */
  let expectSalary = 0;
  const applyExpect = () => {
    const out = document.querySelector('#master-expect-out');
    if (out) out.textContent = expectSalary > 0 ? expectSalary.toFixed(1).replace('.0', '') + ' 万' : '不限';
    document.querySelectorAll('.master-dot').forEach((dot) => {
      const salary = Number(series[type]?.[dot.dataset.masterCity]?.[stage] || 0);
      dot.classList.toggle('is-dim', expectSalary > 0 && salary < expectSalary);
    });
    const note = document.querySelector('#master-expect-note');
    if (note) {
      if (expectSalary <= 0) note.textContent = '设定期望线后，矩阵中未达标城市会变暗';
      else {
        const salary = Number(series[type]?.[selected]?.[stage] || 0);
        const passing = cityNames.filter((city) => Number(series[type]?.[city]?.[stage] || 0) >= expectSalary).length;
        note.textContent = (salary >= expectSalary ? `当前城市 ${salary.toFixed(1)} 万 ≥ 期望线 ✓` : `当前城市 ${salary.toFixed(1)} 万低于期望线 ✗`) + ` · 达标 ${passing}/16 城`;
      }
    }
  };
  document.querySelector('#master-expect')?.addEventListener('input', (event) => { expectSalary = Number(event.target.value) || 0; applyExpect(); });
  new MutationObserver(() => applyExpect()).observe(document.querySelector('#master-matrix-points') || document.body, { childList: true });

  setControls();
  renderAll();
  hydrateCycleCompare();
  applyExpect();
  redirectArchiveAlias();
})();
