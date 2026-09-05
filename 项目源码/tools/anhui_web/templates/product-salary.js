(() => {
  const data = window.productData || {};
  const salaryData = data.salary || data;
  const series = salaryData.series || {};
  const cities = salaryData.cities || [];
  const stages = salaryData.stages || [];
  const query = new URLSearchParams(location.search);
  const validTypes = new Set(Object.keys(series));
  const validStages = new Set(stages);
  const validCities = new Set(cities);
  const fallbackType = validTypes.has('公务员') ? '公务员' : [...validTypes][0];
  const fallbackStage = validStages.has('3年') ? '3年' : stages[0];
  const fallbackCity = validCities.has('合肥') ? '合肥' : cities[0];
  const motion = window.wanyuMotion || {};
  let type = validTypes.has(query.get('type')) ? query.get('type') : fallbackType;
  let stage = validStages.has(query.get('stage')) ? query.get('stage') : fallbackStage;
  let selected = validCities.has(query.get('city')) ? query.get('city') : fallbackCity;
  const inspector = () => document.querySelector('.salary-grid .inspector');
  const openMobileDrawer = () => inspector()?.classList.add('is-mobile-open');
  const closeMobileDrawer = () => inspector()?.classList.remove('is-mobile-open');
  const values = () => cities.map((city) => Number((series[type] || {})[city]?.[stage] || 0));
  const mean = () => {
    const nums = values().filter((value) => Number.isFinite(value) && value > 0);
    return nums.length ? nums.reduce((sum, value) => sum + value, 0) / nums.length : 0;
  };
  const showTooltip = (city) => {
    const value = Number(series[type]?.[city]?.[stage] || 0);
    const tooltip = document.querySelector('#salary-map-tooltip');
    if (tooltip) tooltip.textContent = city + ' · ' + type + ' · ' + stage + ' ' + value.toFixed(1) + ' 万元/年';
  };
  const previewCity = (city) => {
    if (!cities.includes(city)) return;
    document.querySelectorAll('.salary-node, .salary-map__region, .salary-map__hit-region').forEach((node) => node.classList.toggle('is-preview', node.dataset.city === city));
    showTooltip(city);
  };
  const clearPreview = () => document.querySelectorAll('.salary-node.is-preview, .salary-map__region.is-preview, .salary-map__hit-region.is-preview').forEach((node) => node.classList.remove('is-preview'));
  const updateFacts = (city, value) => {
    const average = mean();
    const context = document.querySelector('#salary-fact-context');
    if (context) context.textContent = type + ' · 入职' + stage;
    const cityNode = document.querySelector('#salary-fact-city');
    if (cityNode) cityNode.textContent = city;
    motion.animateNumber?.(document.querySelector('#salary-fact-value'), value, { format: (next) => Number(next).toFixed(1), duration: 420 });
    motion.animateNumber?.(document.querySelector('#salary-fact-average'), average, { format: (next) => Number(next).toFixed(1), duration: 420 });
    const note = document.querySelector('#salary-fact-note');
    if (note) note.textContent = '当前为' + type + ' · 入职' + stage + '的估算中位数';
  };
  const updateUrl = () => {
    const url = new URL(location.href);
    type === '公务员' ? url.searchParams.delete('type') : url.searchParams.set('type', type);
    stage === '3年' ? url.searchParams.delete('stage') : url.searchParams.set('stage', stage);
    selected === '合肥' ? url.searchParams.delete('city') : url.searchParams.set('city', selected);
    history.replaceState({}, '', url);
  };
  const selectCity = (city, reveal = false) => {
    if (!cities.includes(city)) return;
    selected = city;
    document.querySelectorAll('.salary-node, .salary-map__region, .salary-map__hit-region').forEach((node) => node.classList.toggle('is-selected', node.dataset.city === city));
    const value = Number(series[type]?.[city]?.[stage] || 0);
    const ranked = [...cities].sort((a, b) => Number(series[type]?.[b]?.[stage] || 0) - Number(series[type]?.[a]?.[stage] || 0));
    const average = mean();
    motion.transition?.(inspector(), 'is-changing', 300);
    document.querySelector('#salary-city').textContent = city + '市';
    motion.animateNumber?.(document.querySelector('#salary-value'), value, { format: (next) => Number(next).toFixed(1), duration: 420 });
    document.querySelector('#salary-rank').textContent = String(ranked.indexOf(city) + 1).padStart(2, '0') + ' / 16';
    document.querySelector('#salary-delta').textContent = average ? (value - average >= 0 ? '+' : '') + ((value - average) / average * 100).toFixed(1) + '%' : '—';
    document.querySelector('#salary-stage').textContent = type + ' · ' + stage;
    document.querySelector('#salary-caption').textContent = type + ' · ' + stage;
    const select = document.querySelector('#salary-city-search');
    if (select) select.value = city;
    const link = document.querySelector('#salary-dossier-link');
    link.href = '#salary_archive';
    link.textContent = '查看' + city + '待遇档案 →';
    showTooltip(city);
    updateFacts(city, value);
    motion.pulse?.(document.querySelector('.salary-node[data-city="' + CSS.escape(city) + '"]'));
    clearPreview();
    updateUrl();
    if (reveal) openMobileDrawer();
  };
  const render = () => {
    const nums = values().filter(Boolean);
    const min = Math.min(...nums);
    const max = Math.max(...nums);
    document.querySelectorAll('.salary-map__region').forEach((node) => {
      const city = node.dataset.city;
      const value = Number(series[type]?.[city]?.[stage] || 0);
      const t = max === min ? .6 : (value - min) / (max - min);
      node.style.fill = value ? 'rgba(' + Math.round(47 + t * 25) + ',' + Math.round(126 + t * 55) + ',' + Math.round(225 - t * 110) + ',' + (.18 + t * .65).toFixed(2) + ')' : 'rgba(213,225,239,.45)';
    });
    document.querySelectorAll('.salary-node__value').forEach((node) => {
      const city = node.closest('.salary-node')?.dataset.city;
      if (city) motion.animateNumber?.(node, Number(series[type]?.[city]?.[stage] || 0), { format: (next) => Number(next).toFixed(1), duration: 420 });
    });
    document.querySelectorAll('#employment-type [data-type]').forEach((button) => {
      const active = button.dataset.type === type;
      button.classList.toggle('is-selected', active);
      button.setAttribute('aria-pressed', String(active));
    });
    document.querySelectorAll('#career-stage [data-stage]').forEach((button) => {
      const active = button.dataset.stage === stage;
      button.classList.toggle('is-selected', active);
      button.setAttribute('aria-pressed', String(active));
    });
    selectCity(selected);
  };
  const transitionMap = () => motion.transition?.(document.querySelector('#salary-map')?.closest('.map-stage'), 'is-value-transitioning', 420);
  document.querySelectorAll('#employment-type [data-type]').forEach((button) => button.addEventListener('click', () => {
    transitionMap();
    type = button.dataset.type;
    render();
  }));
  document.querySelectorAll('#career-stage [data-stage]').forEach((button) => button.addEventListener('click', () => {
    transitionMap();
    stage = button.dataset.stage;
    render();
  }));
  document.querySelector('#salary-city-search')?.addEventListener('change', (event) => {
    if (event.target.value) selectCity(event.target.value, true);
  });
  document.querySelector('[data-inspector-close]')?.addEventListener('click', closeMobileDrawer);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeMobileDrawer();
  });
  document.querySelectorAll('.salary-node, .salary-map__region, .salary-map__hit-region').forEach((node) => {
    node.addEventListener('click', () => selectCity(node.dataset.city, true));
    node.addEventListener('mouseenter', () => previewCity(node.dataset.city));
    node.addEventListener('mouseleave', clearPreview);
    node.addEventListener('focus', () => previewCity(node.dataset.city));
    node.addEventListener('blur', clearPreview);
    node.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        selectCity(node.dataset.city, true);
      }
    });
  });
  render();
})();
