(() => {
  document.documentElement.classList.add('motion-ready');

  const dataNode = document.querySelector('#page-data');
  const pageData = JSON.parse(dataNode.textContent);
  const series = pageData.series;
  const stages = pageData.stages;
  const typeButtons = [...document.querySelectorAll('#employment-type button')];
  const stageSelect = document.querySelector('#career-stage');
  const stageButtons = [...document.querySelectorAll('[data-stage-button]')];
  const citySelect = document.querySelector('#salary-city-search');
  const mapNodes = [...document.querySelectorAll('.salary-node')];
  const mapRegions = [...document.querySelectorAll('.salary-map__region')];
  const mapCityChips = [...document.querySelectorAll('[data-map-city]')];
  const ridgeRows = [...document.querySelectorAll('.ridge-row')];
  const stageLabels = [...document.querySelectorAll('.stage-legend [data-stage]')];
  const salaryMap = document.querySelector('#salary-map');
  const inspector = document.querySelector('#salary-map-readout');
  const inspectorCity = document.querySelector('#salary-map-city');
  const inspectorNumber = document.querySelector('#salary-map-number');
  const inspectorValue = document.querySelector('#salary-map-value');
  const inspectorContext = document.querySelector('#salary-map-context');
  const inspectorRank = document.querySelector('#inspector-rank');
  const inspectorDelta = document.querySelector('#inspector-delta');
  const inspectorStage = document.querySelector('#inspector-stage');
  const openDossier = document.querySelector('#open-city-dossier');
  const viewLabel = document.querySelector('#salary-view-label');
  const rankingTitle = document.querySelector('#ranking-title');
  const heatMin = document.querySelector('#heat-min');
  const heatMax = document.querySelector('#heat-max');
  const comparisonTopCity = document.querySelector('#comparison-topcity');
  const comparisonSpread = document.querySelector('#comparison-spread');
  const comparisonAverage = document.querySelector('#comparison-average');
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const palette = ['#dce9f2', '#c5e0e7', '#9ed2da', '#70c0c4', '#43aaa7', '#2b908e', '#f0b95c', '#ea6b57'];
  let currentType = '公务员';
  let selectedCity = '合肥';
  const linkedCity = new URLSearchParams(location.search).get('city');
  if (linkedCity && series['公务员']?.[linkedCity]) selectedCity = linkedCity;

  const validNumbers = values => values.filter(value => typeof value === 'number' && Number.isFinite(value));

  function heatColor(value, minimum, maximum) {
    if (typeof value !== 'number') return '#c8d3d7';
    const span = Math.max(maximum - minimum, 0.001);
    const ratio = Math.max(0, Math.min(1, (value - minimum) / span));
    return palette[Math.min(palette.length - 1, Math.floor(ratio * palette.length))];
  }

  function labelForStage(stage) {
    return stage === '刚入职' ? '刚入职' : `入职${stage}`;
  }

  function formatValue(value) {
    return typeof value === 'number' ? `${value.toFixed(1)}万元/年` : '暂无数据';
  }

  function currentEntries() {
    const stage = stageSelect.value;
    return Object.entries(series[currentType])
      .map(([city, values]) => ({ city, value: values[stage] }))
      .filter(item => typeof item.value === 'number')
      .sort((a, b) => b.value - a.value);
  }

  function animateNumber(node, nextValue) {
    if (!node || typeof nextValue !== 'number') return;
    const previous = Number.parseFloat(node.textContent);
    if (reduceMotion || !Number.isFinite(previous) || Math.abs(previous - nextValue) < 0.01) {
      node.textContent = nextValue.toFixed(1);
      return;
    }
    const startedAt = performance.now();
    const duration = 420;
    const tick = now => {
      const progress = Math.min(1, (now - startedAt) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      node.textContent = (previous + (nextValue - previous) * eased).toFixed(1);
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  function inspectorStats(city) {
    const entries = currentEntries();
    const cityEntry = entries.find(item => item.city === city);
    const average = entries.reduce((sum, item) => sum + item.value, 0) / Math.max(entries.length, 1);
    const rank = Math.max(1, entries.findIndex(item => item.city === city) + 1);
    const delta = cityEntry && average ? ((cityEntry.value - average) / average) * 100 : 0;
    return { entries, cityEntry, average, rank, delta };
  }

  function updateInspector(city = selectedCity, animate = true) {
    const stage = stageSelect.value;
    const cityValues = series[currentType]?.[city];
    if (!cityValues) return;
    const value = cityValues[stage];
    const stats = inspectorStats(city);
    inspectorCity.textContent = city;
    animateNumber(inspectorNumber, value);
    inspectorContext.textContent = `${currentType} · ${labelForStage(stage)}`;
    inspectorValue.textContent = `${city}，${currentType}${labelForStage(stage)}，${formatValue(value)}`;
    inspectorRank.textContent = `${stats.rank} / ${stats.entries.length}`;
    inspectorDelta.textContent = `${stats.delta >= 0 ? '+' : ''}${stats.delta.toFixed(1)}%`;
    inspectorStage.textContent = `第 ${stages.indexOf(stage) + 1} 档`;
    if (animate && inspector) {
      inspector.classList.remove('is-changing');
      void inspector.offsetWidth;
      inspector.classList.add('is-changing');
    }
  }

  function previewCity(city) {
    updateInspector(city, false);
    mapRegions.forEach(region => region.classList.toggle('is-preview', region.dataset.city === city && city !== selectedCity));
  }

  function clearPreview() {
    mapRegions.forEach(region => region.classList.remove('is-preview'));
    updateInspector(selectedCity, false);
  }

  function animateMapRefresh() {
    if (!salaryMap) return;
    salaryMap.classList.remove('is-refreshing');
    void salaryMap.getBoundingClientRect().width;
    salaryMap.classList.add('is-refreshing');
  }

  function plotRidge(row, values, selectedStage, minimum, maximum) {
    const numeric = stages.map(stage => values[stage]);
    const span = Math.max(maximum - minimum, 0.001);
    const points = numeric.map((value, index) => {
      const x = 8 + index * 21;
      const y = typeof value === 'number' ? 23 - ((value - minimum) / span) * 17 : 23;
      return { x, y, value, selected: stages[index] === selectedStage };
    });
    const line = points.map(point => `${point.x},${point.y.toFixed(2)}`).join(' ');
    const area = `8,25 ${line} 92,25`;
    const circles = points.map(point => `<circle class="ridge-point${point.selected ? ' is-selected' : ''}" cx="${point.x}" cy="${point.y.toFixed(2)}" r="${point.selected ? 2.15 : 1.45}"></circle>`).join('');
    row.querySelector('.ridge-plot').innerHTML = `<polygon class="ridge-area" points="${area}"></polygon><polyline class="ridge-line" points="${line}"></polyline>${circles}`;
  }

  function reorderRows(stage, citySeries) {
    const firstPositions = new Map(ridgeRows.map(row => [row, row.getBoundingClientRect().top]));
    const ranked = [...ridgeRows].sort((a, b) => {
      const aValue = citySeries[a.dataset.city][stage];
      const bValue = citySeries[b.dataset.city][stage];
      return (bValue ?? -Infinity) - (aValue ?? -Infinity);
    });
    const numericValues = validNumbers(ranked.map(row => citySeries[row.dataset.city][stage]));
    const average = numericValues.reduce((sum, value) => sum + value, 0) / Math.max(numericValues.length, 1);
    ranked.forEach((row, index) => {
      row.style.order = index;
      row.querySelector('[data-rank]').textContent = String(index + 1).padStart(2, '0');
      const value = citySeries[row.dataset.city][stage];
      row.querySelector('[data-ridge-value]').textContent = typeof value === 'number' ? value.toFixed(1) : '—';
      const delta = typeof value === 'number' && average ? ((value - average) / average) * 100 : 0;
      row.querySelector('[data-ridge-delta]').textContent = `${delta >= 0 ? '+' : ''}${delta.toFixed(1)}% 省均值`;
    });
    if (!reduceMotion) {
      requestAnimationFrame(() => {
        ranked.forEach(row => {
          const deltaY = firstPositions.get(row) - row.getBoundingClientRect().top;
          if (Math.abs(deltaY) > 1) {
            row.animate(
              [{ transform: `translateY(${deltaY}px)` }, { transform: 'translateY(0)' }],
              { duration: 520, easing: 'cubic-bezier(.2,.72,.2,1)' },
            );
          }
        });
      });
    }
    const spread = numericValues.length ? Math.max(...numericValues) - Math.min(...numericValues) : 0;
    comparisonTopCity.textContent = ranked[0]?.dataset.city || '—';
    comparisonSpread.textContent = `${spread.toFixed(1)} 万`;
    comparisonAverage.textContent = `${average.toFixed(1)} 万`;
  }

  function renderSalaryView(type, stage) {
    currentType = type;
    const citySeries = series[type];
    const currentValues = validNumbers(Object.values(citySeries).map(values => values[stage]));
    const allValues = validNumbers(Object.values(citySeries).flatMap(values => stages.map(item => values[item])));
    typeButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.type === type)));
    stageButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.stageButton === stage)));
    stageLabels.forEach(label => label.classList.toggle('is-selected', label.dataset.stage === stage));
    viewLabel.textContent = `${type} · ${labelForStage(stage)}`;
    rankingTitle.textContent = `${type} · ${labelForStage(stage)}`;
    if (!currentValues.length) {
      heatMin.textContent = '—';
      heatMax.textContent = '—';
      return;
    }
    const minimum = Math.min(...currentValues);
    const maximum = Math.max(...currentValues);
    const allMinimum = Math.min(...allValues);
    const allMaximum = Math.max(...allValues);
    heatMin.textContent = minimum.toFixed(1);
    heatMax.textContent = maximum.toFixed(1);

    mapRegions.forEach(region => {
      const value = citySeries[region.dataset.city][stage];
      region.style.setProperty('--heat', heatColor(value, minimum, maximum));
    });
    mapNodes.forEach(node => {
      const city = node.dataset.city;
      const value = citySeries[city][stage];
      node.querySelector('.salary-node__value').textContent = typeof value === 'number' ? value.toFixed(1) : '—';
      const valueLabel = typeof value === 'number' ? `${value.toFixed(1)}万元` : '暂无';
      node.setAttribute('aria-label', `${city}，${type}${labelForStage(stage)}估算中位数${valueLabel}`);
      const title = node.querySelector('title');
      if (title) title.textContent = `${city} · ${type}${labelForStage(stage)} · ${valueLabel}`;
    });
    ridgeRows.forEach(row => plotRidge(row, citySeries[row.dataset.city], stage, allMinimum, allMaximum));
    reorderRows(stage, citySeries);
    updateInspector(selectedCity);
    animateMapRefresh();
  }

  function selectCity(city, options = {}) {
    if (!city || !series[currentType]?.[city]) return;
    selectedCity = city;
    mapNodes.forEach(node => node.classList.toggle('is-active', node.dataset.city === city));
    mapRegions.forEach(region => region.classList.toggle('is-active', region.dataset.city === city));
    mapCityChips.forEach(chip => chip.classList.toggle('is-active', chip.dataset.mapCity === city));
    ridgeRows.forEach(row => row.classList.toggle('is-active', row.dataset.city === city));
    if (citySelect) citySelect.value = city;
    updateInspector(city);
    if (options.scrollToDossier) {
      document.querySelector(`#salary-city-${CSS.escape(city)}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  function setupReveals() {
    const items = [...document.querySelectorAll('[data-reveal]')];
    if (reduceMotion || !('IntersectionObserver' in window)) {
      items.forEach(item => item.classList.add('is-visible'));
      return;
    }
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.02, rootMargin: '0px 0px -2% 0px' });
    items.forEach(item => observer.observe(item));
  }

  function setupSectionTracking() {
    if (!('IntersectionObserver' in window)) return;
    const navLinks = [...document.querySelectorAll('.salary-nav a')];
    const sectionById = new Map(navLinks.map(link => [link.getAttribute('href').slice(1), link]));
    const sectionObserver = new IntersectionObserver(entries => {
      const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      navLinks.forEach(link => link.removeAttribute('aria-current'));
      sectionById.get(visible.target.id)?.setAttribute('aria-current', 'true');
    }, { rootMargin: '-18% 0px -68% 0px', threshold: [0.01, 0.2] });
    sectionById.forEach((link, id) => {
      const section = document.getElementById(id);
      if (section) sectionObserver.observe(section);
    });

    const dossierLinks = [...document.querySelectorAll('[data-dossier-link]')];
    const dossierObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        dossierLinks.forEach(link => link.removeAttribute('aria-current'));
        document.querySelector(`[data-dossier-link="${CSS.escape(entry.target.dataset.city)}"]`)?.setAttribute('aria-current', 'true');
      });
    }, { rootMargin: '-18% 0px -72% 0px', threshold: 0.01 });
    document.querySelectorAll('.city-dossier').forEach(section => dossierObserver.observe(section));
  }

  typeButtons.forEach(button => button.addEventListener('click', () => renderSalaryView(button.dataset.type, stageSelect.value)));
  stageButtons.forEach(button => button.addEventListener('click', () => {
    stageSelect.value = button.dataset.stageButton;
    renderSalaryView(currentType, stageSelect.value);
  }));
  stageSelect.addEventListener('change', () => renderSalaryView(currentType, stageSelect.value));
  citySelect.addEventListener('change', () => selectCity(citySelect.value));
  mapCityChips.forEach(chip => chip.addEventListener('click', () => selectCity(chip.dataset.mapCity)));
  mapNodes.forEach(node => {
    node.addEventListener('click', () => selectCity(node.dataset.city));
    node.addEventListener('pointerenter', () => previewCity(node.dataset.city));
    node.addEventListener('pointerleave', clearPreview);
    node.addEventListener('focus', () => previewCity(node.dataset.city));
    node.addEventListener('blur', clearPreview);
    node.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        selectCity(node.dataset.city);
      }
    });
  });
  ridgeRows.forEach(row => {
    row.querySelector('button').addEventListener('click', () => selectCity(row.dataset.city));
    row.addEventListener('pointerenter', () => previewCity(row.dataset.city));
    row.addEventListener('pointerleave', clearPreview);
  });
  openDossier.addEventListener('click', () => selectCity(selectedCity, { scrollToDossier: true }));

  renderSalaryView(currentType, stageSelect.value);
  selectCity(selectedCity);
  setupReveals();
  setupSectionTracking();
})();
