(() => {
  const data = window.productData || {};
  const salaryData = data.salary || data;
  const series = salaryData.series || {};
  const cities = salaryData.cities || [];
  const stages = salaryData.stages || [];
  const query = new URLSearchParams(location.search);
  const validTypes = new Set(Object.keys(series));
  const validStages = new Set(stages);
  const fallbackType = validTypes.has('公务员') ? '公务员' : [...validTypes][0];
  const fallbackStage = validStages.has('3年') ? '3年' : stages[0];
  if (!validTypes.size || !document.querySelector('#salary-ranking-table')) return;
  let type = validTypes.has(query.get('type')) ? query.get('type') : fallbackType;
  let stage = validStages.has(query.get('stage')) ? query.get('stage') : fallbackStage;
  const selected = new Set();
  const renderSummary = () => {
    const wrap = document.querySelector('#salary-compare-bars'); const note = document.querySelector('#salary-compare-summary-note');
    if (!wrap) return;
    if (!selected.size) { wrap.innerHTML = '<p class="compare-summary__empty">从排名表选择城市，查看五个工龄节点。</p>'; if (note) note.textContent = '选择 1–4 个城市查看'; return; }
    const values = [...selected].map((city) => Number(series[type]?.[city]?.[stage] || 0)); const max = Math.max(...values, 1);
    wrap.innerHTML = [...selected].map((city) => { const value = Number(series[type]?.[city]?.[stage] || 0); const counterpart = otherType(); const alternate = Number(series[counterpart]?.[city]?.[stage] || 0); return `<div class="compare-bar" data-compare-bar data-city="${escapeHtml(city)}"><span class="compare-bar__label">${escapeHtml(city)}市</span><span class="compare-bar__track"><i class="compare-bar__fill" style="--bar-width:${Math.max(5, value / max * 100).toFixed(1)}%"></i></span><strong class="compare-bar__value">${value.toFixed(1)} 万元</strong><small class="compare-bar__sub">${escapeHtml(type)} · ${escapeHtml(stage)}；${escapeHtml(counterpart || '另一身份')} · ${escapeHtml(stage)} ${alternate.toFixed(1)} 万元</small></div>`; }).join('');
    if (note) note.textContent = `${selected.size} 个城市 · ${type} · ${stage}`;
  };
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
  const otherType = () => Object.keys(series).find((name) => name !== type);
  const render = () => { const body = document.querySelector('#salary-ranking-table tbody'); const rows = [...body.querySelectorAll('[data-salary-row]')]; rows.forEach((row) => { const city = row.dataset.city; stages.forEach((name, index) => { row.children[index + 2].textContent = series[type][city][name] == null ? '—' : Number(series[type][city][name]).toFixed(1); }); row.dataset.current = series[type][city][stage] || 0; }); rows.sort((a, b) => Number(b.dataset.current) - Number(a.dataset.current) || a.dataset.city.localeCompare(b.dataset.city, 'zh')); rows.forEach((row, index) => { row.querySelector('.rank-cell').textContent = String(index + 1).padStart(2, '0'); body.appendChild(row); }); document.querySelector('#salary-ranking-note').textContent = type + ' · ' + stage; document.querySelectorAll('#salary-type [data-type]').forEach((button) => { const active = button.dataset.type === type; button.classList.toggle('is-selected', active); button.setAttribute('aria-pressed', String(active)); }); document.querySelectorAll('#salary-stage-pills [data-stage]').forEach((button) => { const active = button.dataset.stage === stage; button.classList.toggle('is-selected', active); button.setAttribute('aria-pressed', String(active)); }); renderSummary(); const url = new URL(location.href); type === '公务员' ? url.searchParams.delete('type') : url.searchParams.set('type', type); stage === '3年' ? url.searchParams.delete('stage') : url.searchParams.set('stage', stage); history.replaceState({}, '', url); };
  const renderCompare = () => { const wrap = document.querySelector('#salary-compare-cards'); const counterpart = otherType(); wrap.innerHTML = [...selected].map((city) => { const current = Number(series[type][city][stage] || 0).toFixed(1); const alternate = counterpart ? Number(series[counterpart][city][stage] || 0).toFixed(1) : '—'; return '<div class="compare-card"><strong>' + escapeHtml(city) + '市</strong><span>' + escapeHtml(type) + ' · ' + escapeHtml(stage) + ' ' + current + ' · ' + escapeHtml(counterpart || '另一身份') + ' · ' + escapeHtml(stage) + ' ' + alternate + ' 万元 <button type="button" data-remove-salary="' + escapeHtml(city) + '" aria-label="移除' + escapeHtml(city) + '市">×</button></span></div>'; }).join(''); document.querySelector('#salary-compare-count').textContent = selected.size + ' / 4'; document.querySelector('#salary-compare-empty').hidden = selected.size > 0; document.querySelector('#salary-compare-guide')?.toggleAttribute('hidden', selected.size > 0); renderSummary(); wrap.querySelectorAll('[data-remove-salary]').forEach((button) => button.addEventListener('click', () => { selected.delete(button.dataset.removeSalary); renderCompare(); })); };
  /* —— 五维雷达：把已选城市的五个工龄节点放进同一张图 —— */
  const renderRadar = () => {
    const host = document.querySelector('#salary-radar');
    if (!host) return;
    const picked = [...selected].slice(0, 4);
    if (!picked.length) { host.innerHTML = '<p class="radar-empty">在排名表选择 1–4 个城市，生成五节点雷达对比。</p>'; return; }
    const size = 260; const center = size / 2; const radius = 92;
    const allValues = picked.flatMap((city) => stages.map((stage) => Number(series[type]?.[city]?.[stage] || 0)));
    const max = Math.max(...allValues, 1) * 1.06;
    const colors = ['#2167dc', '#d9912c', '#2b9e9a', '#b6543f'];
    const angleOf = (index) => (Math.PI * 2 * index) / stages.length - Math.PI / 2;
    const point = (stageIndex, value) => {
      const r = (value / max) * radius;
      return (center + Math.cos(angleOf(stageIndex)) * r).toFixed(1) + ',' + (center + Math.sin(angleOf(stageIndex)) * r).toFixed(1);
    };
    const rings = [0.25, 0.5, 0.75, 1].map((ratio) => '<polygon points="' + stages.map((_, index) => center + ',' + center).map((_, index) => point(index, max * ratio)).join(' ') + '" class="radar-ring"/>').join('');
    const axes = stages.map((stage, index) => {
      const [x, y] = point(index, max).split(',');
      const lx = center + Math.cos(angleOf(index)) * (radius + 22);
      const ly = center + Math.sin(angleOf(index)) * (radius + 16);
      return '<line x1="' + center + '" y1="' + center + '" x2="' + x + '" y2="' + y + '" class="radar-axis"/><text x="' + lx.toFixed(1) + '" y="' + ly.toFixed(1) + '" text-anchor="middle" class="radar-axis-label">' + stage + '</text>';
    }).join('');
    const shapes = picked.map((city, cityIndex) => {
      const polygon = stages.map((stage, index) => point(index, Number(series[type]?.[city]?.[stage] || 0))).join(' ');
      const dots = stages.map((stage, index) => { const [x, y] = point(index, Number(series[type]?.[city]?.[stage] || 0)).split(','); return '<circle cx="' + x + '" cy="' + y + '" r="2.6" fill="' + colors[cityIndex % 4] + '"/>'; }).join('');
      return '<polygon points="' + polygon + '" fill="' + colors[cityIndex % 4] + '" fill-opacity=".14" stroke="' + colors[cityIndex % 4] + '" stroke-width="1.8"/>' + dots;
    }).join('');
    const legend = picked.map((city, index) => '<span><i style="background:' + colors[index % 4] + '"></i>' + escapeHtml(city) + '市</span>').join('');
    host.innerHTML = '<svg viewBox="0 0 ' + size + ' ' + size + '" role="img" aria-label="五工龄节点雷达对比">' + rings + axes + shapes + '</svg><div class="radar-legend">' + legend + '</div><small class="radar-note">' + escapeHtml(type) + ' · 五节点同轴对比，各轴独立归一。</small>';
  };
  document.querySelectorAll('#salary-type [data-type]').forEach((button) => button.addEventListener('click', () => { if (validTypes.has(button.dataset.type)) { type = button.dataset.type; render(); renderCompare(); renderRadar(); } }));
  document.querySelectorAll('#salary-stage-pills [data-stage]').forEach((button) => button.addEventListener('click', () => { if (validStages.has(button.dataset.stage)) { stage = button.dataset.stage; render(); renderCompare(); renderRadar(); } }));
  document.querySelectorAll('[data-salary-compare]').forEach((button) => button.addEventListener('click', () => { if (cities.includes(button.dataset.salaryCompare) && (selected.size < 4 || selected.has(button.dataset.salaryCompare))) selected.add(button.dataset.salaryCompare); renderCompare(); renderRadar(); }));
  document.querySelectorAll('#salary-ranking-table th button[data-city]').forEach((button) => button.addEventListener('click', () => { if (cities.includes(button.dataset.city) && (selected.size < 4 || selected.has(button.dataset.city))) selected.add(button.dataset.city); renderCompare(); renderRadar(); }));
  render(); renderCompare(); renderRadar();
})();
