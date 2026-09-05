(() => {
  /* 皖域择岗 · 分数模拟 v9：双科滑杆 / 蒙特卡洛概率 / 岗位级对照 / 方案保存 / 直方图标记 */
  const data = window.productData || {};
  if (!document.querySelector('#sim-score')) return; // 仅分数模拟视图挂载
  const core = window.wanyuCore || {};
  const scoreMetrics = window.wanyuScoreMetrics || {};
  const records = Array.isArray(data.records) ? data.records : [];
  const EXAMS = {
    事业单位: { subjects: ['职测', '综应'], min: 60, max: 150, defaults: [107.5, 107.5], compose: (a, b) => a + b, composeLabel: '职测 + 综应', scaleId: 'syb_300' },
    省考: { subjects: ['行测', '申论'], min: 30, max: 100, defaults: [70, 70], compose: (a, b) => (a + b) / 2, composeLabel: '（行测+申论）÷2', scaleId: 'province_100' },
  };
  const STORAGE_SCHEMES = 'wanyu.simSchemes.v1';
  const STORAGE_STATE = 'wanyu.simState.v1';
  const parseNum = (value) => {
    const num = Number.parseFloat(String(value ?? '').replace(/[^0-9.]/g, ''));
    return Number.isFinite(num) ? num : null;
  };
  const rows = records.map((record) => {
    const scoreObservation = scoreMetrics.fromRecord?.(record);
    return {
      record,
      id: String(record.record_id),
      exam: record.exam,
      city: record.city,
      code: record.code,
      unit: record.unit_position,
      recruits: record.recruits,
      scoreObservation,
      line: scoreObservation?.value ?? null,
      high: parseNum(record.fields?.['最高笔试']),
    };
  }).filter((row) => {
    const config = EXAMS[row.exam];
    return Boolean(config && scoreMetrics.isComparable?.(row.scoreObservation, config.scaleId));
  });
  const scoreExcludedCount = (exam) => records.filter((record) => {
    const config = EXAMS[record.exam];
    return record.exam === exam && (!config || !scoreMetrics.isComparable?.(scoreMetrics.fromRecord?.(record), config.scaleId));
  }).length;

  const examButtons = [...document.querySelectorAll('#sim-exam button')];
  const subjectBoxes = [...document.querySelectorAll('.sim-sub')];
  const subjectInputs = subjectBoxes.map((box) => box.querySelector('input[type="range"]'));
  const subjectOutputs = subjectBoxes.map((box) => box.querySelector('output'));
  const scoreOut = document.querySelector('#sim-score-out');
  const scoreHidden = document.querySelector('#sim-score');
  const scoreNum = document.querySelector('#sim-score-num');
  const volInput = document.querySelector('#sim-vol');
  const volOut = document.querySelector('#sim-vol-out');
  const citySelect = document.querySelector('#sim-city');
  const listNode = document.querySelector('#sim-list');
  const emptyNode = document.querySelector('#sim-empty');
  const histogram = document.querySelector('#sim-histogram');
  const jobSelect = document.querySelector('#sim-job-select');
  const jobReadout = document.querySelector('#sim-job-readout');
  const schemeSelect = document.querySelector('#sim-schemes');
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
  const store = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key) || fallback); } catch { return null; } };
  const userStore = window.WanyuUserStore;
  const v12State = Boolean(data.cycleRuntime?.cycle && userStore);

  let exam = '事业单位';
  let scores = [...EXAMS[exam].defaults];
  let vol = 0;
  let citiesReady = false;

  const composite = () => EXAMS[exam].compose(scores[0], scores[1]);
  const bandOf = (score, line) => (core.bandOf ? core.bandOf(score, line) : (score >= line + 5 ? 'safe' : score >= line ? 'hit' : score >= line - 3 ? 'near' : 'miss'));
  const probabilityOf = (row) => (core.monteCarlo ? core.monteCarlo(composite(), row.line, vol, 500) : { reached: vol > 0 ? 0.5 : (bandOf(composite(), row.line) === 'miss' ? 0 : 1), safe: 0 });
  const eligible = (row) => (window.wanyuEligibility ? window.wanyuEligibility.evaluate((row.record.eligibility?.tags || []).join(' ')).ok : true);
  const poolFor = () => {
    const city = citySelect?.value || '';
    return rows.filter((row) => row.exam === exam && (!city || row.city === city) && eligible(row));
  };

  const loadSavedCodes = () => {
    if (v12State) return rows.filter((row) => (userStore.activeLocalSaved?.() || []).includes(String(row.record.record_id)));
    const savedIds = store('wanyu.jobSaved.v1', '[]');
    if (!Array.isArray(savedIds)) return [];
    return rows.filter((row) => savedIds.includes(String(row.record.record_id)));
  };

  /* —— 快捷收藏：模拟清单直接收藏，与“我的岗位”/检索页双向同步 —— */
  const SAVED_KEY = 'wanyu.jobSaved.v1';
  const savedIdSet = () => v12State ? new Set(userStore.activeLocalSaved?.() || []) : (() => { const ids = store(SAVED_KEY, '[]'); return new Set(Array.isArray(ids) ? ids.map(String) : []); })();
  const toggleSaved = (id) => {
    if (v12State) {
      const ids = new Set(userStore.activeLocalSaved?.() || []);
      const value = String(id);
      const added = !ids.has(value);
      if (added) ids.add(value); else ids.delete(value);
      userStore.saveActiveSaved(ids);
      document.dispatchEvent(new CustomEvent('wanyu:saved-changed', { detail: { id: value } }));
      return added;
    }
    const ids = store(SAVED_KEY, '[]');
    const list = Array.isArray(ids) ? ids.map(String) : [];
    const at = list.indexOf(String(id));
    if (at >= 0) list.splice(at, 1); else list.push(String(id));
    try { localStorage.setItem(SAVED_KEY, JSON.stringify(list)); } catch {}
    document.dispatchEvent(new CustomEvent('wanyu:saved-changed', { detail: { id: String(id) } }));
    return at < 0;
  };

  const renderJobBox = (pool) => {
    if (!jobSelect || !jobReadout) return;
    const saved = loadSavedCodes();
    const savedGroup = jobSelect.querySelector('optgroup[data-group="saved"]');
    const allGroup = jobSelect.querySelector('optgroup[data-group="all"]');
    if (savedGroup) {
      // 收藏随“☆”实时变化，这里每次重建
      savedGroup.innerHTML = saved.map((row) => `<option value="${escapeHtml(row.code)}">${escapeHtml(row.code)} · ${escapeHtml(row.unit.slice(0, 18))}</option>`).join('')
        || '<option value="">（暂无收藏）</option>';
      savedGroup.dataset.ready = '1';
    }
    if (allGroup && !allGroup.dataset.ready) {
      allGroup.innerHTML = pool.slice(0, 400).map((row) => `<option value="${escapeHtml(row.code)}">${escapeHtml(row.code)} · ${escapeHtml(row.city)} · ${escapeHtml(row.unit.slice(0, 14))}</option>`).join('');
      allGroup.dataset.ready = '1';
    }
    const code = String(jobSelect.value || '').trim();
    const row = pool.find((item) => item.code === code) || rows.find((item) => item.code === code);
    if (!row) { jobReadout.innerHTML = '<p class="sim-jobbox__empty">输入或选择岗位代码后，这里给出该岗的逐点对照。</p>'; return; }
    const compositeScore = composite();
    const gap = compositeScore - row.line;
    const prob = probabilityOf(row);
    const target = row.line + 5;
    const bands = [
      ['稳', prob.safe, 'sim-band--safe'],
      ['进面', prob.reached, 'sim-band--hit'],
    ];
    jobReadout.innerHTML = '<div class="sim-jobbox__head"><b>' + escapeHtml(row.code) + '</b><span>' + escapeHtml(row.city) + '市 · ' + escapeHtml(row.unit) + '</span></div>'
      + '<dl><div><dt>该岗入围线</dt><dd>' + row.line.toFixed(1) + '</dd></div>'
      + '<div><dt>我的合成成绩</dt><dd>' + compositeScore.toFixed(1) + '</dd></div>'
      + '<div><dt>分差</dt><dd>' + (gap >= 0 ? '+' + gap.toFixed(1) : '差 ' + Math.abs(gap).toFixed(1)) + '</dd></div>'
      + '<div><dt>稳档需</dt><dd>' + target.toFixed(1) + (compositeScore < target ? '（还差 ' + (target - compositeScore).toFixed(1) + '）' : '（已达标）') + '</dd></div></dl>'
      + (vol > 0 ? '<div class="sim-jobbox__prob">' + bands.map(([label, value, cls]) => '<span><b class="sim-band ' + cls + '">' + label + '</b>' + Math.round(value * 100) + '%</span>').join('') + '<small>波动 ±' + vol + ' 分 · ' + (prob.samples || 0) + ' 次抽样</small></div>' : '<p class="sim-jobbox__hint">把“发挥波动”调高即可看到该岗的进面概率估计。</p>')
      + (() => { const isSaved = savedIdSet().has(row.id); return '<div class="sim-jobbox__actions"><button type="button" class="text-button' + (isSaved ? ' is-saved' : '') + '" data-sim-save="' + escapeHtml(row.id) + '">' + (isSaved ? '★ 已收藏' : '☆ 收藏该岗') + '</button><button type="button" class="text-button" data-sim-detail="' + escapeHtml(row.id) + '">岗位详情 →</button></div>'; })();
  };

  const renderHistogram = (pool) => {
    if (!histogram) return;
    const bins = new Map();
    pool.forEach((row) => {
      const start = Math.floor(row.line / 5) * 5;
      bins.set(start, (bins.get(start) || 0) + 1);
    });
    const sorted = [...bins.entries()].sort((a, b) => a[0] - b[0]);
    const max = Math.max(1, ...sorted.map(([, count]) => count));
    const score = composite();
    histogram.innerHTML = sorted.map(([start, count]) => {
      const reached = score >= start;
      return '<div class="sim-bin' + (reached ? ' is-reached' : '') + '" data-start="' + start + '" title="' + start + '–' + (start + 5) + ' 分：' + count + ' 岗"><i style="--h:' + Math.round(count / max * 100) + '%"></i><span>' + start + '</span></div>';
    }).join('') || '<p class="palette-empty">没有入围线数据</p>';
    // innerHTML 覆盖会带走标记，这里始终重建并放进滚动容器内（随内容滚动）
    let marker = histogram.querySelector('#sim-marker');
    if (!marker) {
      marker = document.createElement('div');
      marker.id = 'sim-marker';
      marker.className = 'sim-marker';
      marker.hidden = true;
      marker.title = '你的合成成绩位置';
      histogram.appendChild(marker);
    }
    const bin = [...histogram.querySelectorAll('.sim-bin')].find((node) => {
      const start = Number(node.dataset.start);
      return score >= start && score < start + 5;
    });
    if (bin) {
      const left = bin.offsetLeft + ((score - Number(bin.dataset.start)) / 5) * bin.offsetWidth;
      marker.style.left = left.toFixed(1) + 'px';
      marker.hidden = false;
    } else {
      marker.hidden = true;
    }
  };

  const render = (persist = true) => {
    const cfg = EXAMS[exam];
    subjectBoxes.forEach((box, index) => {
      box.querySelector('.sim-sub__label').textContent = cfg.subjects[index];
      const input = subjectInputs[index];
      if (input) { input.min = String(cfg.min); input.max = String(cfg.max); input.value = String(scores[index]); }
      const output = subjectOutputs[index];
      if (output) output.textContent = String(scores[index]);
    });
    const compositeScore = composite();
    if (scoreHidden) scoreHidden.value = String(compositeScore);
    if (scoreNum) { scoreNum.max = String(cfg.max * (exam === '事业单位' ? 2 : 1)); scoreNum.value = String(compositeScore); }
    if (scoreOut) scoreOut.textContent = compositeScore.toFixed(1);
    if (volOut) volOut.textContent = '±' + vol;
    document.querySelector('.sim-compose-label')?.replaceChildren(document.createTextNode(cfg.composeLabel));
    if (!citiesReady && citySelect) {
      const cities = [...new Set(rows.filter((row) => row.exam === exam).map((row) => row.city))];
      citySelect.innerHTML = '<option value="">全省（16 市）</option>' + cities.map((city) => '<option value="' + escapeHtml(city) + '">' + escapeHtml(city) + '市</option>').join('');
      citiesReady = true;
    }
    const city = citySelect?.value || '';
    if (citySelect) citySelect.classList.toggle('is-scoped', Boolean(city));
    const pool = poolFor();
    const bucket = { safe: [], hit: [], near: [], miss: [] };
    pool.forEach((row) => bucket[bandOf(compositeScore, row.line)].push(row));
    const byLine = (a, b) => a.line - b.line;
    bucket.safe.sort(byLine); bucket.hit.sort(byLine); bucket.near.sort((a, b) => b.line - a.line); bucket.miss.sort((a, b) => b.line - a.line);
    document.querySelector('#sim-context').textContent = exam + ' · ' + compositeScore.toFixed(1) + ' 分' + (city ? ' · ' + city + '市' : '') + (vol > 0 ? ' · 波动±' + vol : '');
    const scopeCount = document.querySelector('.sim-scope-count');
    if (scopeCount) scopeCount.textContent = city ? '限定 ' + city + '市' : '覆盖 ' + new Set(pool.map((row) => row.city)).size + ' 市';
    document.querySelector('#sim-count-safe').textContent = String(bucket.safe.length);
    document.querySelector('#sim-count-hit').textContent = String(bucket.hit.length);
    document.querySelector('#sim-count-near').textContent = String(bucket.near.length);
    document.querySelector('#sim-count-noline').textContent = String(scoreExcludedCount(exam));
    const qualityNote = document.querySelector('#sim-quality-note');
    if (qualityNote) qualityNote.textContent = `${scoreExcludedCount(exam)} 条记录因缺失、哨兵值或分数口径不明，未参与本次比较。`;
    const savedCountNode = document.querySelector('#sim-count-saved');
    if (savedCountNode) {
      const ids = savedIdSet();
      savedCountNode.textContent = rows.filter((row) => ids.has(row.id) && row.exam === exam && bandOf(compositeScore, row.line) === 'safe').length + ' 条';
    }
    const probNode = document.querySelector('#sim-prob');
    if (probNode) {
      if (vol > 0 && pool.length) {
        const probs = pool.map((row) => probabilityOf(row).reached);
        const avg = probs.reduce((sum, value) => sum + value, 0) / probs.length;
        probNode.textContent = Math.round(avg * 100) + '%（' + Math.round(Math.min(...probs) * 100) + '%–' + Math.round(Math.max(...probs) * 100) + '%）';
      } else {
        probNode.textContent = '—';
      }
    }
    renderHistogram(pool);
    const bandMeta = {
      safe: ['稳', '高于入围线 5 分以上', 'sim-band--safe'],
      hit: ['达线', '入围线 ≤ 我的分数', 'sim-band--hit'],
      near: ['贴线', '差 3 分以内', 'sim-band--near'],
      miss: ['最近未达', '只列最接近的 8 条', 'sim-band--miss'],
    };
    const sections = ['safe', 'hit', 'near', 'miss'].filter((key) => (key === 'miss' ? bucket.miss.length && compositeScore < bucket.miss[0].line : bucket[key].length));
    const rowHtml = (row) => {
      const gap = compositeScore - row.line;
      const gapText = gap >= 0 ? '+' + gap.toFixed(1) : '差 ' + Math.abs(gap).toFixed(1);
      const isSaved = savedIdSet().has(row.id);
      return '<div class="sim-row"><span class="sim-row__gap">' + gapText + '</span>'
        + '<div class="sim-row__main"><strong>' + escapeHtml(row.code) + '</strong><span><b class="sim-city-badge">' + escapeHtml(row.city) + '市</b>' + escapeHtml(row.unit) + '</span></div>'
        + '<div class="sim-row__facts"><span>入围 ' + row.line.toFixed(1) + '</span><span>' + (row.high !== null ? '最高 ' + row.high.toFixed(1) : '—') + '</span><span>招' + row.recruits + '</span></div>'
        + '<button type="button" class="sim-row__save' + (isSaved ? ' is-saved' : '') + '" data-sim-save="' + escapeHtml(row.id) + '" aria-label="收藏该岗位" title="收藏后可在“我的岗位”、对比与决策单中使用">' + (isSaved ? '★' : '☆') + '</button></div>';
    };
    listNode.innerHTML = sections.map((key) => (
      '<section class="sim-group sim-group--' + key + '"><header><b class="sim-band ' + bandMeta[key][2] + '">' + bandMeta[key][0] + '</b><span>' + bucket[key].length + ' 岗 · ' + bandMeta[key][1] + '</span></header>'
      + bucket[key].slice(0, key === 'miss' ? 8 : 200).map(rowHtml).join('')
      + (key === 'miss' && bucket.miss.length > 8 ? '<p class="sim-more">其余 ' + (bucket.miss.length - 8) + ' 条未列出</p>' : '')
      + '</section>'
    )).join('');
    if (emptyNode) emptyNode.hidden = pool.length > 0;
    renderJobBox(pool);
    if (persist) {
      try { localStorage.setItem(STORAGE_STATE, JSON.stringify({ exam, scores, vol, city })); } catch {}
    }
  };

  const renderSchemes = () => {
    if (!schemeSelect) return;
    const schemes = store(STORAGE_SCHEMES, '{}') || {};
    schemeSelect.innerHTML = '<option value="">选择已存方案…</option>' + Object.keys(schemes).map((name) => '<option value="' + escapeHtml(name) + '">' + escapeHtml(name) + '</option>').join('');
  };
  const saveScheme = () => {
    const nameInput = document.querySelector('#sim-scheme-name');
    const name = String(nameInput?.value || '').trim();
    if (!name) { nameInput?.focus(); return; }
    const schemes = store(STORAGE_SCHEMES, '{}') || {};
    schemes[name] = { exam, scores: [...scores], vol, city: citySelect?.value || '' };
    try { localStorage.setItem(STORAGE_SCHEMES, JSON.stringify(schemes)); } catch {}
    if (nameInput) nameInput.value = '';
    renderSchemes();
    if (schemeSelect) schemeSelect.value = name;
  };
  const deleteScheme = () => {
    const name = schemeSelect?.value;
    if (!name) return;
    const schemes = store(STORAGE_SCHEMES, '{}') || {};
    delete schemes[name];
    try { localStorage.setItem(STORAGE_SCHEMES, JSON.stringify(schemes)); } catch {}
    renderSchemes();
  };

  const applyExam = (nextExam) => {
    exam = nextExam;
    scores = [...EXAMS[exam].defaults];
    citiesReady = false;
    render();
  };
  examButtons.forEach((button) => button.addEventListener('click', () => {
    examButtons.forEach((item) => item.classList.toggle('is-selected', item === button));
    applyExam(button.dataset.simExam);
  }));
  subjectInputs.forEach((input, index) => input?.addEventListener('input', () => {
    scores[index] = Number.parseFloat(input.value);
    render();
  }));
scoreNum?.addEventListener('input', () => {
const value = Number.parseFloat(scoreNum.value);
if (!Number.isFinite(value)) return;
const cfg = EXAMS[exam];
const compMax = cfg.max * (exam === '事业单位' ? 2 : 1);
const target = Math.min(Math.max(value, cfg.min), compMax);
    const total = cfg.compose(scores[0], scores[1]) || 1;
    const scale = exam === '省考' ? 2 * target : target; // 省考合成=(两科和)÷2
    const ratio = Math.min(1, Math.max(0, scores[0] / total));
    const s1 = Math.min(cfg.max, Math.max(cfg.min, scale * ratio));
    const s2 = Math.min(cfg.max, Math.max(cfg.min, scale - s1));
    scores = [Number(s1.toFixed(1)), Number(s2.toFixed(1))];
    render();
  });
  volInput?.addEventListener('input', () => { vol = Number.parseFloat(volInput.value) || 0; render(); });
  citySelect?.addEventListener('change', render);
  document.addEventListener('wanyu:profile-changed', () => render(false));
  document.querySelector('#sim-reset')?.addEventListener('click', () => { scores = [...EXAMS[exam].defaults]; vol = 0; if (volInput) volInput.value = '0'; if (citySelect) citySelect.value = ''; render(); });
  jobSelect?.addEventListener('change', render);
  // 清单/岗位对照里的收藏与详情（委托）
  document.addEventListener('click', (event) => {
    const saveButton = event.target.closest('[data-sim-save]');
    if (saveButton) {
      const added = toggleSaved(saveButton.dataset.simSave);
      saveButton.classList.toggle('is-saved', added);
      saveButton.textContent = saveButton.classList.contains('sim-row__save') ? (added ? '★' : '☆') : (added ? '★ 已收藏' : '☆ 收藏该岗');
      render(false);
      return;
    }
    const detailButton = event.target.closest('[data-sim-detail]');
    if (detailButton) {
      const target = rows.find((row) => row.id === String(detailButton.dataset.simDetail));
      if (target) window.wanyuOpenJobDetail?.(target.record);
    }
  });
  // 检索页/详情浮层改动收藏后，同步本页计数与清单星标
  document.addEventListener('wanyu:saved-changed', () => render(false));
  document.querySelector('#sim-scheme-save')?.addEventListener('click', saveScheme);
  document.querySelector('#sim-scheme-delete')?.addEventListener('click', deleteScheme);
  schemeSelect?.addEventListener('change', () => {
    const scheme = (store(STORAGE_SCHEMES, '{}') || {})[schemeSelect.value];
    if (!scheme) return;
    if (EXAMS[scheme.exam]) {
      exam = scheme.exam;
      examButtons.forEach((item) => item.classList.toggle('is-selected', item.dataset.simExam === exam));
      scores = Array.isArray(scheme.scores) ? [...scheme.scores] : [...EXAMS[exam].defaults];
      citiesReady = false;
    }
    vol = Number(scheme.vol) || 0;
    if (volInput) volInput.value = String(vol);
    render(false);
    citySelect.value = String(scheme.city || '');
    render(false);
  });

  // 恢复上次状态
  try {
    const state = store(STORAGE_STATE, 'null');
    if (state && EXAMS[state.exam]) {
      exam = state.exam;
      examButtons.forEach((item) => item.classList.toggle('is-selected', item.dataset.simExam === exam));
      scores = Array.isArray(state.scores) && state.scores.length === 2 ? state.scores.map(Number) : [...EXAMS[exam].defaults];
      vol = Number(state.vol) || 0;
      if (volInput) volInput.value = String(vol);
      citiesReady = false;
    }
  } catch {}
  renderSchemes();
  render(false);
})();
