(() => {
  const app = document.querySelector('#maintainable-app');
  const main = document.querySelector('#maintain-main');
  const statusNode = document.querySelector('#maintain-status');
  const cyclePicker = document.querySelector('#maintain-cycle-picker');
  const state = {
    manifest: null,
    dataStore: null,
    cycle: null,
    view: (location.hash || '#overview').slice(1) || 'overview',
    modules: new Map(),
    auditIndex: null,
    reviewQueue: null,
    supplementEvidence: null,
    mapData: null,
    mapMetric: 'jobs',
    mapCity: '',
    mapMajor: '',
    salaryData: null,
    salaryType: '公务员',
    salaryStage: '3年',
    jobHistory: null,
    auditFilter: 'all',
    changesFilter: 'all',
    examFilter: '全部',
    examSub: '',
    ranking: { major: '', city: '', exam: '', category: '', metric: 'jobs' },
    keyword: '',
    searchMajor: '',
    city: '',
    searchCityGroup: '',
    exam: '',
    searchPage: 0,
    searchPageSize: 60,
    searchSteal: false,
    searchSort: 'source',
    searchDensity: 'comfortable',
    detail: null,
    notice: '',
    renderToken: 0,
  };
  const validViews = new Set(['overview', 'cycle_compare', 'jobs_map', 'salary_map', 'jobs_ranking', 'jobs_search', 'saved', 'changes', 'data_boundary', 'help', 'changelog', 'calendar', 'match']);
  const themeToggle = document.querySelector('#maintain-theme-toggle');
  const THEME_KEY = 'wanyu.v15.theme';
  const themeFromQuery = () => {
    const value = new URL(location.href).searchParams.get('theme');
    return value === 'dark' || value === 'light' ? value : '';
  };
  const currentTheme = () => document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
  const applyTheme = (next, persist) => {
    const theme = next === 'dark' || next === 'light' ? next : currentTheme();
    document.documentElement.dataset.theme = theme;
    if (themeToggle) {
      themeToggle.textContent = theme === 'dark' ? '☀' : '☾';
      themeToggle.setAttribute('aria-label', theme === 'dark' ? '切换到浅色主题' : '切换到深色主题');
      themeToggle.setAttribute('aria-pressed', String(theme === 'dark'));
    }
    if (persist) { try { localStorage.setItem(THEME_KEY, theme); } catch (error) { /* 隐私模式忽略 */ } }
  };
  applyTheme(themeFromQuery() || currentTheme(), Boolean(themeFromQuery()));
  themeToggle?.addEventListener('click', () => applyTheme(currentTheme() === 'dark' ? 'light' : 'dark', true));
  matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', (event) => {
    let stored = '';
    try { stored = localStorage.getItem(THEME_KEY); } catch (error) { /* 隐私模式忽略 */ }
    if (stored !== 'dark' && stored !== 'light') applyTheme(event.matches ? 'dark' : 'light', false);
  });
  const palette = { open: false, query: '', active: 0, entries: [], loaded: false, items: [] };
  const paletteOverlay = () => document.querySelector('[data-maint-palette]');
  // P0-2: 视图单一命名源 —— 桌面导航(index.html)、移动端宫格/更多面板、命令面板、加载标题共用
  // full=考生标准名(与 index.html 桌面导航逐字一致)；short=移动端宫格省字名
  const VIEW_META = {
    overview: { full: '总览', short: '总览' },
    jobs_search: { full: '找岗位', short: '检索' },
    jobs_map: { full: '岗位地图', short: '地图' },
    salary_map: { full: '待遇对比', short: '待遇' },
    jobs_ranking: { full: '城市排行', short: '榜单' },
    cycle_compare: { full: '三年趋势', short: '三年' },
    calendar: { full: '报考日历', short: '日历' },
    match: { full: '为我匹配', short: '匹配' },
    changes: { full: '变更通报', short: '变更' },
    saved: { full: '我的收藏', short: '收藏' },
    data_boundary: { full: '数据说明', short: '数据' },
    help: { full: '使用说明', short: '指南' },
    changelog: { full: '更新日志', short: '日志' },
  };
  // P0-3: 学历筛选改为"可报关系"——用户学历等级 >= 岗位最低学历要求（此前是文本 includes，
  // 选"研究生"只命中 xl 字面含"研究生"的行，漏掉全部"本科及以上"）。岗位文本提到多个档位时取最低档（如"大专或本科"）。
  const EDU_TIER_KEYWORDS = [['博士', 5], ['硕士', 4], ['研究生', 4], ['本科', 3], ['学士', 3], ['大专', 2], ['专科', 2], ['中专', 1], ['高中', 1], ['中师', 1]];
  const xlMinTier = (xl) => {
    const text = String(xl || '');
    if (!text || text.includes('不限') || text.includes('无')) return 0;
    const tiers = EDU_TIER_KEYWORDS.filter(([kw]) => text.includes(kw)).map(([, tier]) => tier);
    return tiers.length ? Math.min(...tiers) : 0;
  };
  const educationAllows = (userLevel, xl) => {
    if (!userLevel || userLevel === '不限') return true;
    return xlMinTier(xl) <= xlMinTier(userLevel);
  };
  const paletteActions = () => [
    ...Object.entries(VIEW_META).map(([view, names]) => ({
      kind: 'view', value: view,
      label: `打开：${names.full}`,
      meta: '视图',
    })),
    { kind: 'theme', label: '切换深浅主题', meta: '外观' },
    ...(state.manifest?.cycles || []).map((item) => ({ kind: 'cycle', value: String(item.cycle), label: `切换周期：${item.cycle}`, meta: '周期' })),
  ];
  const paletteRender = () => {
    const overlay = paletteOverlay();
    if (!overlay) return;
    const query = normalize(palette.query);
    const actions = paletteActions().filter((action) => !query || normalize(action.label).includes(query)).slice(0, 4);
    const jobs = (palette.entries || [])
      .filter((entry) => !query || normalize(`${entry.code} ${entry.unit} ${entry.title} ${entry.city} ${entry.exam}`).includes(query))
      .slice(0, 8)
      .map((entry) => ({ kind: 'job', value: entry.id, label: `${entry.code} · ${entry.title || entry.unit || '岗位'}`, meta: `${cityDisplay(entry.city)} · ${entry.exam}` }));
    palette.items = [...actions, ...jobs];
    palette.active = Math.min(palette.active, Math.max(0, palette.items.length - 1));
    overlay.querySelector('[data-maint-palette-list]').innerHTML = palette.items.map((item, index) => `<button type="button" class="maint-palette__item${index === palette.active ? ' is-active' : ''}" data-maint-palette-item data-index="${index}"><span>${escapeHtml(item.label)}</span><small>${escapeHtml(item.meta || '')}</small></button>`).join('') || '<p class="maint-palette__empty">没有匹配项</p>';
  };
  const openPalette = async () => {
    palette.open = true;
    palette.query = '';
    palette.active = 0;
    if (!palette.loaded) {
      // P0-9: palette.json(1.44MB, jobs_lite 纯子集)退役——命令面板条目改由已在内存的 jobs_lite 行派生，零额外下载
      try {
        const lite = state.modules.get(`${state.cycle}:jobs_lite`) || await loadModule(state.cycle, 'jobs_lite');
        palette.entries = (lite?.allMajors?.rows || []).filter((row) => !isPhantomRow(row)).map((row) => ({ id: row.job_id || row.code || '', code: row.code || '', title: row.zw || row.display_title || '', unit: row.unit || '', city: row.city || row.reg || '', exam: row.exam || '' }));
      } catch (error) { palette.entries = []; }
      palette.loaded = true;
    }
    if (!paletteOverlay()) {
      app.insertAdjacentHTML('beforeend', `<div class="maint-palette" data-maint-palette role="dialog" aria-modal="true" aria-label="命令面板"><div class="maint-palette__panel"><input id="maint-palette-input" type="search" placeholder="搜索视图、周期、岗位（代码 / 单位 / 职位 / 城市）" autocomplete="off"><div class="maint-palette__list" data-maint-palette-list role="listbox" aria-label="命令面板结果"></div><p class="maint-palette__hint">↑↓ 选择 · Enter 执行 · Esc 关闭 · 全部本地匹配</p></div></div>`);
    }
    paletteRender();
    document.querySelector('#maint-palette-input')?.focus();
  };
  const closePalette = () => {
    palette.open = false;
    paletteOverlay()?.remove();
  };
  const paletteExecute = async (item) => {
    closePalette();
    if (!item) return;
    if (item.kind === 'view') { await setView(item.value); return; }
    if (item.kind === 'theme') { applyTheme(currentTheme() === 'dark' ? 'light' : 'dark', true); return; }
    if (item.kind === 'cycle') {
      try { await loadCycle(item.value); palette.loaded = false; await render(); } catch (error) { showError(error); }
      return;
    }
    if (item.kind === 'job') await openDetail(item.value);
  };
  const mapViewNavAttribute = 'data-maintain-view="jobs_map"';
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
  const cleanMajorOption = (value) => {
    let text = String(value || '').trim();
    if (!/[\u4e00-\u9fffA-Za-z]/.test(text)) return '';
    text = text.replace(/^[A-Za-z](?=[\u4e00-\u9fff])/, '')
      .replace(/(?<![A-Za-z0-9])[A-Za-z]?\d{4,8}(?![A-Za-z0-9])/g, '')
      .replace(/\s*[/\\|,，;；]+\s*/g, '、')
      .replace(/、{2,}/g, '、')
      .replace(/^[\s/\\|,，;；:：._-—()（）[\]【】、]+|[\s/\\|,，;；:：._-—()（）[\]【】、]+$/g, '')
      .trim();
    return text;
  };
  const isHumanMajor = (value) => {
    const text = cleanMajorOption(value);
    return text.length >= 2 && /[\u4e00-\u9fffA-Za-z]/.test(text)
      && text.replace(/[\d\s()[\]{}._（）【】+\-*\/、，,;；:.：?？]/g, '').length > 0;
  };
  // 专业选项清洗：去专业代码、去大小写重复、丢截断残缺项；组合招录条件不进建议列表，单个专业全覆盖
  const curateMajorOptions = (catalog, payload) => {
    const raw = Array.isArray(catalog?.majors) && catalog.majors.length
      ? catalog.majors
      : [...new Set(rowsFor(payload).map((row) => cleanMajorOption(row?.zy)).filter(isHumanMajor))];
    const merged = new Map();
    for (const item of raw) {
      let text = cleanMajorOption(item)
        .replace(/\((?=[^()]*\d{6})[^()]*\)?/g, '')
        .replace(/(?<![A-Za-z0-9])[A-Za-z]?\d{4,8}[A-Za-z]{0,2}(?![A-Za-z0-9])/g, '')
        .replace(/、{2,}/g, '、')
        .replace(/^[\s、.。:：,，]+|[\s、.。:：,，]+$/g, '')
        .trim();
      if (!isHumanMajor(text)) continue;
      if (!/[\u4e00-\u9fff]/.test(text)) continue;
      if (text.length > 40) continue;
      if (text.split('(').length !== text.split(')').length) continue;
      if (text.split('（').length !== text.split('）').length) continue;
      if (text.includes('、')) continue;
      if (/^(专业)?不限(专业)?$/.test(text)) text = '不限';
      text = text.replace(/专业$/, '');
      if (!isHumanMajor(text)) continue;
      const key = text.toLowerCase().replace(/\s+/g, '');
      const count = majorCount(catalog, String(item)) || 0;
      const prev = merged.get(key);
      if (!prev || count > prev.count || (count === prev.count && text.length < prev.text.length)) {
        merged.set(key, { text, count });
      }
    }
    return [...merged.values()]
      .sort((a, b) => b.count - a.count || a.text.localeCompare(b.text, 'zh'))
      .slice(0, 1500)
      .map((entry) => entry.text);
  };
  const normalize = (value) => String(value || '').replace(/\s+/g, '').toLocaleLowerCase();
  const number = (value) => Number(value || 0).toLocaleString('en-US');
  const VIEW_NUMBERS = { overview: '01', cycle_compare: '02', jobs_map: '03', salary_map: '04', jobs_ranking: '05', jobs_search: '06', saved: '07', data_boundary: '08', help: '09', changelog: '10', changes: '11', calendar: '12', match: '13' };
  const viewEyebrow = (view, text) => `<p class="maint-eyebrow"><span class="maint-eyebrow__index">${VIEW_NUMBERS[view] || '--'}</span>${text}</p>`;
  const prefersReducedMotion = () => Boolean(matchMedia('(prefers-reduced-motion: reduce)')?.matches);
  const REVEAL_SELECTOR = '.maint-hero, .bento, .maint-panel, .maint-kpis, .maint-callout, .maint-grid';
  const motion = { enabled: false, observer: null, tiltTarget: null };
  const countUp = (node) => {
    const finalText = node.textContent || '';
    const target = Number(finalText.replace(/,/g, ''));
    if (!Number.isFinite(target) || target <= 0) return;
    const startedAt = performance.now();
    const duration = 620;
    const step = (now) => {
      const progress = Math.min(1, (now - startedAt) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      node.textContent = number(Math.round(target * eased));
      if (progress < 1) requestAnimationFrame(step);
      else node.textContent = finalText;
    };
    requestAnimationFrame(step);
  };
  const onReveal = (entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-in');
      entry.target.querySelectorAll?.('[data-countup]').forEach((node) => {
        if (!node.dataset.countupDone) { node.dataset.countupDone = '1'; countUp(node); }
      });
      motion.observer?.unobserve(entry.target);
    });
  };
  const initMotion = () => {
    if (prefersReducedMotion() || typeof IntersectionObserver !== 'function') return;
    motion.enabled = true;
    document.documentElement.classList.add('reveal-ready');
    motion.observer = new IntersectionObserver(onReveal, { threshold: 0.12 });
    document.querySelector('.maint-cta') && motion.observer.observe(document.querySelector('.maint-cta'));
  };
  const hydrateMotion = () => {
    if (!motion.enabled || !motion.observer) return;
    motion.observer.disconnect();
    motion.observer.observe(document.querySelector('.maint-cta'));
    main.querySelectorAll(REVEAL_SELECTOR).forEach((node) => motion.observer.observe(node));
  };
  const applyTilt = (stamp, event) => {
    const rect = stamp.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const px = (event.clientX - rect.left) / rect.width - 0.5;
    const py = (event.clientY - rect.top) / rect.height - 0.5;
    stamp.style.setProperty('--tilt-x', `${(py * -6).toFixed(2)}deg`);
    stamp.style.setProperty('--tilt-y', `${(px * 8).toFixed(2)}deg`);
  };
  const resetTilt = (stamp) => {
    stamp.style.setProperty('--tilt-x', '0deg');
    stamp.style.setProperty('--tilt-y', '0deg');
  };
  const readableStatus = (value) => ({
    verified: '已核验',
    partial_evidence: '部分证据已核验',
    source_bundle: '源包接入',
    derived: '派生指标',
    registered: '已登记',
    unpublished_or_unavailable: '未发布或未取得',
    ambiguous_join: '无法唯一关联',
    needs_review: '待复核',
  }[String(value)] || String(value || '—'));
  const severityLabel = (value) => ({ high: '高风险', critical: '高风险', medium: '中风险', low: '低风险' }[String(value)] || String(value || '—'));
  const methodLabel = (value) => ({ official_page: '官方页面/附件', source_bundle: '源包接入', derived: '由源字段派生', mirror_verified: '镜像核对' }[String(value)] || String(value || '未提供处理方式'));
  const majorCount = (catalog, value) => Number(catalog?.major_counts?.[value] || 0);
  const commonMajorValues = (majors, catalog) => [...new Set(majors || [])]
    .sort((a, b) => majorCount(catalog, b) - majorCount(catalog, a) || String(a).localeCompare(String(b), 'zh'))
    .slice(0, 8);
  const majorTools = (target, majors, catalog) => {
    const common = commonMajorValues(majors, catalog);
    if (!common.length) return '';
    return `<div class="maint-major-tools" aria-label="常用专业关键词"><span>常用关键词</span>${common.map((value) => `<button type="button" data-maint-quick-major="${escapeHtml(value)}" data-maint-quick-target="${escapeHtml(target)}">${escapeHtml(value)}<small>${number(majorCount(catalog, value))}岗</small></button>`).join('')}</div>`;
  };
  const activeFilterMarkup = (entries) => {
    const visible = entries.filter((entry) => entry?.value);
    if (!visible.length) return '<div class="maint-active-filters" data-maint-active-filter><span>未设置筛选</span></div>';
    return `<div class="maint-active-filters" data-maint-active-filter aria-label="已生效筛选"><span>已生效</span>${visible.map((entry) => `<button type="button" data-maint-clear-filter="${escapeHtml(entry.key)}" aria-label="清除${escapeHtml(entry.label)}筛选">${escapeHtml(entry.label)}：${escapeHtml(entry.value)} ×</button>`).join('')}</div>`;
  };
// D2(2026-09-05): 马鞍山 110 个疑似重复收录岗位（华图源跨市复制，成绩公告全部来自六安，见 tools/anhui_web/d2_resolution_report_20260905.txt）——用户视图剔除，数据文件保留审计痕迹
  const PHANTOM_CODES = new Set(["0901001", "0901002", "0901003", "0901004", "0901005", "0901006", "0901007", "0901008", "0901009", "0901010", "0901011", "0901012", "0901013", "0901014", "0901015", "0901016", "0901017", "0901018", "0901019", "0901020", "0901021", "0901022", "0901023", "0901024", "0901026", "0901027", "0901028", "0901029", "0901030", "0901031", "0901032", "0901033", "0901034", "0901036", "0901037", "0901038", "0901039", "0901040", "0901041", "0901042", "0901043", "0901044", "0901045", "0901046", "0901047", "0901048", "0901049", "0901050", "0901051", "0901052", "0901053", "0901054", "0901055", "0901056", "0901057", "0901059", "0901060", "0901061", "0901062", "0901063", "0901064", "0901065", "0901066", "0901067", "0901068", "0901069", "0901070", "0901071", "0901072", "0901073", "0901074", "0901075", "0901077", "0901078", "0901079", "0901080", "0901081", "0901082", "0901083", "0901084", "0901085", "0901086", "0901087", "0901088", "0901089", "0901090", "0901091", "0901094", "0901095", "0901096", "0901097", "0901098", "0901099", "0901100", "0901101", "0901102", "0901103", "0901104", "0901106", "0901107", "0901108", "0901109", "0901110", "0901112", "0901113", "0901114", "0901115", "0901116", "0901117", "0901118"]);
  const isPhantomRow = (row) => Boolean(row) && String(row.city || '') === '马鞍山' && PHANTOM_CODES.has(String(row.code || ''));
  const rowsFor = (payload) => Array.isArray(payload?.allMajors?.rows) ? payload.allMajors.rows.filter((row) => !isPhantomRow(row)) : [];
  const metaFor = (payload) => payload?.allMajors?.meta || {};
  const sourceText = (row) => [row?.code, row?.city, row?.exam, row?.unit, row?.zw, row?.zy, row?.bz, row?.lb].map((value) => String(value || '')).join(' ');
  const setStatus = (message, tone = '') => {
    if (statusNode) { statusNode.textContent = message; statusNode.dataset.tone = tone; }
  };
  const offlineBadge = () => {
    const badge = document.querySelector('#maintain-offline-badge');
    if (badge) badge.hidden = Boolean(navigator.onLine);
  };
  offlineBadge();
  addEventListener('online', () => { offlineBadge(); setStatus('已恢复在线', 'ready'); });
  addEventListener('offline', () => { offlineBadge(); setStatus('离线模式 · 正在显示缓存数据', 'offline'); });
  const entryFor = (cycle) => state.manifest?.cycles?.find((entry) => String(entry.cycle) === String(cycle));
  const moduleUrl = (cycle, module) => {
    const entry = entryFor(cycle);
    return entry?.modules?.[module]?.data || (module === 'jobs' ? entry?.data : '');
  };
  const validateModule = (payload, cycle, module) => {
    if (!payload || typeof payload !== 'object') throw new Error(`${cycle} ${module} JSON 不是对象`);
    if (module === 'jobs' && (!payload.allMajors?.meta || !Array.isArray(payload.allMajors.rows))) throw new Error(`${cycle} jobs.json 缺少 allMajors.rows`);
    if (module === 'jobs_lite' && (!payload.allMajors?.meta || !Array.isArray(payload.allMajors.rows))) throw new Error(`${cycle} jobs_lite.json 缺少 allMajors.rows`);
    if (module === 'overview' && !payload.allMajors?.meta) throw new Error(`${cycle} overview.json 缺少摘要`);
    if (module === 'catalog' && (!Array.isArray(payload.majors) || !payload.facets || payload.major_options_mode !== 'readable_keywords')) throw new Error(`${cycle} catalog.json 缺少可读专业目录或筛选面`);
    if (module === 'positions' && (!Array.isArray(payload.rows) || payload.source_module !== 'jobs.json')) throw new Error(`${cycle} positions.json 缺少岗位索引`);
    if (module === 'changes' && (!Array.isArray(payload.changes) || !payload.summary || !payload.target_cycle)) throw new Error(`${cycle} changes.json 缺少跨周期变化摘要`);
    if (module === 'scores' && (!payload.summary || !payload.keyed)) throw new Error(`${cycle} scores.json 缺少成绩索引摘要`);
    if (module === 'audit' && !payload.audit) throw new Error(`${cycle} audit.json 缺少周期审计`);
    if (module === 'major_city' && (payload.schema !== 'wanyu-maintainable-major-city/v1' || !payload.keywords || typeof payload.keywords !== 'object' || !Number.isFinite(Number(payload.rows_total)))) throw new Error(`${cycle} major_city.json 缺少专业城市索引`);
    return payload;
  };
  const loadModule = async (cycle, module) => {
    const key = `${cycle}:${module}`;
    if (state.modules.has(key)) return state.modules.get(key);
    if (!state.dataStore) throw new Error('数据存储层尚未初始化');
    const url = moduleUrl(cycle, module);
    if (!url) throw new Error(`manifest 未登记 ${cycle} ${module} 模块`);
    setStatus(`${cycle} · 正在加载${({ overview: '概览', jobs: '岗位', jobs_lite: '岗位', catalog: '专业目录', positions: '岗位索引', palette: '命令面板', changes: '年度变化', audit: '审计', scores: '成绩' }[module] || '数据')}数据…`);
    const payload = validateModule(await state.dataStore.load(cycle, module), cycle, module);
    state.modules.set(key, payload);
    return payload;
  };
  const loadGlobalAudit = async () => {
    if (state.auditIndex) return state.auditIndex;
    if (!state.dataStore) throw new Error('数据存储层尚未初始化');
    setStatus('三年审计索引加载中…');
    const audit = await state.dataStore.loadGlobal('audit');
    if (!Array.isArray(audit?.cycles) || !audit.summary) throw new Error('three-year.json 缺少审计汇总');
    state.auditIndex = audit;
    return audit;
  };
  const loadReviewQueue = async () => {
    if (state.reviewQueue) return state.reviewQueue;
    if (!state.dataStore) throw new Error('数据存储层尚未初始化');
    setStatus('复核队列加载中…');
    const queue = await state.dataStore.loadGlobal('review_queue');
    if (!Array.isArray(queue?.items) || !queue.summary) throw new Error('review-queue.json 缺少队列汇总');
    state.reviewQueue = queue;
    return queue;
  };
  const loadSupplementEvidence = async () => {
    if (!state.manifest?.supplement) return null;
    if (state.supplementEvidence) return state.supplementEvidence;
    if (!state.dataStore) throw new Error('数据存储层尚未初始化');
    setStatus('补充证据台账加载中…');
    const payload = await state.dataStore.loadGlobal('supplement');
    if (payload?.schema !== 'wanyu-supplement-evidence/v1' || !payload.summary || !Array.isArray(payload.files)) {
      throw new Error('supplement-20260904.json 缺少证据台账结构');
    }
    state.supplementEvidence = payload;
    return payload;
  };
  const loadMap = async () => {
    if (state.mapData) return state.mapData;
    if (!state.dataStore) throw new Error('数据存储层尚未初始化');
    setStatus('真实地图几何加载中…');
    const map = await state.dataStore.loadGlobal('map');
    if (map?.schema !== 'wanyu-maintainable-map/v1' || !Array.isArray(map.features) || Number(map.feature_count) !== 16) {
      throw new Error('data/map/anhui.json 缺少真实 16 市地图几何');
    }
    if (map.features.some((feature) => !feature?.city || !feature?.d || !Number.isFinite(Number(feature.x)) || !Number.isFinite(Number(feature.y)))) {
      throw new Error('data/map/anhui.json 存在无法渲染的地图 feature');
    }
    state.mapData = map;
    return map;
  };
  const loadSalary = async () => {
    if (state.salaryData) return state.salaryData;
    if (!state.dataStore || !state.manifest?.salary) { state.salaryData = null; return null; }
    try {
      const salary = await state.dataStore.loadGlobal('salary');
      if (salary?.schema !== 'wanyu-maintainable-salary/v1' || typeof salary.series !== 'object' || !salary.series) {
        state.salaryData = null;
        return null;
      }
      state.salaryData = salary;
      return salary;
    } catch (error) {
      state.salaryData = null;
      return null;
    }
  };
  const loadJobHistory = async () => {
    if (state.jobHistory) return state.jobHistory;
    if (!state.dataStore || !state.manifest?.job_history) { state.jobHistory = null; return null; }
    try {
      const payload = await state.dataStore.loadGlobal('job_history');
      if (payload?.schema !== 'wanyu-maintainable-job-history/v1' || typeof payload.jobs !== 'object' || !payload.jobs) {
        state.jobHistory = null;
        return null;
      }
      state.jobHistory = payload;
      return payload;
    } catch (error) {
      state.jobHistory = null;
      return null;
    }
  };
  const jobHistoryKey = (row) => [row?.city, row?.unit, row?.zw || row?.display_title]
    .map((value) => String(value || '').replace(/\s+/g, '').toLowerCase())
    .join('|');
  const loadCycle = async (cycle) => {
    if (!entryFor(cycle)) throw new Error(`未知数据周期：${cycle}`);
    state.cycle = String(cycle);
    await loadModule(state.cycle, 'overview');
    return state.modules.get(`${state.cycle}:overview`);
  };
  const examRowMatches = (row, exam = '全部', sub = '') => {
    if ((!exam || exam === '全部') && !sub) return true;
    const value = String(row?.exam || '');
    if (exam === '公务员') {
      if (sub === '国考') return value.includes('国考');
      if (sub === '省考') return value.includes('省考');
      return value.includes('省考') || value.includes('国考');
    }
    if (exam === '事业编') {
      if (!value.includes('事业')) return false;
      if (sub) return String(row?.cycle || '') === sub;
      return true;
    }
    return sub ? value.includes(sub) : value.includes(exam);
  };
  const examScopeOptions = ['公务员', '事业编'];
  const scopeExamPayload = (payload) => {
    const exam = state.examFilter || '全部';
    const sub = state.examSub || '';
    if (exam === '全部' && !sub) return payload;
    const rows = rowsFor(payload).filter((row) => examRowMatches(row, exam, sub));
    return { allMajors: { rows } };
  };
  const filterRows = (payload, filters = {}) => rowsFor(payload).filter((row) => {    const major = normalize(row?.zy);
    const readableMajor = normalize(cleanMajorOption(row?.zy));
    const city = String(row?.city || row?.reg || '');
    const exam = String(row?.exam || '');
    const category = String(row?.lb || '');
    return (!filters.major || major.includes(normalize(filters.major)) || readableMajor.includes(normalize(filters.major)))
      && (!filters.city || city === filters.city)
      && (!filters.cityGroup || mapCityFor(city) === filters.cityGroup)
      && (!filters.exam || examRowMatches(row, filters.exam))
      && (!filters.category || category === filters.category);
  });
  const hasObservedCompetition = (row) => {
    const observations = row?.competition_observations;
    if (!observations || typeof observations !== 'object') return false;
    const preferred = observations.preferred_type ? observations[observations.preferred_type] : null;
    return Boolean(preferred) && preferred.status === 'observed';
  };
  const aggregateCities = (payload, filters = {}) => {
    const buckets = new Map();
    filterRows(payload, filters).forEach((row) => {
      const major = String(row?.zy || '');
      const city = String(row?.city || row?.reg || '未标注');
      const item = buckets.get(city) || { city, jobs: 0, recruits: 0, exams: new Set(), majors: new Set(), observed: 0 };
      item.jobs += 1;
      item.recruits += Number(row?.num || row?.recruits || 0);
      if (row?.exam) item.exams.add(String(row.exam));
      if (major) item.majors.add(major);
      if (hasObservedCompetition(row)) item.observed += 1;
      buckets.set(city, item);
    });
    return [...buckets.values()].map((item) => ({ ...item, exams: [...item.exams].join(' · '), majors: [...item.majors].join('；') }));
  };
  const uniqueValues = (payload, field) => [...new Set(rowsFor(payload).map((row) => String(row?.[field] || '').trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh'));
  const optionMarkup = (values, selected, label = '全部') => `<option value="">${label}</option>${values.map((value) => `<option value="${escapeHtml(value)}" ${selected === value ? 'selected' : ''}>${escapeHtml(value)}</option>`).join('')}`;
  const prefectureCityOrder = ['合肥', '芜湖', '蚌埠', '淮南', '马鞍山', '淮北', '铜陵', '安庆', '黄山', '滁州', '阜阳', '宿州', '六安', '亳州', '池州', '宣城'];
  const prefectureCities = new Set(prefectureCityOrder);
  const cityDisplay = (value) => {
    const city = String(value || '').trim();
    if (city === '省直') return city;
    return prefectureCities.has(city) ? `${city}市` : city;
  };
  const mapCityFor = (value) => {
    const city = String(value || '').trim();
    if (!city || city === '省直') return null;
    if (city === '宿松') return '安庆';
    if (city === '广德') return '宣城';
    return prefectureCityOrder.find((candidate) => city === candidate || city.startsWith(candidate)) || null;
  };
  const trendCityKey = (value) => {
    const city = String(value || '').trim();
    if (city === '省直') return '省直';
    return mapCityFor(city) || city || '未标注';
  };
  const renderCyclePicker = () => {
    if (!cyclePicker || !state.manifest) return;
    const examTypes = ['全部', '公务员', '事业编'];
    const currentExam = state.examFilter || '全部';
    cyclePicker.innerHTML = `
      <div class="cycle-picker-group">
        ${state.manifest.cycles.map((item) => `<button type="button" data-maintain-cycle="${escapeHtml(item.cycle)}" aria-pressed="${String(item.cycle) === String(state.cycle) ? 'true' : 'false'}" class="${String(item.cycle) === String(state.cycle) ? 'is-active' : ''}">${escapeHtml(item.cycle)}<small>${escapeHtml(item.cycle === '2026' ? '当前' : '历史')}</small></button>`).join('')}
      </div>
      <div class="exam-picker-group">
        ${examTypes.map((exam) => `<button type="button" data-maint-exam-filter="${escapeHtml(exam)}" aria-pressed="${exam === currentExam ? 'true' : 'false'}" class="${exam === currentExam ? 'is-active' : ''}">${escapeHtml(exam)}</button>`).join('')}
      </div>
      ${currentExam !== '全部' ? `<div class="exam-sub-group" role="group" aria-label="考试细分">${[["", "不细分"], ...(currentExam === '公务员' ? [["国考", "国考"], ["省考", "省考"]] : [["上半年", "上半年联考"], ["下半年", "下半年联考"]])].map(([value, label]) => `<button type="button" data-maint-exam-sub="${escapeHtml(value)}" class="${String(state.examSub || '') === String(value) ? 'is-active' : ''}">${escapeHtml(label)}</button>`).join('')}</div>` : ''}
    `;
  };
  const renderMobileNav = () => {
    if (!document.querySelector('[data-maint-mobile-nav]')) {
      app.insertAdjacentHTML('beforeend', `<nav class="maint-mobile-nav" data-maint-mobile-nav aria-label="移动端主导航"><a href="#overview" data-maintain-view="overview"><span aria-hidden="true">⌂</span><strong>${VIEW_META.overview.short}</strong></a><a href="#jobs_search" data-maintain-view="jobs_search"><span aria-hidden="true">⌕</span><strong>${VIEW_META.jobs_search.short}</strong></a><a href="#jobs_map" data-maintain-view="jobs_map"><span aria-hidden="true">⌁</span><strong>${VIEW_META.jobs_map.short}</strong></a><a href="#saved" data-maintain-view="saved"><span aria-hidden="true">☆</span><strong>${VIEW_META.saved.short}</strong></a><button type="button" data-maint-mobile-more-toggle aria-expanded="false"><span aria-hidden="true">•••</span><strong>更多</strong></button></nav>`);
    }
    if (!document.querySelector('[data-maint-mobile-more]')) {
      app.insertAdjacentHTML('beforeend', `<div class="maint-mobile-more" data-maint-mobile-more hidden><div class="maint-mobile-more__panel" role="dialog" aria-modal="true" aria-label="更多视图"><div class="maint-mobile-more__head"><strong>更多视图</strong><button type="button" data-maint-mobile-more-close aria-label="关闭更多视图">×</button></div><div class="maint-mobile-more__grid">${['match', 'cycle_compare', 'salary_map', 'jobs_ranking', 'calendar', 'help', 'changelog'].map((view) => `<a href="#${view}" data-maintain-view="${view}">${VIEW_META[view].full}</a>`).join('')}</div></div></div>`);
    }
    document.querySelectorAll('[data-maint-mobile-nav] [data-maintain-view], [data-maint-mobile-more] [data-maintain-view]').forEach((node) => {
      const active = node.dataset.maintainView === state.view;
      node.classList.toggle('is-active', active);
      if (active) node.setAttribute('aria-current', 'page'); else node.removeAttribute('aria-current');
    });
  };
  const closeMobileMore = () => {
    const menu = document.querySelector('[data-maint-mobile-more]');
    const trigger = document.querySelector('[data-maint-mobile-more-toggle]');
    if (menu) menu.hidden = true;
    trigger?.setAttribute('aria-expanded', 'false');
  };
  const renderNav = () => {
    renderCyclePicker();
    renderMobileNav();
    document.querySelectorAll('[data-maintain-view]').forEach((node) => node.classList.toggle('is-active', node.dataset.maintainView === state.view));
  };
  const sparkline = (trend, city, cycles) => {
    const values = (cycles || []).map((item) => Number(trend?.[city]?.posts?.[item.cycle])).filter((value) => Number.isFinite(value));
    if (values.length < 2) return '';
    const max = Math.max(...values); const min = Math.min(...values); const span = (max - min) || 1;
    const step = 26; const width = (values.length - 1) * step; const height = 12;
    const points = values.map((value, index) => `${(index * step).toFixed(1)},${(height - ((value - min) / span) * height).toFixed(1)}`).join(' ');
    return `<svg class="sparkline" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="${escapeHtml(cityDisplay(city))}三年趋势"><polyline pathLength="1" points="${points}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  };
  const deltaChip = (value, base) => {
    if (!base || !Number.isFinite(Number(value))) return '';
    const numeric = Number(value);
    return `<span class="delta-chip">${numeric >= 0 ? '▲' : '▼'} ${Math.abs(numeric).toFixed(1)}% <small>vs ${escapeHtml(base)}</small></span>`;
  };
  const renderOverview = (overview, jobs, derived) => {
    const exam = state.examFilter || '全部';
    const sub = state.examSub || '';
    const scopeLabel = exam === '全部' && !sub ? '全部' : `${exam}${sub ? ` · ${sub}` : ''}`;
    const examLabel = exam === '全部' && !sub ? '' : `（${scopeLabel}）`;
    const examRows = rowsFor(jobs);
    const examRecruits = examRows.reduce((sum, row) => sum + (Number(row?.num ?? row?.recruits ?? 0) || 0), 0);
    const examPayload = { allMajors: { rows: examRows } };
    const meta = metaFor(overview); const audit = overview.auditSummary || {}; const cities = aggregateCities(examPayload).sort((a, b) => b.jobs - a.jobs || b.recruits - a.recruits);
    const cycles = state.manifest?.cycles || [];
    const trend = derived?.city_trend || {};
    const vs = !((exam !== '全部') || sub) && derived?.vs_prev && derived.vs_prev.base_cycle ? derived.vs_prev : null;
    const mixMap = new Map();
    examRows.forEach((row) => {
      const examName = String(row?.exam || '未标注');
      const item = mixMap.get(examName) || { exam: examName, posts: 0, recruits: 0 };
      item.posts += 1;
      item.recruits += Number(row?.num ?? row?.recruits ?? 0) || 0;
      mixMap.set(examName, item);
    });
    const mixTotalRows = examRows.length || 1;
    const mix = [...mixMap.values()]
      .sort((a, b) => b.posts - a.posts || a.exam.localeCompare(b.exam, 'zh'))
      .map((item) => ({ ...item, post_share: Number((item.posts * 100 / mixTotalRows).toFixed(1)) }));
    const mixTotal = mix.reduce((sum, item) => sum + Number(item.posts || 0), 0) || 1;
    const mixColors = ['var(--viz-1)', 'var(--viz-2)', 'var(--viz-3)', 'var(--viz-4)', 'var(--accent-teal)'];
    let mixOffset = 0;
    const mixBar = mix.map((item, index) => {
      const width = Number(item.posts || 0) / mixTotal * 100; const left = mixOffset; mixOffset += width;
      return `<span class="mixbar__seg" style="left:${left.toFixed(2)}%;width:${width.toFixed(2)}%;background:${mixColors[index % mixColors.length]}" title="${escapeHtml(item.exam)} · ${number(item.posts)} 岗 · ${number(item.recruits)} 人"></span>`;
    }).join('');
    const mixLegend = mix.map((item, index) => `<span class="mixbar__legend"><i style="background:${mixColors[index % mixColors.length]}"></i>${escapeHtml(item.exam)} · ${number(item.posts)} 岗</span>`).join('');
    return `<section class="maint-hero"><div>${viewEyebrow('overview', `${escapeHtml(state.cycle)} · 年度概览${examLabel}`)}<h1>三年的岗位，一次摊开给你看</h1><p>省考、事业编、国考的岗位数、招录、竞争与成绩状态都在这里；每个数字都能回到来源、可核对，报与不报由你定。</p></div><div class="maint-hero__stamp"><span>周期证据层</span><strong>${escapeHtml(readableStatus(audit.evidence_level || '已构建'))}</strong><small>${number(audit.gap_count || 0)} 项公开边界 · ${number(audit.score_unresolved || 0)} 条待复核成绩</small></div></section><section class="bento" aria-label="周期关键指标"><article class="bento__cell bento__cell--metric"><span class="bento__label">全库岗位</span><strong class="bento__metric" data-countup>${number(exam === '全部' ? meta.total : examRows.length)}</strong>${deltaChip(vs?.jobs_delta_pct, vs?.base_cycle)}<small>${scopeLabel} · 当前周期岗位行</small></article><article class="bento__cell bento__cell--metric"><span class="bento__label">招录人数</span><strong class="bento__metric" data-countup>${number(exam === '全部' ? meta.recruits : examRecruits)}</strong>${deltaChip(vs?.recruits_delta_pct, vs?.base_cycle)}<small>${scopeLabel} · 公告口径合计</small></article><article class="bento__cell bento__cell--mix"><span class="bento__label">考试构成</span><div class="mixbar" role="img" aria-label="考试构成">${mixBar || '<span class="empty">—</span>'}</div><div class="mixbar__legends">${mixLegend || '—'}</div><small>按考试类别统计 · 可由岗位原始数据复算</small></article><article class="bento__cell bento__cell--note"><span class="bento__label">证据层</span><strong>${escapeHtml(readableStatus(audit.evidence_level || '已构建'))}</strong><small>${number(audit.gap_count || 0)} 项公开边界 · ${number(audit.score_unresolved || 0)} 条待复核成绩；未知不推断为零</small><a href="#data_boundary">打开数据审计 →</a></article></section><section class="maint-grid"><div class="maint-panel"><header><div><p class="maint-eyebrow">城市分布</p><h2>城市岗位分布</h2></div><a href="#jobs_ranking">打开岗位榜单 →</a></header><div class="city-list">${cities.slice(0, 8).map((item, index) => `<div class="city-row"><b>${String(index + 1).padStart(2, '0')}</b><span>${escapeHtml(cityDisplay(item.city))}</span><i><em style="width:${Math.min(100, item.jobs / Math.max(cities[0]?.jobs || 1, 1) * 100)}%"></em></i>${sparkline(trend, item.city, cycles)}<strong>${number(item.jobs)}</strong><small>${number(item.recruits)} 人</small></div>`).join('')}</div></div><aside class="maint-panel maint-panel--note"><p class="maint-eyebrow">数据说明</p><h2>数据边界公开</h2><p>本周期登记 ${number(audit.gap_count || 0)} 项边界；证据层、源文件和成绩安全留空均在“数据审计”中保留。</p><a class="maint-action" href="#data_boundary">打开数据审计 →</a><div class="aside-steps"><p class="maint-eyebrow">考生常用路径</p><ol><li><a href="#jobs_search">检索岗位</a> — 按专业、城市、学历筛出能报的</li><li><a href="#salary_map">查待遇地图</a> — 十六市全包年收入对比</li><li><a href="#saved">收藏与对比</a> — 把拿不准的留在一起慢慢比</li></ol></div></aside></section>`;
  };
  const mapMetricLabel = (metric) => metric === 'recruits' ? '招录人数' : metric === 'salary' ? '待遇' : '岗位数';
  const mapColor = (intensity) => ['var(--map-stop-0)', 'var(--map-stop-1)', 'var(--map-stop-2)', 'var(--map-stop-3)', 'var(--map-stop-4)', 'var(--map-stop-5)'][Math.min(5, Math.max(0, Math.round(Number(intensity || 0) * 5)))];
  const majorHit = (row, query) => {
    if (!query) return true;
    const q = normalize(query);
    if (!q) return true;
    return normalize(row?.zy).includes(q) || normalize(cleanMajorOption(row?.zy)).includes(q);
  };
  const aggregateMapCities = (payload, majorQuery = '') => {
    const buckets = new Map(prefectureCityOrder.map((city) => [city, { city, jobs: 0, recruits: 0, rows: 0, rawCities: new Set() }]));
    const direct = { city: '省直', jobs: 0, recruits: 0, rows: 0, rawCities: new Set(['省直']) };
    const unmapped = new Map();
    let totalRecruits = 0;
    let hitRows = 0;
    rowsFor(payload).forEach((row) => {
      if (!majorHit(row, majorQuery)) return;
      hitRows += 1;
      const rawCity = String(row?.city || row?.reg || '未标注').trim() || '未标注';
      const city = mapCityFor(rawCity);
      const target = city ? buckets.get(city) : rawCity === '省直' ? direct : null;
      const recruits = Number(row?.num || row?.recruits || 0);
      totalRecruits += Number.isFinite(recruits) ? recruits : 0;
      if (target) {
        target.jobs += 1;
        target.recruits += Number.isFinite(recruits) ? recruits : 0;
        target.rows += 1;
        target.rawCities.add(rawCity);
      } else {
        const item = unmapped.get(rawCity) || { city: rawCity, jobs: 0, recruits: 0 };
        item.jobs += 1;
        item.recruits += Number.isFinite(recruits) ? recruits : 0;
        unmapped.set(rawCity, item);
      }
    });
    const plain = (item) => ({ ...item, rawCities: [...item.rawCities] });
    const cities = prefectureCityOrder.map((city) => plain(buckets.get(city)));
    return { cities, direct: plain(direct), unmapped: [...unmapped.values()], sourceRows: hitRows, mappedRows: cities.reduce((sum, item) => sum + item.rows, 0) + direct.rows, totalRecruits };
  };
  const renderMap = (mapPayload, jobs, majorIndex = null) => {
    const majorQuery = String(state.mapMajor || '').trim();
    const majorApi = window.WanyuMajorCityIndex;
    const indexedKey = majorApi?.majorIndexKey?.(majorIndex, majorQuery) || '';
    const indexedSummary = indexedKey ? majorApi?.aggregateIndexedMajorCities?.(majorIndex, indexedKey) : null;
    const summary = indexedSummary || aggregateMapCities(jobs, majorQuery);
    const rowCount = jobs ? rowsFor(jobs).length : Number(majorIndex?.rows_total || 0);
    const byCity = new Map(summary.cities.map((item) => [item.city, item]));
    const salaryOn = state.mapMetric === 'salary' && !!state.salaryData && !majorQuery;
    const metric = salaryOn ? 'salary' : (state.mapMetric === 'recruits' ? 'recruits' : 'jobs');
    const salarySeries = (state.salaryData && state.salaryData.series && state.salaryData.series[state.salaryType]) || {};
    const salaryRaw = (city) => { const v = salarySeries[city] && salarySeries[city][state.salaryStage]; return (v === null || v === undefined) ? null : Number(v); };
    const valueFor = (item) => salaryOn ? salaryRaw(item.city) : Number(item[metric] || 0);
    const metricUnit = () => salaryOn ? '万' : metric === 'recruits' ? '人' : '岗';
    const valueText = (item) => { const v = valueFor(item); return salaryOn ? (v === null ? '未取得' : String(v)) : number(v); };
    const metricTip = (item) => { const v = valueFor(item); return salaryOn ? `${cityDisplay(item.city)} · ${state.salaryType} · ${state.salaryStage} · ${v === null ? '未取得' : `${v} 万元/年`}` : `${cityDisplay(item.city)} · ${number(item.jobs)} 岗 · 招录 ${number(item.recruits)} 人`; };
    const salaryValues = salaryOn ? summary.cities.map((item) => salaryRaw(item.city)).filter((v) => v !== null && Number.isFinite(v)) : [];
    const maximum = salaryOn
      ? Math.max(1, ...(salaryValues.length ? salaryValues : [1]))
      : Math.max(1, ...summary.cities.map((item) => Number(item[metric] || 0)));
    const meanValue = (() => { const nums = (salaryOn ? salaryValues : summary.cities.map((item) => Number(item[metric] || 0))).filter((v) => Number.isFinite(v)); return nums.length ? nums.reduce((sum, v) => sum + v, 0) / nums.length : 0; })();
    const isAboveMean = (item) => { const v = valueFor(item); return v !== null && Number.isFinite(v) && v >= meanValue; };
    const salaryButton = state.salaryData ? `<button type="button" data-maint-map-metric="salary" class="${metric === 'salary' ? 'is-active' : ''}" ${majorQuery ? 'disabled title="待遇是地市级估算口径，无法按专业拆分；清除专业筛选后可查看待遇"' : ''}>待遇</button>` : '';
    const majorCounts = new Map();
    rowsFor(jobs).forEach((row) => { const value = cleanMajorOption(row?.zy); if (isHumanMajor(value) && value.length <= 32) majorCounts.set(value, (majorCounts.get(value) || 0) + 1); });
    const majorOptions = indexedSummary ? (majorApi?.majorIndexOptions?.(majorIndex) || []) : [...majorCounts.entries()].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0]), 'zh'));
    const majorFilterUi = `<div class="maint-map-major"><label>专业关键词<input id="maint-map-major" list="maint-map-major-options" value="${escapeHtml(majorQuery)}" placeholder="输入专业，地图实时只看该专业的岗位分布" autocomplete="off"></label><datalist id="maint-map-major-options">${majorOptions.slice(0, 300).map(([value, count]) => `<option value="${escapeHtml(value)}" label="${number(count)} 岗"></option>`).join('')}</datalist><div class="maint-major-tools" aria-label="常用专业关键词"><span>常用专业</span>${majorOptions.slice(0, 12).map(([value, count]) => `<button type="button" data-maint-map-quick-major="${escapeHtml(value)}">${escapeHtml(value)}<small>${number(count)}岗</small></button>`).join('')}</div>${majorQuery ? `<button type="button" class="maint-row-action" data-maint-map-clear-major>清除专业筛选</button><span class="maint-toolbar__count">专业「${escapeHtml(majorQuery)}」命中 ${number(summary.sourceRows)} / ${number(rowCount)} 行</span>` : '<span class="maint-filter-hint">按岗位表专业原文关键词命中；未筛选时统计全部岗位</span>'}</div>`;
    const salaryControls = salaryOn ? `<div class="maint-map-salary-controls" role="group" aria-label="待遇口径"><span class="maint-map-salary-controls__grp"><span class="maint-map-salary-controls__label">身份</span>${(state.salaryData.employment_types || []).map((t) => `<button type="button" data-maint-salary-type="${escapeHtml(t)}" class="${state.salaryType === t ? 'is-active' : ''}">${escapeHtml(t)}</button>`).join('')}</span><span class="maint-map-salary-controls__grp"><span class="maint-map-salary-controls__label">工龄</span>${(state.salaryData.stages || []).map((st) => `<button type="button" data-maint-salary-stage="${escapeHtml(st)}" class="${state.salaryStage === st ? 'is-active' : ''}">${escapeHtml(st)}</button>`).join('')}</span><p class="maint-map-salary-note">${escapeHtml(state.salaryData.note || '待遇为 2026 快照的全包估算中位数（万元/年），非官方逐岗工资，不代表 2024/2025。')}</p></div>` : '';
    const selected = state.mapCity === '省直' ? summary.direct : byCity.get(state.mapCity) || null;
    const selectedName = selected ? cityDisplay(selected.city) : '全省十六市';
    const featureMarkup = mapPayload.features.map((feature, index) => {
      const item = byCity.get(String(feature.city)) || { city: String(feature.city), jobs: 0, recruits: 0, rows: 0, rawCities: [] };
      const raw = valueFor(item);
      const value = raw === null ? 0 : raw;
      const selectedClass = state.mapCity === item.city ? ' is-selected' : '';
      return `<path class="maint-map-region${selectedClass}" data-maint-map-region data-maint-map-city="${escapeHtml(item.city)}" role="button" tabindex="0" aria-pressed="${state.mapCity === item.city ? 'true' : 'false'}" pathLength="1" style="--map-fill:${mapColor(value / maximum)};--map-delay:${index * 22}ms" d="${escapeHtml(feature.d)}"><title>${escapeHtml(metricTip(item))}</title></path>`;
    }).join('');
    const labelMarkup = mapPayload.features.map((feature) => {
      const city = String(feature.city); const item = byCity.get(city) || { city, jobs: 0, recruits: 0 }; const selectedClass = state.mapCity === city ? ' is-selected' : '';
      return `<g class="maint-map-label${selectedClass}" data-maint-map-city="${escapeHtml(city)}" aria-hidden="true"><text x="${Number(feature.x).toFixed(1)}" y="${Number(feature.y).toFixed(1)}">${escapeHtml(city)}</text><text class="maint-map-label__value" x="${Number(feature.x).toFixed(1)}" y="${(Number(feature.y) + 16).toFixed(1)}">${valueText(item)} ${metricUnit()}</text></g>`;
    }).join('');
    const rawCities = selected?.rawCities?.filter(Boolean) || [];
    const returnAll = '<button type="button" class="maint-action" data-maint-map-city="">← 返回全省汇总</button>';
    const selectedDetails = selected ? `<p class="maint-map-inspector__city">${escapeHtml(selectedName)}</p><div class="maint-map-inspector__number"><strong>${salaryOn ? valueText(selected) : number(selected[metric])}</strong><span>${salaryOn ? `待遇 · ${escapeHtml(state.salaryType)} ${escapeHtml(state.salaryStage)} · 万元/年` : escapeHtml(mapMetricLabel(metric))}</span></div><dl class="maint-map-facts"><div><dt>岗位行</dt><dd>${number(selected.jobs)}</dd></div><div><dt>招录人数</dt><dd>${number(selected.recruits)}</dd></div><div><dt>原始城市值</dt><dd>${escapeHtml(rawCities.join('、') || '—')}</dd></div></dl>${selected.city === '省直' ? `<p class="maint-map-note">省直是省级直属岗位口径，不属于十六市行政区，单独保留，不伪造为“省直市”。待遇为地市级估算，省直不纳入。${returnAll}` : `<button type="button" class="maint-primary-action" data-maint-map-open-city="${escapeHtml(selected.city)}">在岗位检索中查看 ${escapeHtml(cityDisplay(selected.city))} →</button>${returnAll}`}` : `<p class="maint-map-inspector__city">全省 · 十六市 + 省直</p><div class="maint-map-inspector__number"><strong>${salaryOn ? String(Math.round(meanValue * 100) / 100) : number(metric === 'recruits' ? summary.totalRecruits : summary.sourceRows)}</strong><span>${salaryOn ? `待遇均值 · ${escapeHtml(state.salaryType)} ${escapeHtml(state.salaryStage)} · 万元/年` : escapeHtml(mapMetricLabel(metric))}</span></div><dl class="maint-map-facts"><div><dt>岗位行</dt><dd>${number(summary.sourceRows)}</dd></div><div><dt>招录人数</dt><dd>${number(summary.totalRecruits)}</dd></div><div><dt>已定位到行政区</dt><dd>${number(summary.mappedRows)} / ${number(summary.sourceRows)}</dd></div></dl><p class="maint-map-note">${salaryOn ? '十六市待遇均值，来自 2026 快照的全包估算中位数，非官方逐岗工资；点击城市查看该市待遇。' : '未选择城市时显示全省汇总；点击地图区域、城市标签或下方城市卡查看单市数据和原始城市值，再次点击已选城市可返回全省。'}</p>`;
    const unmappedText = summary.unmapped.length ? `仍有 ${number(summary.unmapped.reduce((sum, item) => sum + item.jobs, 0))} 行城市值未能归入十六市，页面没有静默丢弃：${escapeHtml(summary.unmapped.map((item) => `${item.city} ${item.jobs}岗`).join('、'))}。` : '当前周期所有岗位行均已归入十六市或省直独立口径。';
    const chips = summary.cities.map((item) => {
      const aboveMean = isAboveMean(item);
      return `<button type="button" class="maint-map-city-chip${state.mapCity === item.city ? ' is-selected' : ''}${aboveMean ? ' is-above-mean' : ''}" data-maint-map-city="${escapeHtml(item.city)}" title="${aboveMean ? '高于十六市均值' : '低于十六市均值'}"><span>${escapeHtml(cityDisplay(item.city))}</span><strong>${valueText(item)}</strong><small>${metricUnit()}</small></button>`;
    }).join('');
    return `${state.notice ? `<div class="maint-inline-notice" role="status">${escapeHtml(state.notice)}</div>` : ''}<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('jobs_map', `${escapeHtml(state.cycle)} · CITY MAP`)}<h1>岗位地图，先看地域，再回到岗位。</h1><p>真实安徽十六市边界；数字按当前周期岗位实时汇总，可用下方专业关键词筛选——比如输入“法学”，地图就只统计各地市含法学的岗位。省直单独保留，未知城市不会硬算进某个市。</p></div><div class="maint-hero__stamp"><span>地图数据层</span><strong>16 市 + 省直</strong><small>${majorQuery ? `专业「${escapeHtml(majorQuery)}」· ` : ''}真实市界 · ${number(summary.sourceRows)} 行实时汇总</small></div></section><section class="maint-panel maint-map-workbench"><header class="maint-map-toolbar"><div><p class="maint-eyebrow">地图视角</p><h2>${escapeHtml(mapMetricLabel(metric))}热力${majorQuery ? ' · 按专业筛选' : ''}</h2></div><div class="maint-map-metric-toggle" role="group" aria-label="地图指标"><button type="button" data-maint-map-metric="jobs" class="${metric === 'jobs' ? 'is-active' : ''}">岗位数</button><button type="button" data-maint-map-metric="recruits" class="${metric === 'recruits' ? 'is-active' : ''}">招录人数</button>${salaryButton}</div>${salaryControls}<a class="maint-action" href="#jobs_ranking" data-maintain-view="jobs_ranking">打开岗位榜单 →</a>${majorFilterUi}</header><div class="maint-map-layout"><div class="maint-map-canvas"><div class="maint-map-legend"><span>少</span><i></i><span>多</span><small>按${escapeHtml(mapMetricLabel(metric))}归一化</small></div><svg id="maint-map" class="maint-map-svg" viewBox="0 0 640 660" role="group" aria-labelledby="maint-map-title maint-map-desc"><title id="maint-map-title">${escapeHtml(state.cycle)} 年安徽十六市岗位地图</title><desc id="maint-map-desc">地图颜色按${escapeHtml(mapMetricLabel(metric))}从低到高变化；点击市级区域、城市标签或下方城市卡查看汇总。</desc><g class="maint-map-regions">${featureMarkup}</g><g class="maint-map-labels">${labelMarkup}</g></svg><details class="maint-source-details"><summary>查看地图数据来源</summary><p class="maint-map-source">几何源：<code>tools/anhui_web/data/anhui_340000_full.json</code> · 展示模块：<code>data/map/anhui.json</code></p></details></div><aside class="maint-map-inspector" data-maint-map-inspector><p class="maint-eyebrow">城市详情</p>${selectedDetails}</aside></div></section><section class="maint-panel maint-map-city-panel"><header><div><p class="maint-eyebrow">城市列表</p><h2>十六市与省直</h2></div><span class="maint-audit-date">${number(summary.mappedRows)} / ${number(summary.sourceRows)} 行已定位</span></header><div class="maint-map-city-grid">${chips}<button type="button" class="maint-map-city-chip maint-map-city-chip--direct${state.mapCity === '省直' ? ' is-selected' : ''}" data-maint-map-city="省直"><span>省直</span><strong>${salaryOn ? '—' : number(summary.direct[metric])}</strong><small>${metricUnit()}</small></button></div></section><section class="maint-callout"><strong>定位边界</strong><span>${unmappedText} 2024 年原始表含区县、市直、宿松、广德等城市值，地图仅做行政区级导航汇总；岗位详情仍以原始岗位表为准。</span></section>`;
  };
  const renderSalaryMap = () => {
    if (!state.salaryData) {
      return `<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('salary_map', '待遇 · 2026 快照')}<h1>待遇地图</h1><p>本发布包未附带待遇数据模块（<code>data/salary/anhui.json</code>）。</p></div></section><section class="maint-panel"><p class="empty">暂无待遇数据可展示。该模块仅覆盖十六市地市级 2026 快照估算，缺失时保持空值不推断为零。</p></section>`;
    }
    const sd = state.salaryData;
    const series = (sd.series && sd.series[state.salaryType]) || {};
    const salaryOf = (city) => { const v = series[city] && series[city][state.salaryStage]; return (v === null || v === undefined) ? null : Number(v); };
    const entries = prefectureCityOrder.map((city) => ({ city, value: salaryOf(city) }));
    const finite = entries.map((entry) => entry.value).filter((v) => v !== null && Number.isFinite(v));
    const maximum = finite.length ? Math.max(...finite) : 0;
    const minimum = finite.length ? Math.min(...finite) : 0;
    const span = maximum - minimum;
    const mean = finite.length ? finite.reduce((sum, v) => sum + v, 0) / finite.length : 0;
    const intensity = (v) => v === null || !Number.isFinite(v) ? 0 : (span <= 0 ? 0.6 : (v - minimum) / span);
    const mapData = state.mapData;
    const legendNote = `${escapeHtml(state.salaryType)} · ${escapeHtml(state.salaryStage)} · ${escapeHtml(sd.unit || '万元/年')}`;
    const regionMarkup = mapData ? mapData.features.map((feature, index) => {
      const city = String(feature.city); const v = salaryOf(city); const sel = state.mapCity === city ? ' is-selected' : '';
      return `<path class="maint-map-region${sel}" data-maint-map-region data-maint-map-city="${escapeHtml(city)}" role="button" tabindex="0" aria-pressed="${state.mapCity === city ? 'true' : 'false'}" pathLength="1" style="--map-fill:${mapColor(intensity(v))};--map-delay:${index * 22}ms" d="${escapeHtml(feature.d)}"><title>${escapeHtml(`${cityDisplay(city)} · ${v === null ? '未取得' : `${v} ${sd.unit || '万元/年'}`}`)}</title></path>`;
    }).join('') : '';
    const labelMarkup = mapData ? mapData.features.map((feature) => {
      const city = String(feature.city); const v = salaryOf(city); const sel = state.mapCity === city ? ' is-selected' : '';
      return `<g class="maint-map-label${sel}" data-maint-map-city="${escapeHtml(city)}" aria-hidden="true"><text x="${Number(feature.x).toFixed(1)}" y="${Number(feature.y).toFixed(1)}">${escapeHtml(city)}</text><text class="maint-map-label__value" x="${Number(feature.x).toFixed(1)}" y="${(Number(feature.y) + 16).toFixed(1)}">${v === null ? '未取得' : `${v} 万`}</text></g>`;
    }).join('') : '';
    const controls = `<div class="maint-map-salary-controls" role="group" aria-label="待遇口径"><span class="maint-map-salary-controls__grp"><span class="maint-map-salary-controls__label">身份</span>${(sd.employment_types || []).map((t) => `<button type="button" data-maint-salary-type="${escapeHtml(t)}" class="${state.salaryType === t ? 'is-active' : ''}">${escapeHtml(t)}</button>`).join('')}</span><span class="maint-map-salary-controls__grp"><span class="maint-map-salary-controls__label">工龄</span>${(sd.stages || []).map((st) => `<button type="button" data-maint-salary-stage="${escapeHtml(st)}" class="${state.salaryStage === st ? 'is-active' : ''}">${escapeHtml(st)}</button>`).join('')}</span></div>`;
    const selected = state.mapCity && prefectureCities.has(state.mapCity) ? { city: state.mapCity, value: salaryOf(state.mapCity) } : null;
    const stageSeries = (city) => (sd.stages || []).map((st) => { const v = (sd.series[state.salaryType]?.[city] || {})[st]; return Number.isFinite(Number(v)) ? Number(v) : null; });
    const curveValues = selected ? stageSeries(selected.city) : (sd.stages || []).map((st, idx) => { const nums = prefectureCityOrder.map((c) => stageSeries(c)[idx]).filter((v) => v !== null); return nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : null; });
    const curveSvg = (() => {
      const nums = curveValues.filter((v) => v !== null && Number.isFinite(v));
      if (nums.length < 2) return '';
      const max = Math.max(...nums); const min = Math.min(...nums); const span = (max - min) || 1;
      const step = 30; const width = (curveValues.length - 1) * step; const height = 26;
      const pt = (v, i) => `${(i * step).toFixed(1)},${(height - ((v - min) / span) * (height - 6) - 3).toFixed(1)}`;
      const line = curveValues.map((v, i) => v === null ? '' : pt(v, i)).join(' ');
      const dots = curveValues.map((v, i) => v === null ? '' : `<circle cx="${(i * step).toFixed(1)}" cy="${height - ((v - min) / span) * (height - 6) - 3}" r="2.2" fill="var(--viz-3)"/>`).join('');
      return `<svg class="maint-salary-curve" viewBox="0 0 ${width} ${height}" width="100%" height="${height}" preserveAspectRatio="none" role="img" aria-label="工龄梯度曲线"><polyline points="${line}" fill="none" stroke="var(--viz-3)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>${dots}</svg>`;
    })();
    const curveBlock = curveSvg ? `<div class="maint-salary-curve-wrap"><p class="maint-salary-curve-cap">${selected ? `${escapeHtml(cityDisplay(selected.city))} 工龄梯度 · ${escapeHtml(state.salaryType)}` : `十六市均值 · ${escapeHtml(state.salaryType)}`}<span>（${escapeHtml(sd.unit || '万元/年')}）</span></p>${curveSvg}<div class="maint-salary-curve-axis">${(sd.stages || []).map((st) => `<span>${escapeHtml(st)}</span>`).join('')}</div></div>` : '';
    const rankMax = maximum || 1;
    const rank = [...entries].sort((a, b) => (b.value === null ? -1 : b.value) - (a.value === null ? -1 : a.value));
    const rankRows = rank.map((entry, index) => `<div class="city-row city-row--clickable${state.mapCity === entry.city ? ' is-selected' : ''}" data-maint-map-city="${escapeHtml(entry.city)}" role="button" tabindex="0"><b>${String(index + 1).padStart(2, '0')}</b><span>${escapeHtml(cityDisplay(entry.city))}</span><i><em style="width:${entry.value === null ? 0 : Math.max(3, entry.value / rankMax * 100)}%"></em></i><strong>${entry.value === null ? '—' : entry.value}</strong><small>万</small></div>`).join('');
    const svgBlock = mapData ? `<svg id="maint-map" class="maint-map-svg" viewBox="0 0 640 660" role="group" aria-label="安徽十六市待遇热力图"><g class="maint-map-regions">${regionMarkup}</g><g class="maint-map-labels">${labelMarkup}</g></svg>` : '<p class="empty">地图几何未加载</p>';
    return `<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('salary_map', '待遇 · 2026 快照')}<h1>待遇地图 · 各地市全包年收入</h1><p>${escapeHtml(sd.note || '待遇为 2026 快照的年度全包估算中位数（万元/年），非官方逐岗工资，不代表 2024/2025。')}</p><a class="maint-action" href="#jobs_map" data-maintain-view="jobs_map">← 返回岗位地图</a></div><div class="maint-hero__stamp"><span>口径</span><strong>${escapeHtml(sd.metric || '年度全包估算中位数')}</strong><small>${legendNote}</small></div></section><section class="maint-panel maint-map-workbench"><header class="maint-map-toolbar"><div><p class="maint-eyebrow">待遇热力</p><h2>十六市待遇热力</h2></div>${controls}</header><div class="maint-map-layout"><div class="maint-map-canvas"><div class="maint-map-legend"><span>${finite.length ? minimum.toFixed(1) : '低'}</span><i></i><span>${finite.length ? maximum.toFixed(1) : '高'}</span><small>按${escapeHtml(state.salaryType)} ${escapeHtml(state.salaryStage)}归一化</small></div>${svgBlock}<details class="maint-source-details"><summary>查看待遇数据来源</summary><p class="maint-map-source">待遇源：<code>${escapeHtml(sd.source_module || 'source_docs 全包分析')}</code> · 展示模块：<code>data/salary/anhui.json</code> · 几何：<code>data/map/anhui.json</code></p></details></div><aside class="maint-map-inspector" data-maint-map-inspector><p class="maint-eyebrow">城市详情</p><p class="maint-map-inspector__city">${selected ? escapeHtml(cityDisplay(selected.city)) : '全省 · 十六市均值'}</p><div class="maint-map-inspector__number"><strong>${selected ? (selected.value === null ? '未取得' : selected.value) : (finite.length ? mean.toFixed(2) : '—')}</strong><span>${selected ? `待遇 · ${escapeHtml(state.salaryType)} ${escapeHtml(state.salaryStage)} · ${escapeHtml(sd.unit || '万元/年')}` : `十六市均值 · ${escapeHtml(sd.unit || '万元/年')}`}</span></div>${curveBlock}<p class="maint-map-note">${selected ? `点击地图区域、城市标签或右侧排行榜查看该市待遇；${escapeHtml(cityDisplay(selected.city))} 当前口径${selected.value === null ? '未取得' : `约 ${selected.value} 万元/年`}。` : '点击地图区域、城市标签或右侧排行榜查看该市待遇。均值随身份/工龄切换重算。'}</p></aside></div></section><section class="maint-panel"><header><div><p class="maint-eyebrow">待遇排行</p><h2>十六市待遇排行</h2></div><span class="maint-audit-date">${escapeHtml(sd.snapshot || '2026')} 快照 · 单位 ${escapeHtml(sd.unit || '万元/年')}</span></header><div class="city-list">${rankRows}</div></section><section class="maint-callout"><strong>口径提示</strong><span>待遇为 ${escapeHtml(sd.snapshot || '2026')} 快照的全包估算中位数，不随报考周期变化，非官方逐岗工资或个人收入承诺；与岗位数、招录人数分母不同，不可混读。省直不属于十六市行政区，不纳入待遇估算。</span></section>`;
  };
  const changeStatusLabel = (status) => ({ added: '新增', withdrawn: '撤回', revised: '字段变更', unchanged: '保持', needs_review: '待复核' }[String(status)] || status);
  const matchingPolicyLabel = (value) => ({ exact_code: '职位代码精确匹配', composite_exact: '考试/城市/代码组合匹配', semantic_candidate_requires_review: '语义候选仅进入待复核' }[String(value)] || String(value || '未说明'));
  const scopedRowsForCycle = (cycle) => {
    const jobs = state.modules.get(`${cycle}:jobs`);
    return rowsFor(jobs).filter((row) => examRowMatches(row, state.examFilter || '全部', state.examSub || ''));
  };
  const changeSummaryForScope = (payload) => {
    const summary = { added: 0, withdrawn: 0, revised: 0, unchanged: 0, needs_review: 0 };
    const changes = Array.isArray(payload?.changes) ? payload.changes : [];
    const scoped = (state.examFilter || '全部') !== '全部' || Boolean(state.examSub);
    if (!scoped) return payload?.summary || summary;
    const baseRows = new Map(rowsFor(state.modules.get(`${payload.base_cycle}:jobs`)).map((row) => [String(row.job_id || row.row_id || row.code || ''), row]));
    const targetRows = new Map(rowsFor(state.modules.get(`${payload.target_cycle}:jobs`)).map((row) => [String(row.job_id || row.row_id || row.code || ''), row]));
    changes.forEach((change) => {
      const candidate = targetRows.get(String(change.target_record_id || '')) || baseRows.get(String(change.base_record_id || ''));
      if (!candidate || !examRowMatches(candidate, state.examFilter || '全部', state.examSub || '')) return;
      const status = String(change.status || 'needs_review');
      if (Object.prototype.hasOwnProperty.call(summary, status)) summary[status] += 1;
      else summary.needs_review += 1;
    });
    return summary;
  };
  const slopeGraph = (trend, cycles, examFilter = '全部', examSub = '') => {
    // 如果有筛选，需要从jobs数据重新计算
    let filteredTrend = trend;
    if ((examFilter !== '全部' || examSub) && state.modules) {
      filteredTrend = {};
      // 从各周期的jobs数据中按考试类别统计
      for (const cycle of cycles) {
        const jobsData = state.modules.get(`${cycle.cycle}:jobs`);
        if (!jobsData) continue;
        const rows = rowsFor(jobsData);
        rows.forEach(row => {
          const city = trendCityKey(row.city || row.reg);
          if (!city) return;
          
          // 判断是否匹配筛选条件（公务员 = 省考 + 国考）
          const match = examRowMatches(row, examFilter, examSub);
          
          if (match) {
            if (!filteredTrend[city]) filteredTrend[city] = { posts: {}, recruits: {} };
            if (!filteredTrend[city].posts[cycle.cycle]) filteredTrend[city].posts[cycle.cycle] = 0;
            if (!filteredTrend[city].recruits[cycle.cycle]) filteredTrend[city].recruits[cycle.cycle] = 0;
            filteredTrend[city].posts[cycle.cycle] += 1;
            filteredTrend[city].recruits[cycle.cycle] += Number(row.num ?? row.recruits ?? 0);
          }
        });
      }
    }

    const cities = Object.keys(filteredTrend || {});
    if (cities.length < 1 || cycles.length < 2) return '';

    // 按最新周期岗位数排序
    const latestCycle = cycles[cycles.length - 1]?.cycle;
    const sortedCities = Object.keys(filteredTrend).sort((a, b) => {
      const aVal = Number(filteredTrend[a]?.posts?.[latestCycle]) || 0;
      const bVal = Number(filteredTrend[b]?.posts?.[latestCycle]) || 0;
      return bVal - aVal;
    });

    // 生成表格
    const headerRow = cycles.map(c => `<th>${c.cycle}年</th>`).join('');
    const rows = sortedCities.map(city => {
      const cells = cycles.map(c => {
        const val = Number(filteredTrend[city]?.posts?.[c.cycle]);
        const scoped = (examFilter && examFilter !== '全部') || Boolean(examSub);
        return `<td>${Number.isFinite(val) ? number(val) : (scoped ? '<span class="no-data" title="该年度暂无此类别公开数据，不代表未招录">暂无数据</span>' : '—')}</td>`;
      }).join('');
      // 计算变化
      const first = Number(filteredTrend[city]?.posts?.[cycles[0]?.cycle]);
      const last = Number(filteredTrend[city]?.posts?.[cycles[cycles.length - 1]?.cycle]);
      let change = '';
      if (Number.isFinite(first) && Number.isFinite(last) && first > 0) {
        const pct = ((last - first) / first * 100).toFixed(1);
        change = pct > 0 ? `<span style="color:var(--pos)">+${pct}%</span>` : pct < 0 ? `<span style="color:var(--danger)">${pct}%</span>` : '持平';
      }
      return `<tr><th>${escapeHtml(cityDisplay(city))}</th>${cells}<td>${change}</td></tr>`;
    }).join('');

    return `<div class="table-scroll"><table class="maint-table"><thead><tr><th>城市</th>${headerRow}<th>三年变化</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  };
  const renderCompare = (changePayloads = [], derived = null) => {
    const pairs = changePayloads.filter((payload) => payload?.base_cycle).map((payload) => {
      const summary = changeSummaryForScope(payload);
      const changed = Number(summary.revised || 0) + Number(summary.added || 0) + Number(summary.withdrawn || 0);
      const policies = (payload.matching_policy || []).map(matchingPolicyLabel);
      const scopedLabel = (state.examFilter || '全部') === '全部' && !state.examSub ? '全周期' : `${state.examFilter}${state.examSub ? ` · ${state.examSub}` : ''}`;
      return `<article class="change-card" data-maint-comparison-row><div class="change-card__head"><div><p class="maint-eyebrow">${escapeHtml(payload.base_cycle)} → ${escapeHtml(payload.target_cycle)}</p><h3>${escapeHtml(payload.target_cycle)} 年度变化 · ${escapeHtml(scopedLabel)}</h3></div><span class="audit-chip ${payload.comparable ? 'audit-chip--good' : 'audit-chip--warn'}">${payload.comparable ? '口径一致 · 可比' : '口径不同 · 不可比'}</span></div><div class="change-card__metric"><strong>${number(changed)}</strong><span>条岗位信息有变化</span></div><div class="change-card__stats"><span><b>${number(summary.added || 0)}</b>新增</span><span><b>${number(summary.withdrawn || 0)}</b>撤回</span><span><b>${number(summary.revised || 0)}</b>信息修订</span><span><b>${number(summary.needs_review || 0)}</b>待人工复核</span></div><details class="maint-source-details"><summary>查看对比口径</summary><p class="change-card__note">${escapeHtml(policies.join(' · ') || '未说明')}。只统计能确认的岗位变化，无法确认的不强行归类。</p></details></article>`;
    }).join('');
    const scoped = (state.examFilter || '全部') !== '全部' || Boolean(state.examSub);
    const cycleRows = (state.manifest?.cycles || []).map((item) => {
      const rows = scopedRowsForCycle(item.cycle);
      const posts = scoped ? rows.length : Number(item.posts || 0);
      const recruits = scoped ? rows.reduce((sum, row) => sum + (Number(row.num ?? row.recruits ?? 0) || 0), 0) : Number(item.recruits || 0);
      return `<tr><th>${escapeHtml(item.cycle)}</th><td>${number(posts)}</td><td>${number(recruits)}</td><td>${number(item.gaps)}</td><td>${number(item.score_unresolved)}</td><td><details class="maint-source-details"><summary>外置岗位模块</summary><code>${escapeHtml(item.modules?.jobs?.data || item.data)}</code></details></td></tr>`;
    }).join('');
    const slope = slopeGraph(derived?.city_trend || {}, state.manifest?.cycles || [], state.examFilter || '全部', state.examSub || '');
    const examLabel = state.examFilter === '全部' && !state.examSub ? '' : `（${state.examFilter}${state.examSub ? ` · ${state.examSub}` : ''}）`;
    const scopeNote = scoped ? '岗位数与招录人数按当前考试细分重新汇总；公开缺口与待复核成绩属于周期级证据，不随考试筛选。' : '岗位数与招录人数为周期全量；公开缺口与待复核成绩属于周期级证据。';
    return `<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('cycle_compare', '三年数据对比')}<h1>三年岗位数据对比</h1><p>查看各城市2024-2026年岗位数变化趋势，了解招录形势。</p></div></section>${slope ? `<section class="maint-panel"><header><div><h2>各城市岗位数三年对比${examLabel}</h2></div></header>${slope}</section>` : ''}<section class="maint-grid maint-grid--compare" data-maint-change-summary>${pairs || '<div class="maint-panel"><p class="empty">当前没有可比较的数据。</p></div>'}</section><section class="maint-panel"><header><div><h2>三年数据概况${examLabel}</h2><p class="maint-filter-hint">${scopeNote}</p></div></header><div class="table-scroll"><table class="maint-table" data-maint-cycle-summary><thead><tr><th>年份</th><th>岗位数</th><th>招录人数</th><th>公开缺口（周期级）</th><th>待复核成绩（周期级）</th><th>证据模块</th></tr></thead><tbody>${cycleRows}</tbody></table></div></section><div id="v17-tools-container"></div>`;
  };
  // —— 变更通报视图（#changes）：消费 changes.json 的逐岗 diff，轻量展示，最多渲染 200 条 ——
  const changesFieldLabel = (field) => ({ recruits: '招录人数', num: '招录人数', zy: '专业要求', major: '专业要求', xl: '学历', xw: '学位', xz: '政治面貌', age: '年龄要求', unit: '单位', post_name: '职位名称', zw: '职位名称', category: '岗位类别', lb: '岗位类别', code: '职位代码', city: '城市', exam: '考试类别', bz: '备注' }[String(field)] || String(field || '—'));
  const changesStatusMeta = (status) => ({
    added: { label: '新增', tone: 'added' },
    withdrawn: { label: '撤回', tone: 'withdrawn' },
    revised: { label: '信息修订', tone: 'revised' },
    needs_review: { label: '待人工复核', tone: 'needs_review' },
    unchanged: { label: '保持', tone: 'unchanged' },
  }[String(status)] || { label: String(status || '—'), tone: 'unchanged' });
  const changesMethodText = (value) => ({ exact_code: '职位代码精确匹配', composite_exact: '考试/城市/代码组合匹配', semantic_candidate: '按单位与职位名称近似对比，仅提示、不下结论', added: '两年职位表逐岗对比后新出现', withdrawn: '两年职位表逐岗对比后未再出现' }[String(value)] || matchingPolicyLabel(value));
  const changesFilterOptions = [['all', '全部'], ['added', '新增'], ['withdrawn', '撤回'], ['revised', '信息修订'], ['needs_review', '待人工复核']];
  const CHANGES_LIST_LIMIT = 200;
  const renderChanges = (changes) => {
    if (!changes) {
      return `<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('changes', '职位表变更通报')}<h1>职位表变更通报</h1><p>当前周期没有已登记的两年职位表逐岗对比结果；切换到有对比数据的周期即可查看。</p></div></section><section class="maint-panel"><p class="empty">当前周期没有变更通报数据。</p></section>`;
    }
    const summary = changes.summary || {};
    const all = Array.isArray(changes.changes) ? changes.changes : [];
    const filterValue = changesFilterOptions.some(([value]) => value === state.changesFilter) ? state.changesFilter : 'all';
    const filtered = filterValue === 'all' ? all : all.filter((item) => String(item?.status || '') === filterValue);
    const visible = filtered.slice(0, CHANGES_LIST_LIMIT);
    const truncated = filtered.length > visible.length;
    const baseCycle = String(changes.base_cycle || '2025');
    const targetCycle = String(changes.target_cycle || state.cycle || '2026');
    const filterLabel = (changesFilterOptions.find(([value]) => value === filterValue) || changesFilterOptions[0])[1];
    const chips = changesFilterOptions.map(([value, label]) => `<button type="button" data-maint-changes-filter="${value}" class="${filterValue === value ? 'is-active' : ''}" aria-pressed="${filterValue === value ? 'true' : 'false'}">${label}</button>`).join('');
    const recordText = (item) => {
      const base = String(item?.base_record_id || '');
      const target = String(item?.target_record_id || '');
      if (item?.status === 'added' && target) return `${escapeHtml(targetCycle)} 岗位记录 · <code>${escapeHtml(target)}</code>`;
      if (item?.status === 'withdrawn' && base) return `${escapeHtml(baseCycle)} 岗位记录 · <code>${escapeHtml(base)}</code>`;
      if (base && target) return `<code>${escapeHtml(base)}</code> → <code>${escapeHtml(target)}</code>`;
      return `<code>${escapeHtml(base || target || '记录编号未提供')}</code>`;
    };
    const items = visible.map((item) => {
      const meta = changesStatusMeta(item?.status);
      const fields = Array.isArray(item?.changed_fields) ? item.changed_fields.map(changesFieldLabel).join('、') : '';
      const fieldText = fields || (String(item?.status) === 'revised' ? '字段原文以两年职位表为准' : '无单字段差异');
      const candidates = Array.isArray(item?.candidate_record_ids) ? item.candidate_record_ids.length : 0;
      return `<article class="review-item"><div class="review-item__meta"><span class="maint-changes-badge" data-tone="${meta.tone}">${escapeHtml(meta.label)}</span><span>${escapeHtml(baseCycle)} → ${escapeHtml(targetCycle)}</span></div><strong>${recordText(item)}</strong><p>变化字段：${escapeHtml(fieldText)}</p><small>对比方式：${escapeHtml(changesMethodText(item?.match_method))}${candidates ? ` · 有 ${number(candidates)} 个近似候选，无法唯一对应，请以官方公告为准` : ''}</small></article>`;
    }).join('');
    return `<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('changes', `${escapeHtml(baseCycle)} → ${escapeHtml(targetCycle)} · 两年职位表逐岗对比`)}<h1>职位表变更通报</h1><p>${escapeHtml(baseCycle)} → ${escapeHtml(targetCycle)} 两年职位表逐岗对比；只显示能确定的字段变化，无法唯一对应的岗位单独标出、不下结论。</p></div><div class="maint-hero__stamp"><span>数据说明</span><strong>${number(all.length)} 条逐岗对比</strong><small>只显示能确定的字段变化</small></div></section><section class="maint-callout"><strong>免责说明</strong><span>变化由两年职位表逐岗对比得出，报考资格以当年官方公告为准。</span></section><section class="maint-kpis maint-kpis--audit" aria-label="变更汇总"><article><span>新增</span><strong data-countup>${number(summary.added || 0)}</strong><small>两年对比后新出现的岗位</small></article><article><span>撤回</span><strong>${number(summary.withdrawn || 0)}</strong><small>上年有、今年职位表未再出现</small></article><article><span>信息修订</span><strong>${number(summary.revised || 0)}</strong><small>同一岗位的字段内容有变化</small></article><article><span>待人工复核</span><strong>${number(summary.needs_review || 0)}</strong><small>无法唯一对应，不做判定</small></article></section><section class="maint-panel"><header><div><p class="maint-eyebrow">状态筛选</p><h2>按变更类型查看</h2></div><span class="maint-toolbar__count">${escapeHtml(filterLabel)} · 共 ${number(filtered.length)} 条${truncated ? ` · 当前显示前 ${number(visible.length)} 条` : ''}</span></header><div class="review-filters" role="group" aria-label="变更状态筛选">${chips}</div><div class="review-list">${items || '<p class="empty">当前筛选没有变更记录。</p>'}</div>${truncated ? `<p class="maint-detail-footnote">变更较多，页面只列出前 ${number(CHANGES_LIST_LIMIT)} 条；完整清单以 data/cycles/${escapeHtml(targetCycle)}/changes.json 为准。</p>` : ''}</section>`;
  };
  const renderRanking = (payload, catalog = {}) => {
    const filters = state.ranking;
    const filtered = filterRows(payload, filters);
    const rows = aggregateCities(payload, filters).sort((a, b) => (filters.metric === 'recruits' ? b.recruits - a.recruits : b.jobs - a.jobs) || a.city.localeCompare(b.city, 'zh'));
    const maxRecruits = Math.max(1, ...rows.map((item) => Number(item.recruits || 0)));
    const coverageChip = (item) => {
      const coverage = item.jobs ? Math.round(Number(item.observed || 0) / Number(item.jobs || 1) * 100) : 0;
      return coverage > 0
        ? `<span class="ratio-chip" title="该市有 ${coverage}% 的岗位能查到官方报名/笔试等竞争人数；其余官方未逐岗公布，这里留空、不补成 100%。">${coverage}% <small>竞争覆盖</small></span>`
        : '<span class="ratio-chip ratio-chip--none" title="该市暂无可核对的官方逐岗竞争人数（未逐岗公布），不做推断">— 无公开数据</span>';
    };
    const fallbackMajors = [...new Set(rowsFor(payload).map((row) => cleanMajorOption(row?.zy)).filter((value) => isHumanMajor(value) && value.length <= 32))].sort((a, b) => a.localeCompare(b, 'zh'));
    const majors = curateMajorOptions(catalog, payload);
    const facets = catalog.facets || {};
    const cities = Array.isArray(facets.cities) && facets.cities.length ? facets.cities : uniqueValues(payload, 'city');
    const exams = Array.isArray(facets.exams) && facets.exams.length ? facets.exams : uniqueValues(payload, 'exam');
    const categories = Array.isArray(facets.categories) && facets.categories.length ? facets.categories : uniqueValues(payload, 'lb');
    const notice = state.notice ? `<div class="maint-inline-notice" role="status">${escapeHtml(state.notice)}</div>` : '';
    const active = activeFilterMarkup([
      { key: 'ranking.major', label: '专业关键词', value: filters.major },
      { key: 'ranking.city', label: '城市', value: filters.city ? cityDisplay(filters.city) : '' },
      { key: 'ranking.exam', label: '考试', value: filters.exam },
      { key: 'ranking.category', label: '岗位类型', value: filters.category },
    ]);
    return `${notice}<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('jobs_ranking', `${escapeHtml(state.cycle)} · 岗位排名`)}<h1>岗位榜单，先选专业再看城市。</h1><p>按专业、城市、考试和岗位类型组合筛选，随时可清空；筛选只改变你看到的结果，不改动任何岗位原文。</p></div></section><section class="maint-toolbar maint-toolbar--ranking"><label>专业关键词<input id="maint-ranking-major" list="maint-ranking-options" value="${escapeHtml(filters.major)}" placeholder="输入或选择，如：软件工程"></label><datalist id="maint-ranking-options">${majors.map((value) => `<option value="${escapeHtml(value)}" label="${number(majorCount(catalog, value))} 岗"></option>`).join('')}</datalist><span class="maint-filter-hint">按源专业文本关键词命中；详情保留专业原文</span>${majorTools('ranking', majors, catalog)}<label>城市<select id="maint-ranking-city">${optionMarkup(cities, filters.city)}</select></label><label>考试<select id="maint-ranking-exam">${optionMarkup(examScopeOptions, filters.exam, '全部考试')}</select></label><label>岗位类型<select id="maint-ranking-category">${optionMarkup(categories, filters.category)}</select></label><label>排序<select id="maint-ranking-metric"><option value="jobs" ${filters.metric === 'jobs' ? 'selected' : ''}>岗位数</option><option value="recruits" ${filters.metric === 'recruits' ? 'selected' : ''}>招录人数</option></select></label>${active}<span class="maint-toolbar__count">${filters.major ? `专业“${escapeHtml(filters.major)}” · ` : ''}${number(filtered.length)} / ${number(rowsFor(payload).length)} 个岗位 · ${number(rows.length)} 个城市</span><button type="button" data-maint-save-filter data-filter-view="jobs_ranking">保存筛选</button><button type="button" data-maintain-clear-ranking data-maintain-clear-major>重置筛选</button></section><section class="maint-panel"><div class="table-scroll"><table class="maint-table maint-table--ranking"><thead><tr><th>排名</th><th>城市</th><th>岗位数</th><th>招录人数</th><th>竞争覆盖</th><th>考试类别</th><th>专业关键词命中</th><th>岗位行</th></tr></thead><tbody>${rows.map((item, index) => `<tr data-maintain-ranking-row data-ranking-major="${escapeHtml(item.majors)}"><td class="rank">${index < 3 ? `<span class="rank-med rank-med--${index + 1}">${String(index + 1).padStart(2, '0')}</span>` : String(index + 1).padStart(2, '0')}</td><th>${escapeHtml(cityDisplay(item.city))}</th><td>${number(item.jobs)}</td><td class="num-bar"><i style="flex:0 0 ${(Number(item.recruits || 0) / maxRecruits * 100).toFixed(1)}%" aria-hidden="true"></i><b>${number(item.recruits)}</b></td><td>${coverageChip(item)}</td><td>${escapeHtml(item.exams || '—')}</td><td>${filters.major ? `命中“${escapeHtml(filters.major)}”` : '全部专业'}${filters.city ? ` · ${escapeHtml(cityDisplay(filters.city))}` : ''}</td><td><button type="button" class="maint-row-action" data-maint-ranking-city="${escapeHtml(item.city)}">查看岗位</button></td></tr>`).join('') || '<tr><td colspan="8" class="empty">当前条件没有匹配城市 <button type="button" class="maint-row-action" data-maintain-clear-ranking>重置筛选</button></td></tr>'}</tbody></table></div></section>`;
  };
  const searchFlowMarkup = () => `<section class="ui-search-flow" data-ui-search-flow aria-label="岗位决策路径"><div class="ui-search-flow__intro"><span>岗位检索</span><strong>把候选岗位变成可复核决定</strong><small>先缩小范围，再打开原文，最后留下你的选择。</small></div><div class="ui-search-flow__step is-current"><b>01</b><span><strong>缩小范围</strong><small>专业 · 城市 · 学历</small></span></div><div class="ui-search-flow__step"><b>02</b><span><strong>核对原文</strong><small>职位字段 · 来源定位</small></span></div><div class="ui-search-flow__step"><b>03</b><span><strong>保存或对比</strong><small>回到收藏 · 留下快照</small></span></div></section>`;
  const PROFILE_KEY = 'wanyu.profile.v1';
  const readProfile = () => {
    try {
      const raw = JSON.parse(localStorage.getItem(PROFILE_KEY) || '{}');
      return { gender: raw.gender || '', fresh: raw.fresh || '', party: raw.party || '', legal: raw.legal || '', age: raw.age || '' };
    } catch (error) { return { gender: '', fresh: '', party: '', legal: '', age: '' }; }
  };
  const writeProfile = (profile) => {
    try { localStorage.setItem(PROFILE_KEY, JSON.stringify(profile)); } catch (error) { /* 存储不可用时条件仅在本次会话生效 */ }
  };
  const profileActive = (p) => Boolean(p && (p.gender || p.fresh || p.party || p.legal || p.age));
  const renderSearch = (payload, catalog = {}, majorIndex = null, reqFields = null) => {
    const profile = readProfile();
    const profileOn = profileActive(profile) && Boolean(reqFields);
    const profileMiss = profileActive(profile) && !reqFields;
    // T2 一票否决：仅硬性要求且用户明确不满足才否决；置信度非 high 一律不否决（标"待核对"）
    const profileFail = (row) => {
      if (!profileOn) return false;
      const rf = reqFields[String(row.job_id || '')];
      if (!rf || rf.confidence !== 'high') return false;
      if (rf.fresh_only && profile.fresh === 'no') return true;
      if (rf.party_only && profile.party === 'no') return true;
      if (rf.cert_legal && profile.legal === 'no') return true;
      if (rf.gender === 'male' && profile.gender === 'female') return true;
      if (rf.gender === 'female' && profile.gender === 'male') return true;
      if (rf.age_max != null && profile.age && Number(profile.age) > Number(rf.age_max)) return true;
      return false;
    };
    const profilePending = (row) => {
      if (!profileOn) return false;
      const rf = reqFields[String(row.job_id || '')];
      return Boolean(rf && rf.confidence !== 'high');
    };
    const all = rowsFor(payload);
    const query = normalize(state.keyword);
    const majorQuery = normalize(state.searchMajor);
    // T1 三级匹配：明确含 / 专业类可报（推导，亮明依据）/ 专业不限；目录未收录则回退原文包含
    let tier = null;
    if (majorIndex?.postings && majorQuery) {
      const p = majorIndex.postings;
      const explicitSet = new Set(p.explicit[majorQuery] || []);
      const classSet = new Set();
      (majorIndex.classes || []).forEach((c) => {
        if ((c.members || []).includes(majorQuery) && Array.isArray(p.by_class[c.key])) {
          p.by_class[c.key].forEach((id) => classSet.add(id));
        }
      });
      const clsName = (majorIndex.classes || []).find((c) => (c.members || []).includes(majorQuery))?.key
        || (Array.isArray(p.by_class[majorQuery]) ? majorQuery : '');
      if (Array.isArray(p.by_class[majorQuery])) p.by_class[majorQuery].forEach((id) => classSet.add(id));
      const unlimitSet = new Set(p.unlimited || []);
      if (explicitSet.size || classSet.size || unlimitSet.size) {
        tier = { explicit: explicitSet, byClass: classSet, clsName, unlimit: unlimitSet };
      }
    }
    const rowTier = (row) => {
      if (!tier) return 0;
      const id = String(row.job_id || row.row_id || row.code || '');
      if (tier.explicit.has(id)) return 1;
      if (tier.byClass.has(id)) return 2;
      if (tier.unlimit.has(id)) return 3;
      return 9;
    };
    const cityGroup = state.searchCityGroup;
    const stealEligible = (row) => {
      const recruits = Number(row?.num ?? row?.recruits ?? 0);
      const examinees = Number(row?.competition_observations?.examinees?.value ?? row?.bm ?? 0);
      return recruits >= 3 && examinees > 0;
    };
    const stealRatio = (row) => {
      const recruits = Number(row?.num ?? row?.recruits ?? 0);
      const examinees = Number(row?.competition_observations?.examinees?.value ?? row?.bm ?? 0);
      return recruits > 0 && examinees > 0 ? examinees / recruits : Number.POSITIVE_INFINITY;
    };
    const filtered = all.filter((row) => {
      const rawMajor = normalize(row?.zy);
      const readableMajor = normalize(cleanMajorOption(row?.zy));
      return (!query || normalize(sourceText(row)).includes(query))
        && (!majorQuery || (tier ? rowTier(row) !== 9 : rawMajor.includes(majorQuery) || readableMajor.includes(majorQuery)))
        && (!state.city || String(row.city || row.reg || '') === state.city)
        && (!cityGroup || mapCityFor(row.city || row.reg) === cityGroup)
        && (!state.exam || examRowMatches(row, state.exam))
        && (!state.education || educationAllows(state.education, row.xl))
        && (!state.searchSteal || stealEligible(row))
        && !profileFail(row);
    });
    // 计算竞争比统计
    const competitionStats = { fierce: 0, medium: 0, easy: 0, unknown: 0 };
    filtered.forEach(row => {
      const recruits = Number(row.num ?? row.recruits ?? 0);
      const examinees = Number(row.competition_observations?.examinees?.value ?? row.bm ?? 0);
      if (examinees > 0 && recruits > 0) {
        const ratio = examinees / recruits;
        if (ratio >= 5) competitionStats.fierce++;
        else if (ratio >= 2) competitionStats.medium++;
        else competitionStats.easy++;
      } else {
        competitionStats.unknown++;
      }
    });
    const cities = uniqueValues(payload, 'city');
    const exams = uniqueValues(payload, 'exam');
    const majorOptions = curateMajorOptions(catalog, all);
    const sorted = [...filtered].sort((a, b) => {
      if (tier) {
        const tierDiff = rowTier(a) - rowTier(b);
        if (tierDiff) return tierDiff;
      }
      if (state.searchSteal) {
        const diff = stealRatio(a) - stealRatio(b);
        if (diff) return diff;
        return Number(b?.num ?? b?.recruits ?? 0) - Number(a?.num ?? a?.recruits ?? 0);
      }
      if (state.searchSort === 'recruits') return Number(b?.num ?? b?.recruits ?? 0) - Number(a?.num ?? a?.recruits ?? 0);
      if (state.searchSort === 'city') return String(a?.city || '').localeCompare(String(b?.city || ''), 'zh') || String(a?.code || '').localeCompare(String(b?.code || ''));
      if (state.searchSort === 'unit') return String(a?.unit || '').localeCompare(String(b?.unit || ''), 'zh') || String(a?.code || '').localeCompare(String(b?.code || ''));
      return 0;
    });
    const pageSize = [30, 60, 120].includes(Number(state.searchPageSize)) ? Number(state.searchPageSize) : 60;
    const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize));
    const page = Math.min(Math.max(0, state.searchPage), pageCount - 1);
    const pageRows = sorted.slice(page * pageSize, (page + 1) * pageSize);
    const notice = state.notice ? `<div class="maint-inline-notice" role="status">${escapeHtml(state.notice)}</div>` : '';
    const active = activeFilterMarkup([
      { key: 'search.keyword', label: '关键词', value: state.keyword },
      { key: 'search.major', label: '专业', value: state.searchMajor },
      { key: 'search.city', label: '城市', value: state.city ? cityDisplay(state.city) : '' },
      { key: 'search.cityGroup', label: '地图汇总', value: cityGroup ? cityDisplay(cityGroup) : '' },
      { key: 'search.exam', label: '考试', value: state.exam },
      { key: 'search.education', label: '学历', value: state.education },
      { key: 'search.steal', label: '捡漏雷达', value: state.searchSteal ? '按竞争比升序' : '' },
    ]);
    const educationLevels = ['本科', '研究生', '大专', '不限'];
    return `${notice}<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('jobs_search', '岗位检索')}<h1>找到适合你的岗位</h1><p>输入专业、选择城市和学历，快速筛选能报的岗位。点击"查看详情"了解岗位信息。</p></div></section><section class="maint-toolbar maint-toolbar--search"><label>关键词<input id="maint-search-keyword" type="search" value="${escapeHtml(state.keyword)}" placeholder="单位 / 职位 / 专业 / 代码"></label><label>专业<input id="maint-search-major" list="maint-search-major-options" value="${escapeHtml(state.searchMajor)}" placeholder="输入专业，如：法学、计算机"></label><datalist id="maint-search-major-options">${majorOptions.map((value) => `<option value="${escapeHtml(value)}" label="${number(majorCount(catalog, value))}个岗位"></option>`).join('')}</datalist><label>城市<select id="maint-search-city"><option value="">全部城市</option>${cities.map((city) => `<option ${state.city === city ? 'selected' : ''} value="${escapeHtml(city)}">${escapeHtml(city)}</option>`).join('')}</select></label><label>学历<select id="maint-search-education"><option value="">全部学历</option>${educationLevels.map((level) => `<option ${state.education === level ? 'selected' : ''} value="${escapeHtml(level)}">${escapeHtml(level)}</option>`).join('')}</select></label><label>考试<select id="maint-search-exam">${optionMarkup(examScopeOptions, state.exam, '全部考试')}</select></label><label>排序<select id="maint-search-sort"><option value="recruits" ${state.searchSort === 'recruits' ? 'selected' : ''}>招录人数</option><option value="source" ${state.searchSort === 'source' ? 'selected' : ''}>默认顺序</option><option value="city" ${state.searchSort === 'city' ? 'selected' : ''}>城市</option></select></label>${cityGroup ? `<button type="button" class="maint-row-action" data-maint-clear-city-group>清除地图筛选</button>` : ''}${active}<div class="maint-search-stats"><span class="maint-search-stats__total">找到 <strong>${number(filtered.length)}</strong> 个岗位</span><span class="maint-search-stats__fierce" title="竞争比5:1以上">🔥 竞争激烈 ${number(competitionStats.fierce)}个</span><span class="maint-search-stats__medium" title="竞争比2-5:1">⚠️ 竞争适中 ${number(competitionStats.medium)}个</span><span class="maint-search-stats__easy" title="竞争比2:1以下">✅ 竞争较小 ${number(competitionStats.easy)}个</span>${tier ? `<span class="maint-search-stats__tier t1" title="岗位专业要求原文明确包含「${escapeHtml(majorQuery)}」">✔ 明确含 ${number(filtered.filter((row) => rowTier(row) === 1).length)}</span><span class="maint-search-stats__tier t2" title="依据：该岗要求『${escapeHtml(tier.clsName)}』，「${escapeHtml(majorQuery)}」属该专业类（推导，依据可展开原文）">🔁 类内可报·推导 ${number(filtered.filter((row) => rowTier(row) === 2).length)}</span><span class="maint-search-stats__tier t3" title="该岗不限专业">➖ 不限专业 ${number(filtered.filter((row) => rowTier(row) === 3).length)}</span>` : ''}${profileOn ? `<span class="maint-search-stats__tier t1" title="按「我的条件」核对：应届/性别/党员/法考/年龄硬性要求，一票否决；存疑岗位不否决">👤 符合我的条件 ${number(filtered.length)}</span>` : ''}${profileMiss ? '<span class="maint-filter-hint">「我的条件」核对目前覆盖 2026 周期</span>' : ''}</div><div class="maint-search-actions">${!tier && majorQuery ? `<span class="maint-filter-hint">专业目录未收录「${escapeHtml(majorQuery)}」，当前按岗位原文包含匹配；可尝试目录内规范名</span>` : ''}${state.searchSteal ? '<span class="maint-steal-hint">口径：招录 ≥3 人 · 有官方报名观测 · 按竞争比从低到高；竞争比 = 官方报名人数 ÷ 招录数</span>' : ''}<button type="button" data-maint-steal-toggle class="${state.searchSteal ? 'is-active' : ''}" aria-pressed="${state.searchSteal ? 'true' : 'false'}" title="招录≥3人且官方公布报名人数的岗位，按竞争比从低到高">🎯 捡漏雷达</button><button type="button" data-maint-profile-toggle class="${profileOn ? 'is-active' : ''}" aria-expanded="${state.profileOpen ? 'true' : 'false'}" title="填写学历/应届/性别/党员/法考/年龄，全站自动标注可报">👤 我的条件</button><a class="maint-row-action" href="#match" data-maintain-view="match" title="专业+条件一次生成可报榜">⚡ 为我匹配</a><button type="button" data-maint-clear-search>清空筛选</button><button type="button" data-maint-save-filter data-filter-view="jobs_search">保存筛选</button><button type="button" data-maint-export-search>导出结果</button></div>${state.profileOpen ? `<div class="maint-profile-panel"><span class="maint-profile-panel__title">我的条件（仅存本机浏览器）</span><label>性别<select id="maint-profile-gender"><option value="">不限</option><option value="male" ${profile.gender === 'male' ? 'selected' : ''}>男</option><option value="female" ${profile.gender === 'female' ? 'selected' : ''}>女</option></select></label><label>应届身份<select id="maint-profile-fresh"><option value="">不限</option><option value="yes" ${profile.fresh === 'yes' ? 'selected' : ''}>是</option><option value="no" ${profile.fresh === 'no' ? 'selected' : ''}>否</option></select></label><label>政治面貌<select id="maint-profile-party"><option value="">不限</option><option value="yes" ${profile.party === 'yes' ? 'selected' : ''}>党员（含预备）</option><option value="no" ${profile.party === 'no' ? 'selected' : ''}>群众</option></select></label><label>法律职业资格<select id="maint-profile-legal"><option value="">不限</option><option value="yes" ${profile.legal === 'yes' ? 'selected' : ''}>有</option><option value="no" ${profile.legal === 'no' ? 'selected' : ''}>无</option></select></label><label>年龄<input id="maint-profile-age" type="number" min="16" max="60" value="${escapeHtml(profile.age)}" placeholder="周岁"></label><button type="button" class="maint-row-action" data-maint-profile-clear>清除条件</button><span class="maint-filter-hint">硬性要求不满足即隐藏该岗；条件解析存疑的岗位不否决、标「待核对」；最终以官方公告为准</span></div>` : ''}</section><section class="maint-panel"><div class="table-scroll"><table class="maint-table maint-table--search"><thead><tr><th scope="col">城市</th><th scope="col">单位</th><th scope="col">职位</th><th scope="col">专业</th><th scope="col">学历</th><th scope="col">招录</th><th scope="col">竞争</th><th scope="col">操作</th></tr></thead><tbody>${pageRows.map((row) => { const recordId = row.job_id || row.row_id || row.code || ''; const recruits = Number(row.num ?? row.recruits ?? 0); const examinees = Number(row.competition_observations?.examinees?.value ?? row.bm ?? 0); let compBadge = ''; if (examinees > 0 && recruits > 0) { const ratio = (examinees / recruits).toFixed(1); if (examinees / recruits >= 5) compBadge = `<span class="comp-badge comp-fierce" title="报名${examinees}人/招${recruits}人">${ratio}:1 🔥</span>`; else if (examinees / recruits >= 2) compBadge = `<span class="comp-badge comp-medium" title="报名${examinees}人/招${recruits}人">${ratio}:1</span>`; else compBadge = `<span class="comp-badge comp-easy" title="报名${examinees}人/招${recruits}人">${ratio}:1 ✅</span>`; } else { compBadge = '<span class="comp-badge comp-unknown">暂无数据</span>'; } return `<tr data-maint-search-row data-record-id="${escapeHtml(recordId)}"><td>${escapeHtml(row.city)}</td><td>${escapeHtml(row.unit)}</td><td>${escapeHtml(row.zw || row.display_title || '源表未单列披露')}</td><td class="major-cell" title="${escapeHtml(row.zy)}">${escapeHtml(row.zy)}${(() => { const t = rowTier(row); if (!tier || t === 9) return ''; if (t === 1) return '<span class="tier-badge tb1">✔ 明确含</span>'; if (t === 2) return `<span class="tier-badge tb2" title="依据：该岗要求『${escapeHtml(tier.clsName)}』，「${escapeHtml(majorQuery)}」属该专业类（推导）">类内可报·推导</span>`; return '<span class="tier-badge tb3">不限专业</span>'; })()}${profilePending(row) ? '<span class="tier-badge tb2" title="该岗条件解析置信度较低，请以原文核对">待核对</span>' : ''}</td><td>${escapeHtml(row.xl || '—')}</td><td>${escapeHtml(row.num ?? row.recruits ?? '—')}</td><td>${compBadge}</td><td><button type="button" class="maint-row-action" data-maint-position-detail data-record-id="${escapeHtml(recordId)}">查看详情</button></td></tr>`; }).join('') || '<tr><td colspan="8" class="empty">没有找到匹配的岗位 <button type="button" class="maint-row-action" data-maint-clear-search>清空全部筛选</button></td></tr>'}</tbody></table></div><div class="maint-pagination" data-maint-pagination aria-label="分页"><span class="maint-pagination__label">第 ${number(page + 1)} / ${number(pageCount)} 页</span><div class="maint-pagination__buttons"><button type="button" data-maint-search-page="prev" ${page <= 0 ? 'disabled' : ''}>上一页</button><button type="button" data-maint-search-page="next" ${page >= pageCount - 1 ? 'disabled' : ''}>下一页</button></div></div></section>`;
  };
  const detailStatusLabel = (status) => ({ verified: '已核验', partial_evidence: '部分证据已核验', source_bundle: '源包接入', derived: '派生指标', registered: '已登记', unpublished_or_unavailable: '未发布或未取得', ambiguous_join: '无法唯一关联', needs_review: '待复核', unavailable: '未取得', suspected_sentinel: '疑似哨兵值', incompatible_scale: '量纲不兼容', not_applicable: '不适用' }[String(status)] || '未知');
  const detailValue = (value, status = '') => {
    if (value === false) return '否';
    if (value === true) return '是';
    if (value !== null && value !== undefined && String(value).trim() !== '') return escapeHtml(value);
    return `<span class="maint-value-null">${escapeHtml(detailStatusLabel(status || 'unavailable'))}</span>`;
  };
  const positionIndexRow = (positions, recordId) => (positions?.rows || []).find((item) => String(item.record_id) === String(recordId));
  const renderDetailDrawer = (row, indexRow, historyEntry) => {
    const source = indexRow?.source || {};
    const recordId = row.job_id || row.row_id || row.code || '';
    const store = window.WanyuUserStore;
    const saved = store?.loadPositions?.().some((item) => item.recordId === recordId);
    const compared = store?.loadCompare?.().includes(recordId);
    const score = row.score_observation || {};
    let historyBlock = '';
    if (historyEntry && historyEntry.cycles) {
      const order = ['2024', '2025', '2026'].filter((cycle) => historyEntry.cycles[cycle]);
      if (order.length >= 2) {
        const rowsHtml = order.map((cycle) => {
          const h = historyEntry.cycles[cycle];
          const lineText = h.lo == null ? '—' : (h.hi != null && h.hi !== h.lo ? `${h.lo}–${h.hi}` : `${h.lo}`);
          const ratioText = h.num > 0 && h.bm != null ? `${(h.bm / h.num).toFixed(1)}:1` : '—';
          return `<tr><td>${cycle}</td><td>${h.posts} 岗</td><td>${number(h.num)} 人</td><td>${h.bm != null ? number(h.bm) : '—'}</td><td>${ratioText}</td><td>${lineText}</td></tr>`;
        }).join('');
        const vizYears = order.filter((y) => historyEntry.cycles[y]?.lo != null);
        const vizPosts = order.map((y) => ({ year: y, posts: historyEntry.cycles[y]?.posts ?? 0 }));
        let spark = '';
        let trendBadge = '';
        if (vizYears.length >= 2) {
          const los = vizYears.map((y) => historyEntry.cycles[y].lo);
          const minV = Math.min(...los), maxV = Math.max(...los);
          const span = maxV - minV || 1;
          const W = 500, H = 88, PAD = 14;
          const pts = los.map((v, i) => [PAD + (i * (W - PAD * 2)) / (los.length - 1), H - PAD - ((v - minV) / span) * (H - PAD * 2)]);
          const poly = pts.map((pt) => `${pt[0].toFixed(1)},${pt[1].toFixed(1)}`).join(' ');
          spark = `<svg class="maint-trend-spark" viewBox="0 0 ${W} ${H}" role="img" aria-label="同职位族入围线走势：${vizYears.join('、')}年分别为 ${los.join('、')} 分"><polyline points="${poly}" fill="none" stroke="var(--accent-primary,#3a83f7)" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>${pts.map((pt, i) => `<circle cx="${pt[0].toFixed(1)}" cy="${pt[1].toFixed(1)}" r="4.5" fill="var(--accent-primary,#3a83f7)"/><text x="${pt[0].toFixed(1)}" y="${pt[1].toFixed(1) - 10}" text-anchor="middle" class="maint-trend-spark__val">${los[i]}</text>`).join('')}<text x="${PAD}" y="${H - 2}" text-anchor="start" class="maint-trend-spark__year">${vizYears[0]}</text><text x="${W - PAD}" y="${H - 2}" text-anchor="end" class="maint-trend-spark__year">${vizYears[vizYears.length - 1]}</text></svg>`;
        }
        if (vizPosts.length >= 2) {
          const p0 = vizPosts[0].posts, p1 = vizPosts[vizPosts.length - 1].posts;
          if (p1 > p0) trendBadge = `<span class="tier-badge tb1" title="同职位族招录人数 ${p0}→${p1}">扩招 ↗（${p0}→${p1}）</span>`;
          else if (p1 < p0) trendBadge = `<span class="tier-badge tb2" title="同职位族招录人数 ${p0}→${p1}">缩招 ↘（${p0}→${p1}）</span>`;
          else trendBadge = `<span class="tier-badge tb3" title="同职位族招录人数持平（${p0}）">招录持平（${p0}）</span>`;
        }
        historyBlock = `<section class="maint-detail-section"><h3>跨年走势 · 同单位同职位族 ${trendBadge}</h3>${spark}<div class="table-scroll"><table class="maint-table maint-table--history"><thead><tr><th scope="col">年份</th><th scope="col">岗位</th><th scope="col">招录</th><th scope="col">报名</th><th scope="col">竞争比</th><th scope="col">入围线</th></tr></thead><tbody>${rowsHtml}</tbody></table></div><p class="maint-detail-footnote">按“城市+单位+职位名称”聚合的同职位族跨年数据，仅显示有数据的年份；报名与入围线在官方未公布或无法唯一匹配时保持空值，不以 0 冒充。</p></section>`;
      }
    }
    const fields = [
      ['单位', row.unit, ''], ['职位', row.zw || row.display_title, row.title_status], ['城市', row.city || row.reg, ''],
      ['考试类别', row.exam, ''], ['职位代码', row.code, ''], ['招录人数', row.num ?? row.recruits, ''],
      ['专业要求（源文）', row.zy, ''], ['学历', row.xl, ''], ['学位', row.xw, ''], ['政治面貌', row.xz, ''],
      ['年龄要求', row.age, ''], ['备注', row.bz, ''], ['成绩/入围线', score.value, score.status],
    ];
    return `<div class="maint-detail-backdrop" data-maint-detail-drawer role="presentation"><aside class="maint-detail-drawer" role="dialog" aria-modal="true" aria-labelledby="maint-detail-title"><header class="maint-detail-head"><div><p class="maint-eyebrow">${escapeHtml(state.cycle)} · 岗位详情</p><h2 id="maint-detail-title">${escapeHtml(row.zw || row.display_title || '岗位详情')}</h2><p>${escapeHtml(row.unit || '未提供单位')} · ${escapeHtml(row.code || '')} · ${escapeHtml(row.city || row.reg || '')} · ${escapeHtml(row.exam || '')}</p><p class="maint-evidence-chip">✔ 来源可核对${source.observed_at ? ` · 材料取得 ${escapeHtml(source.observed_at)}` : ''}</p></div><button type="button" class="maint-detail-close" data-maint-detail-close aria-label="关闭岗位详情">×</button></header><div class="maint-detail-actions"><div class="maint-detail-action-group"><button type="button" data-maint-save-position data-record-id="${escapeHtml(recordId)}">${saved ? '已收藏' : '收藏岗位'}</button><button type="button" data-maint-position-compare data-record-id="${escapeHtml(recordId)}">${compared ? '移出对比' : '加入对比'}</button><button type="button" data-maint-share-job data-record-id="${escapeHtml(recordId)}">复制分享文本</button></div><details class="maint-detail-id"><summary>岗位编号</summary><code>${escapeHtml(recordId)}</code></details></div><section class="maint-decision-bar" aria-label="报考决策要点">${(() => {
      const num = Number(row.num ?? row.recruits ?? 0);
      const examinees = Number(row.competition_observations?.examinees?.value ?? row.bm ?? 0);
      const ratio = examinees > 0 && num > 0 ? `${(examinees / num).toFixed(1)}:1` : null;
      const lineVal = row.score_observation?.value;
      const lineOk = row.score_observation?.status === 'comparable';
      const cyc = historyEntry?.cycles ? ['2024', '2025', '2026'].filter((y) => historyEntry.cycles[y]) : [];
      let trend = '首年岗，无跨年参照';
      if (cyc.length >= 2) {
        const first = historyEntry.cycles[cyc[0]];
        const last = historyEntry.cycles[cyc[cyc.length - 1]];
        if (first.lo != null && last.lo != null) {
          const arrow = last.lo > first.lo ? '↗ 走高' : (last.lo < first.lo ? '↘ 走低' : '→ 持平');
          trend = `${cyc[0]}–${cyc[cyc.length - 1]} 入围线 ${first.lo}→${last.lo} ${arrow}`;
        } else trend = `${cyc.length} 个年度有招录，入围线未全公布`;
      }
      return `<div class="maint-decision-bar__cell"><span>招录</span><strong>${num > 0 ? number(num) : '未公布'}</strong><small>人</small></div><div class="maint-decision-bar__cell"><span>官方报名竞争</span><strong>${ratio || '未公布'}</strong><small>${ratio ? `报名 ${number(examinees)} 人` : '无官方观测'}</small></div><div class="maint-decision-bar__cell"><span>入围线</span><strong>${lineOk && lineVal != null ? escapeHtml(String(lineVal)) : '未公布'}</strong><small>${lineOk ? '可复核口径' : (lineVal != null ? '量纲不符，不参与比较' : '未公布不推断')}</small></div><div class="maint-decision-bar__cell maint-decision-bar__cell--wide"><span>跨年走势</span><strong>${escapeHtml(trend)}</strong><small>${cyc.length ? `同单位同职位族 · ${cyc.join('/')}` : '本族仅今年在库'}</small></div>`;
    })()}</section><section class="maint-detail-section"><h3>岗位原始字段</h3><dl class="maint-detail-fields">${fields.map(([label, value, status]) => `<div><dt>${escapeHtml(label)}</dt><dd>${detailValue(value, status)}</dd></div>`).join('')}</dl></section>${historyBlock}<section class="maint-detail-section maint-detail-evidence"><h3>证据与来源</h3><div class="maint-detail-status"><span class="audit-chip">${escapeHtml(detailStatusLabel(source.status))}</span><span>${escapeHtml(methodLabel(source.method))}</span></div><details class="maint-source-details"><summary>查看来源定位</summary><dl class="maint-detail-fields"><div><dt>来源文件</dt><dd><code>${escapeHtml(source.source_ref || '未提供')}</code></dd></div><div><dt>源定位</dt><dd><code>${escapeHtml(source.source_locator || '未提供')}</code></dd></div><div><dt>源材料获取日期</dt><dd>${source.observed_at || '未提供'}</dd></div><div><dt>说明</dt><dd>${escapeHtml(source.note || '原始值保留在岗位数据中')}</dd></div></dl></details></section><p class="maint-detail-footnote">专业候选是展示层关键词；报考资格仍以当年官方公告、职位表和专业目录为准。岗位原文未被清洗或改写。</p></aside></div>`;
  };
  const lockBodyScroll = (lock) => {
    if (lock) {
      if (!('scrollLock' in document.body.dataset)) {
        document.body.dataset.scrollLock = document.body.style.overflow || '';
        document.body.style.overflow = 'hidden';
      }
    } else if ('scrollLock' in document.body.dataset) {
      document.body.style.overflow = document.body.dataset.scrollLock || '';
      delete document.body.dataset.scrollLock;
    }
  };
  let detailInflight = null;
  const openDetail = async (recordId, options = {}) => {
    if (detailInflight) return detailInflight;
    detailInflight = (async () => {
    const jobs = state.modules.get(`${state.cycle}:jobs`) || await loadModule(state.cycle, 'jobs'); const positions = state.modules.get(`${state.cycle}:positions`) || await loadModule(state.cycle, 'positions');
    const row = rowsFor(jobs).find((item) => String(item.job_id || item.row_id || item.code) === String(recordId));
    if (!row) { setStatus('岗位详情不存在', 'error'); return; }
    const indexRow = positionIndexRow(positions, recordId);
    const jobHistory = await loadJobHistory().catch(() => null);
    const historyEntry = jobHistory?.jobs?.[jobHistoryKey(row)] || null;
    state.detail = { recordId };
    lockBodyScroll(true);
    if (!options.fromHash) {
      const defaultCycle = state.manifest?.default_cycle || '2026';
      const cycleQuery = String(state.cycle) !== String(defaultCycle) ? `?cycle=${encodeURIComponent(String(state.cycle))}` : '';
      history.replaceState({}, '', `${cycleQuery}#job/${encodeURIComponent(String(recordId))}`);
    }
    document.querySelector('[data-maint-detail-drawer]')?.remove();
    main.insertAdjacentHTML('beforeend', renderDetailDrawer(row, indexRow, historyEntry));
    setStatus(`${state.cycle} · 岗位详情已打开`, 'ready');
    document.querySelector('[data-maint-detail-close]')?.focus();
    })();
    try { await detailInflight; } finally { detailInflight = null; }
  };
  const closeDetail = () => {
    const recordId = state.detail?.recordId;
    document.querySelector('[data-maint-detail-drawer]')?.remove();
    state.detail = null;
    lockBodyScroll(false);
    const viewHash = `#${state.view}`;
    if ((location.hash || '#overview') !== viewHash) history.replaceState({}, '', `${location.pathname}${location.search}${viewHash}`);
    const rowsPayload = state.modules.get(`${state.cycle}:jobs_lite`) || state.modules.get(`${state.cycle}:jobs`);
    setStatus(`${state.cycle} · 数据已就绪 · ${rowsPayload ? `${number(rowsFor(rowsPayload).length)} 个岗位` : '审计数据'}`, 'ready');
    if (recordId) [...document.querySelectorAll('[data-maint-position-detail]')].find((node) => node.dataset.recordId === recordId)?.focus();
  };
  const currentRowsPayload = () => scopeExamPayload(state.modules.get(`${state.cycle}:jobs_lite`) || state.modules.get(`${state.cycle}:jobs`) || null);
  const renderMatch = (payload, catalog, majorIndex, reqFields) => {
    if (!state.matchMajor) state.matchMajor = normalize(state.searchMajor || '');
    const all = rowsFor(payload);
    const majorQuery = normalize(state.matchMajor);
    const profile = readProfile();
    const profileOn = profileActive(profile) && Boolean(reqFields);
    const p = majorIndex?.postings || null;
    const explicitSet = new Set(p && majorQuery ? p.explicit[majorQuery] || [] : []);
    const classSet = new Set();
    let clsName = '';
    if (p && majorQuery) {
      (majorIndex.classes || []).forEach((c) => {
        if ((c.members || []).includes(majorQuery) && Array.isArray(p.by_class[c.key])) {
          if (!clsName) clsName = c.key;
          p.by_class[c.key].forEach((id) => classSet.add(id));
        }
      });
      if (Array.isArray(p.by_class[majorQuery])) {
        if (!clsName) clsName = majorQuery;
        p.by_class[majorQuery].forEach((id) => classSet.add(id));
      }
    }
    const unlimitSet = new Set(p ? p.unlimited || [] : []);
    const tierOf = (row) => {
      const id = String(row.job_id || row.row_id || row.code || '');
      if (explicitSet.has(id)) return 1;
      if (classSet.has(id)) return 2;
      if (unlimitSet.has(id)) return 3;
      return 9;
    };
    const profileFail = (row) => {
      if (!profileOn) return false;
      const rf = reqFields[String(row.job_id || '')];
      if (!rf || rf.confidence !== 'high') return false;
      if (rf.fresh_only && profile.fresh === 'no') return true;
      if (rf.party_only && profile.party === 'no') return true;
      if (rf.cert_legal && profile.legal === 'no') return true;
      if (rf.gender === 'male' && profile.gender === 'female') return true;
      if (rf.gender === 'female' && profile.gender === 'male') return true;
      if (rf.age_max != null && profile.age && Number(profile.age) > Number(rf.age_max)) return true;
      return false;
    };
    const matched = majorQuery && p
      ? all.filter((row) => tierOf(row) !== 9 && !profileFail(row))
      : [];
    const n1 = matched.filter((row) => tierOf(row) === 1).length;
    const n2 = matched.filter((row) => tierOf(row) === 2).length;
    const n3 = matched.filter((row) => tierOf(row) === 3).length;
    const ratioOf = (row) => {
      const num = Number(row.num ?? row.recruits ?? 0);
      const examinees = Number(row.competition_observations?.examinees?.value ?? row.bm ?? 0);
      return num > 0 && examinees > 0 ? examinees / num : Number.POSITIVE_INFINITY;
    };
    const top = [...matched].sort((a, b) => (tierOf(a) - tierOf(b)) || (ratioOf(a) - ratioOf(b))).slice(0, 30);
    const majorOptions = curateMajorOptions(catalog, all);
    const input = `<div class="maint-match-input"><input id="maint-match-major" list="maint-match-major-options" value="${escapeHtml(state.matchMajor)}" placeholder="输入你的专业，如：知识产权、软件工程、会计学"><datalist id="maint-match-major-options">${majorOptions.slice(0, 500).map(([value]) => `<option value="${escapeHtml(value)}"></option>`).join('')}</datalist><button type="button" class="maint-action" data-maint-match-go>生成我的可报榜</button>${profileOn ? '<span class="tier-badge tb1">👤 条件已启用</span>' : `<a class="maint-filter-hint" href="#jobs_search" data-maintain-view="jobs_search">先去「我的条件」填应届/性别/党员/法考，结果更准 →</a>`}</div>`;
    if (!majorQuery) {
      return `<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('match', '为我匹配')}<h1>一步得到你的可报榜。</h1><p>输入专业 + 可选的个人条件，本页把「明确含你的专业」「专业类可报（推导）」「不限专业」三类岗位一次性排好，每条亮明依据。</p></div></section><section class="maint-panel">${input}<p class="maint-filter-hint">数据：${escapeHtml(String(state.cycle))} 周期 · 匹配口径与「找岗位」一致，依据均可展开原文核对。</p></section>`;
    }
    const tiersBar = `<div class="maint-search-stats"><span class="maint-search-stats__tier t1">✔ 明确可报 ${number(n1)}</span><span class="maint-search-stats__tier t2">🔁 类内可报·推导 ${number(n2)}</span><span class="maint-search-stats__tier t3">➖ 不限专业 ${number(n3)}</span>${profileOn ? `<span class="maint-search-stats__tier t1">👤 已按我的条件过滤</span>` : ''}</div>`;
    const tableRows = top.map((row) => {
      const t = tierOf(row);
      const num = Number(row.num ?? row.recruits ?? 0);
      const examinees = Number(row.competition_observations?.examinees?.value ?? row.bm ?? 0);
      const ratio = num > 0 && examinees > 0 ? `${(examinees / num).toFixed(1)}:1` : '暂无数据';
      const tierBadge = t === 1 ? '<span class="tier-badge tb1">✔ 明确含</span>' : (t === 2 ? `<span class="tier-badge tb2" title="依据：该岗要求『${escapeHtml(clsName)}』，「${escapeHtml(majorQuery)}」属该专业类（推导）">类内可报·推导</span>` : '<span class="tier-badge tb3">不限专业</span>');
      return `<tr data-maint-search-row data-record-id="${escapeHtml(row.job_id || row.code)}"><td>${escapeHtml(row.city)}</td><td>${escapeHtml(row.unit)}</td><td>${escapeHtml(row.zw || row.display_title || '—')}</td><td class="major-cell" title="${escapeHtml(row.zy)}">${tierBadge}</td><td>${escapeHtml(row.xl || '—')}</td><td>${escapeHtml(num || '—')}</td><td>${escapeHtml(ratio)}</td><td><button type="button" class="maint-row-action" data-maint-position-detail data-record-id="${escapeHtml(row.job_id || row.code)}">查看详情</button></td></tr>`;
    }).join('');
    const result = majorQuery && !p
      ? `<p class="empty">匹配索引尚未加载完成，请稍候自动刷新；或回到<a href="#jobs_search" data-maintain-view="jobs_search">找岗位</a>先行检索。</p>`
      : `${tiersBar}<div class="table-scroll"><table class="maint-table"><thead><tr><th scope="col">城市</th><th scope="col">单位</th><th scope="col">职位</th><th scope="col">匹配依据</th><th scope="col">学历</th><th scope="col">招录</th><th scope="col">竞争</th><th scope="col">操作</th></tr></thead><tbody>${tableRows || '<tr><td colspan="8" class="empty">没有匹配的岗位：可清空部分条件，或确认专业名在目录内（回找岗位页可按原文检索）</td></tr>'}</tbody></table></div><p class="maint-filter-hint">显示竞争最友好的前 30 岗（命中档优先，再按竞争比升序）；完整清单用「找岗位」按同条件导出。</p>`;
    return `<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('match', '为我匹配')}<h1>${escapeHtml(majorQuery)} · 你的可报榜。</h1><p>三类命中一次排开，每条亮明匹配依据；个人条件只做硬性一票否决，存疑岗位不否决。</p></div></section><section class="maint-panel">${input}${result}</section>`;
  };
  const renderCalendar = (cal) => {
    const items = Array.isArray(cal?.items) ? cal.items : [];
    const statusLabel = { expected: '预计', live: '进行中', done: '已发生' };
    const rows = items.map((item) => `<tr><th scope="row">${escapeHtml(item.stage || '')}</th><td>${item.date ? escapeHtml(item.date) : `<span class="tier-badge tb2">${escapeHtml(statusLabel[item.status] || '预计')}</span>`}</td><td>${escapeHtml(item.expect || '—')}</td><td class="major-cell">${escapeHtml(item.basis || '')}</td></tr>`).join('');
    return `<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('calendar', '报考日历')}<h1>关键时间，一眼看清。</h1><p>未公布的节点不填具体日期，只给预计窗口与依据；一切以官方公告为准。本页与职位表数据同步更新。</p></div><div class="maint-hero__stamp"><span>窗口提醒</span><strong>2027 国考</strong><small>预计 10 月中旬出公告 · 报名约 10 天</small></div></section><section class="maint-panel"><header><div><p class="maint-eyebrow">节点清单</p><h2>报名前后的关键节点</h2></div><span class="maint-audit-date">${escapeHtml(cal?.updated || '')} 更新</span></header><div class="table-scroll"><table class="maint-table"><thead><tr><th>节点</th><th>日期</th><th>窗口</th><th>依据 / 口径</th></tr></thead><tbody>${rows || '<tr><td colspan="4" class="empty">日历数据待更新</td></tr>'}</tbody></table></div><p class="maint-callout" style="margin-top:14px"><strong>数据同步承诺</strong><span>2027 官方职位表发布后，本站按「构建 → 校验 → 发布」管线尽快上线新周期数据，并在首页同步预告；发布前本站数据仍为 2026 快照，报前参考请以官方公告为准。</span></p></section><section class="maint-callout"><strong>现在能做什么</strong><span>先用 <a href="#jobs_search" data-maintain-view="jobs_search">找岗位</a> 熟悉三年职位表与竞争行情，收藏目标岗并关注 <a href="#changes" data-maintain-view="changes">变更通报</a>；新公告发布后回到同一收藏夹即可对照新表。</span></section>`;
  };
  const renderSaved = (savedChanges = null) => {
    const store = window.WanyuUserStore;
    const snapshots = store?.loadFilterSnapshots?.() || [];
    const positions = store?.loadPositions?.() || [];
    const compareIds = store?.loadCompare?.() || [];
    const jobs = currentRowsPayload();
    const rows = rowsFor(jobs);
    const rowFor = (recordId) => rows.find((row) => String(row.job_id || row.row_id || row.code) === String(recordId));
    const formatSavedDate = (value) => {
      if (!value) return '时间未提供';
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
    };
    const filterSummary = (filters = {}) => [
      filters.major && `专业：${filters.major}`,
      filters.keyword && `关键词：${filters.keyword}`,
      filters.cityGroup && `地图：${cityDisplay(filters.cityGroup)}`,
      filters.city && `城市：${cityDisplay(filters.city)}`,
      filters.exam && `考试：${filters.exam}`,
      filters.category && `岗位类型：${filters.category}`,
    ].filter(Boolean).join(' · ') || '未命名筛选';
    const positionCycle = (recordId) => String(recordId || '').match(/^job-(\d{4})-/)?.[1] || '';
    const renderSavedPosition = (item) => {
      const row = rowFor(item.recordId);
      const belongsTo = positionCycle(item.recordId);
      const title = row?.unit || row?.zw || item.recordId;
      const meta = row ? `${row.code || item.recordId} · ${cityDisplay(row.city || row.reg)} · ${row.bz || item.note || '无备注'}` : `${belongsTo ? `${belongsTo} 周期` : '其他周期'} · 当前周期未加载`;
      return `<article class="saved-item"><button type="button" class="saved-item__link" data-maint-saved-position data-record-id="${escapeHtml(item.recordId)}" ${row ? '' : 'disabled'} title="${row ? '打开岗位详情' : '切换至对应周期后打开'}"><strong>${escapeHtml(title)}</strong><small>${escapeHtml(meta)}</small></button><button type="button" data-maint-remove-position data-record-id="${escapeHtml(item.recordId)}">移除</button></article>`;
    };
    const renderCompareItem = (recordId) => {
      const row = rowFor(recordId);
      const belongsTo = positionCycle(recordId);
      return `<article class="saved-item"><button type="button" class="saved-item__link" data-maint-saved-position data-record-id="${escapeHtml(recordId)}" ${row ? '' : 'disabled'}><strong>${escapeHtml(row?.unit || row?.zw || recordId)}</strong><small>${escapeHtml(row ? `${row.code || recordId} · ${cityDisplay(row.city || row.reg)}` : `${belongsTo ? `${belongsTo} 周期` : '其他周期'} · 当前周期未加载`)}</small></button><button type="button" data-maint-remove-compare data-record-id="${escapeHtml(recordId)}">移除</button></article>`;
    };
    const notice = state.notice ? `<div class="maint-inline-notice" role="status">${escapeHtml(state.notice)}</div>` : '';
    const compareRows = compareIds.map((recordId) => rowFor(recordId)).filter(Boolean);
    const compareDiffSection = compareRows.length >= 2 ? (() => {
      const diffFields = [
        ['城市', (row) => String(row.city || row.reg || '')], ['考试类别', (row) => String(row.exam || '')],
        ['招录人数', (row) => String(row.num ?? row.recruits ?? '')], ['学历', (row) => String(row.xl || '')],
        ['专业要求（源文）', (row) => String(row.zy || '')], ['备注', (row) => String(row.bz || '')],
      ];
      const diffCount = diffFields.filter(([, get]) => new Set(compareRows.map(get)).size > 1).length;
      const head = compareRows.map((row) => `<th scope="col">${escapeHtml(row.zw || row.display_title || row.unit || row.code || '岗位')}</th>`).join('');
      const body = diffFields.map(([label, get]) => {
        const values = compareRows.map(get);
        const isDiff = new Set(values).size > 1;
        return `<tr><th scope="row">${escapeHtml(label)}${isDiff ? ' <span class="diff-mark" title="该字段存在差异">≠</span>' : ''}</th>${values.map((value) => `<td class="${isDiff ? 'is-diff' : ''}">${escapeHtml(value || '未提供')}</td>`).join('')}</tr>`;
      }).join('');
      return `<section class="maint-panel maint-panel--compare"><header><div><p class="maint-eyebrow">对比差异</p><h2>对比差异</h2></div><span class="maint-audit-date">${number(compareRows.length)} 岗 · 差异 ${number(diffCount)} 处</span></header><div class="table-scroll"><table class="maint-table maint-table--compare-diff"><thead><tr><th>字段</th>${head}</tr></thead><tbody>${body}</tbody></table></div><div class="maint-detail-actions"><button type="button" data-maint-export-compare>导出对比 CSV</button><small>差异单元格以左侧标记高亮；“未提供”保持空值语义，不推断。</small></div></section>`;
    })() : '';
    const changeAlert = (() => {
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
    return `${notice}${changeAlert}<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('saved', '我的收藏')}<h1>把筛选和重点岗位留在手边。</h1><p>快照只保存周期、条件和版本；收藏和对比只保存稳定岗位 ID，不复制或改写源数据。</p></div></section><section class="maint-grid maint-grid--saved" data-maint-saved-panel><section class="maint-panel"><header><div><p class="maint-eyebrow">筛选快照</p><h2>筛选快照</h2></div><span class="maint-workspace-actions"><button type="button" class="maint-row-action" data-maint-export-workspace>导出工作台</button><button type="button" class="maint-row-action" data-maint-import-workspace>导入工作台</button><span class="maint-audit-date">${number(snapshots.length)} 个</span></span></header><div class="saved-list">${snapshots.map((snapshot) => `<article class="saved-item"><div><strong>${escapeHtml(filterSummary(snapshot.filters || {}))}</strong><small>${escapeHtml(snapshot.cycle || '—')} · ${escapeHtml(snapshot.view === 'jobs_ranking' ? '岗位榜单' : '岗位检索')} · ${escapeHtml(formatSavedDate(snapshot.createdAt))}</small></div><button type="button" data-maint-load-snapshot data-snapshot-id="${escapeHtml(snapshot.id)}">恢复</button></article>`).join('') || '<p class="empty">还没有筛选快照。先在岗位检索或岗位榜单点击“保存筛选”。</p>'}</div></section><section class="maint-panel"><header><div><p class="maint-eyebrow">已收藏岗位</p><h2>已收藏岗位</h2></div><span class="maint-audit-date">${number(positions.length)} 个</span></header><div class="saved-list">${positions.map((item) => renderSavedPosition(item)).join('') || '<p class="empty">还没有收藏岗位。打开岗位详情即可收藏。</p>'}</div></section><section class="maint-panel"><header><div><p class="maint-eyebrow">对比清单</p><h2>对比清单</h2></div><span class="maint-audit-date">${number(compareIds.length)} / 4</span></header><div class="saved-list">${compareIds.map((recordId) => renderCompareItem(recordId)).join('') || '<p class="empty">还没有加入对比的岗位。岗位详情或检索行内可加入，最多 4 个。</p>'}</div></section></section>${compareDiffSection}`;
  };
  const saveCurrentFilter = (view) => {
    const store = window.WanyuUserStore;
    if (!store) return;
    const filters = view === 'jobs_ranking' ? { ...state.ranking } : { keyword: state.keyword, major: state.searchMajor, city: state.city, cityGroup: state.searchCityGroup, exam: state.exam };
    const snapshot = store.makeSnapshot(state.cycle, filters, view === 'jobs_ranking' ? state.ranking.metric : 'jobs', state.manifest?.release || '');
    snapshot.view = view;
    store.saveFilterSnapshot(snapshot);
    state.notice = '筛选已保存';
  };
  const exportCurrentSearch = () => {
    const store = window.WanyuUserStore;
    const jobs = currentRowsPayload();
    if (!store || !jobs) return;
    const all = rowsFor(jobs); const query = normalize(state.keyword); const majorQuery = normalize(state.searchMajor); const cityGroup = state.searchCityGroup;
    const filtered = all.filter((row) => { const rawMajor = normalize(row?.zy); const readableMajor = normalize(cleanMajorOption(row?.zy)); return (!query || normalize(sourceText(row)).includes(query)) && (!majorQuery || rawMajor.includes(majorQuery) || readableMajor.includes(majorQuery)) && (!state.city || String(row.city || row.reg || '') === state.city) && (!cityGroup || mapCityFor(row.city || row.reg) === cityGroup) && (!state.exam || examRowMatches(row, state.exam))
      && (!state.education || educationAllows(state.education, row.xl)); });
    const blob = new Blob([store.serializeExport(filtered, 'csv')], { type: 'text/csv;charset=utf-8' });
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `wanyu-${state.cycle}-positions.csv`; link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 0);
    state.notice = `已导出 ${number(filtered.length)} 行`;
  };
  const exportCompareCsv = () => {
    const store = window.WanyuUserStore;
    const jobs = state.modules.get(`${state.cycle}:jobs`);
    if (!store || !jobs) return;
    const rows = rowsFor(jobs);
    const compareRows = (store.loadCompare?.() || []).map((recordId) => rows.find((row) => String(row.job_id || row.row_id || row.code) === String(recordId))).filter(Boolean);
    if (compareRows.length < 2) { state.notice = '对比岗位不足两行，无法导出'; return; }
    const blob = new Blob([store.serializeExport(compareRows, 'csv')], { type: 'text/csv;charset=utf-8' });
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `wanyu-${state.cycle}-compare.csv`; link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 0);
    state.notice = `已导出 ${number(compareRows.length)} 个对比岗位`;
  };
  const auditStatus = (item) => String(item?.status || item?.dominant_status || item?.evidence_level || 'registered');
  const auditGapsFor = (auditPayload) => {
    const audit = auditPayload?.audit || {}; const info = auditPayload?.cycleInfo || {}; const gaps = [...(audit.gaps || []), ...(info.gaps || [])];
    return gaps.filter((item, index, values) => values.findIndex((candidate) => JSON.stringify(candidate) === JSON.stringify(item)) === index);
  };
  const renderSupplementEvidence = (supplement) => {
    if (!supplement) return '';
    const summary = supplement.summary || {};
    const cycleRows = Object.entries(supplement.by_cycle || {}).sort(([left], [right]) => left.localeCompare(right)).map(([cycle, item]) => `<tr data-maint-supplement-cycle-row><th>${escapeHtml(cycle)}</th><td>${number(item.raw_files)}</td><td>${number(item.valid_documents)}</td><td>${number(item.blocked_downloads)}</td><td>${number(item.bytes)}</td></tr>`).join('');
    return `<section class="maint-panel maint-supplement-panel" data-maint-supplement-evidence><header><div><p class="maint-eyebrow">2026-09-04 · 证据台账</p><h2>补充证据台账</h2></div><span class="maint-audit-date">${escapeHtml(supplement.generated_at || '—')}</span></header><p>本轮代理回收资料已完成磁盘级登记与哈希核验；证据归档和正式业务入库分开计算，避免重复计数或把待复核结论写成事实。</p><section class="maint-kpis maint-kpis--audit"><article><span>原始文件</span><strong>${number(summary.raw_files)}</strong><small>${number(summary.raw_bytes)} bytes</small></article><article><span>可解析资料</span><strong>${number(summary.valid_documents)}</strong><small>XLS / XLSX / PDF</small></article><article><span>阻断下载</span><strong>${number(summary.blocked_downloads)}</strong><small>404 HTML，不进入数据</small></article><article><span>正式入库</span><strong>${number(summary.formal_integrated_records)}</strong><small>业务基线未改写</small></article></section><div class="table-scroll"><table class="maint-table maint-table--audit"><thead><tr><th>周期</th><th>原始文件</th><th>可解析</th><th>阻断下载</th><th>字节数</th></tr></thead><tbody>${cycleRows}</tbody></table></div><p class="maint-detail-footnote">清单 ${number(summary.supplement_manifest_rows)} 条 / 覆盖 ${number(summary.manifest_coverage)} 条；SHA-256 匹配 ${number(summary.checksum_matches)} 条，待唯一归属成绩 ${number(summary.probable_score_evidence)} 条。另有 ${number(summary.normalized_evidence_records)} 条拟聘用证据记录保存在独立 inventory 中，不并入公开招聘岗位基线。</p></section>`;
  };
  const renderAuditCenter = (globalAudit, cycleAuditPayload, reviewQueue) => {
    const summary = globalAudit.summary || {};
    const queueSummary = reviewQueue?.summary || {};
    const gaps = auditGapsFor(cycleAuditPayload);
    const audit = cycleAuditPayload.audit || {};
    const cycleItems = globalAudit.cycles || [];
    const activeFilter = state.auditFilter || 'all';
    const reviewItems = (reviewQueue?.items || []).filter((item) => activeFilter === 'all' || (activeFilter === 'high' ? ['high', 'critical'].includes(item.severity) : String(item.kind) === activeFilter));
    const filterButtons = [['all', '全部'], ['high', '高风险'], ['unpublished_or_unavailable', '未发布'], ['ambiguous_join', '连接歧义'], ['needs_review', '待复核']].map(([value, label]) => `<button type="button" data-maint-review-filter="${value}" class="${activeFilter === value ? 'is-active' : ''}">${label}</button>`).join('');
    const statusDefinitions = `<details class="maint-source-details"><summary>证据状态怎么理解</summary><p class="maint-detail-footnote">“部分证据已核验”表示岗位主表已有可复核来源，但部分报名、拟聘或成绩资料仍未发布、未回收或无法唯一匹配；空值不等于 0。</p></details>`;
    return `<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('data_boundary', '2024—2026 · 数据说明')}<h1>数据审计中心，先看证据再看结论。</h1><p>这里把三年规模、已登记公开边界和成绩匹配边界分开呈现；没有官方逐项证据时，保留空值与原因，不用推测补齐。</p></div></section><section class="maint-kpis maint-kpis--audit"><article><span>三年岗位行</span><strong data-countup>${number(summary.post_count)}</strong><small>三周期汇总</small></article><article><span>三年招录人数</span><strong data-countup>${number(summary.recruit_count)}</strong><small>公告口径合计</small></article><article><span>公开缺口事件</span><strong>${number(queueSummary.public_boundary_count ?? summary.gap_count)}</strong><small>跨三年已登记，不等同于为零</small></article><article><span>成绩待复核</span><strong>${number(queueSummary.unresolved_score_count ?? summary.unresolved_score_count)}</strong><small>无法唯一匹配</small></article></section><section class="maint-panel"><header><div><p class="maint-eyebrow">三年数据</p><h2>三年审计对照</h2></div><span class="maint-audit-date">审计快照 ${escapeHtml(globalAudit.generated_on || '—')}</span></header>${statusDefinitions}<div class="table-scroll"><table class="maint-table maint-table--audit"><thead><tr><th>周期</th><th>证据层</th><th>岗位</th><th>招录</th><th>公开缺口</th><th>成绩待复核</th><th>状态</th></tr></thead><tbody>${cycleItems.map((item) => `<tr data-maint-audit-cycle-row><th>${escapeHtml(item.cycle)}</th><td><span class="audit-chip">${escapeHtml(readableStatus(item.evidence_level || '—'))}</span></td><td>${number(item.posts)}</td><td>${number(item.recruits)}</td><td>${number((item.gaps || []).length)}</td><td>${number(item.score_unresolved)}</td><td>${escapeHtml(readableStatus(item.status || item.dominant_status || item.evidence_level || 'registered'))}</td></tr>`).join('')}</tbody></table></div></section><section class="maint-panel maint-review-panel"><header><div><p class="maint-eyebrow">待办事项 · ${number(queueSummary.event_count || reviewItems.length)}  条待办</p><h2>复核队列</h2></div><div class="review-filters">${filterButtons}</div></header><div class="review-list">${reviewItems.map((item) => `<article class="review-item" data-maint-review-item data-review-kind="${escapeHtml(item.kind)}" data-review-severity="${escapeHtml(item.severity)}"><div class="review-item__meta"><span class="audit-chip">${escapeHtml(readableStatus(item.kind))}</span><span>${escapeHtml(severityLabel(item.severity))}</span><span>${escapeHtml(item.cycle || '')}</span></div><strong>${escapeHtml(item.title || '未命名审计事件')}</strong><p>${escapeHtml(item.detail || '暂无详细说明')}</p><details class="maint-source-details"><summary>查看证据与处理条件</summary><small>来源：官方公告核对记录 · 出现 ${number(item.occurrences || 1)} 次 · ${escapeHtml(item.resolution_trigger || '取得新证据后重新构建')}</small></details></article>`).join('') || '<p class="empty">当前筛选没有复核事件。</p>'}</div></section><section class="maint-grid maint-grid--audit"><section class="maint-panel"><header><div><p class="maint-eyebrow">${escapeHtml(state.cycle)} · 登记事项</p><h2>当前周期公开缺口</h2></div></header><div class="boundary-list">${gaps.map((item) => { const text = typeof item === 'string' ? item : (item.title || item.detail || item.note || JSON.stringify(item)); const status = typeof item === 'object' ? (item.status || item.kind || 'registered') : 'registered'; return `<article><span>${escapeHtml(readableStatus(status))}</span><strong>${escapeHtml(text)}</strong><small>保持公开标记，取得官方公告后再进入构建链路。</small></article>`; }).join('') || '<p class="empty">本周期没有额外登记缺口。</p>'}</div></section><aside class="maint-panel maint-panel--note"><p class="maint-eyebrow">数据来源</p><h2>数据怎样进入页面</h2><div class="audit-chain"><span>官方/原始来源</span><b>→</b><span>周期数据包</span><b>→</b><span>数据文件</span><b>→</b><span>页面展示</span></div><p>当前周期审计状态：<strong>${escapeHtml(readableStatus(audit.evidence_level || '—'))}</strong>。</p><details class="maint-source-details"><summary>查看维护链路</summary><p class="maint-detail-footnote">数据来自官方公告与公示名单，更新时逐项人工核对后上线。</p></details></aside></section>`;
  };
  const renderHelp = () => `<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('help', '使用指南')}${state.manifest?.release ? `<small>${escapeHtml(state.manifest.release)}</small>` : ''}<h1>如何找到合适的岗位</h1><p>三步帮你快速定位目标岗位，所有数据均来自官方公告。</p></div></section><section class="maint-grid maint-grid--guide"><article class="maint-panel guide-step"><span>01</span><h2>搜索专业或城市</h2><p>在岗位检索中输入专业关键词，比如”法学””计算机””会计”，或直接选择城市筛选。系统会自动匹配相关岗位。</p><a href="#jobs_search" data-maintain-view="jobs_search">去岗位检索 →</a></article><article class="maint-panel guide-step"><span>02</span><h2>查看岗位详情</h2><p>点击岗位卡片查看完整信息：招录单位、职位代码、专业要求、学历门槛、招录人数等。竞争比和分数线一目了然。</p><a href="#jobs_ranking" data-maintain-view="jobs_ranking">去岗位榜单 →</a></article><article class="maint-panel guide-step"><span>03</span><h2>对比与收藏</h2><p>把心仪的岗位加入收藏或对比列表，方便后续筛选。收藏数据保存在本地，换设备需重新添加。</p><a href="#saved" data-maintain-view="saved">查看收藏 →</a></article></section><section class="maint-panel guide-note"><h2>如何判断一个岗位</h2><p>先筛选，再看岗位原文与证据，最后确认资料边界。页面上的“未提供”不等于 0，只有来源明确为 0 才显示 0。</p></section><section class="maint-panel guide-note"><h2>快捷操作</h2><p>按 <code>Ctrl</code>+<code>K</code> 打开搜索面板，可快速切换视图、周期或搜索岗位。<code>↑</code><code>↓</code> 选择，<code>Enter</code> 确认，<code>Esc</code> 关闭。</p></section><section class="maint-panel guide-note"><h2>数据说明</h2><p>本平台数据覆盖安徽16市，包含省考、事业编、国考三类考试。数据按年度分周期整理，支持2024-2026年对比查看。所有数据均可追溯到官方来源。</p></section><section class="maint-panel guide-note"><h2>常见问题</h2><p><strong>数据多久更新？</strong>官方公告发布后会尽快更新。<br><strong>为什么有些字段为空？</strong>官方未公布的信息会保留空白，不会推测填充。<br><strong>如何导出数据？</strong>岗位检索结果可导出 CSV；「收藏与快照」页可把收藏、对比和筛选快照一键导出为带版本的 JSON 文件，也能重新导入。</p></section>`;
  const restoreUpdateChecklist = () => {
    let done = [];
    try { done = JSON.parse(localStorage.getItem('wanyu.update.checklist.v1') || '[]'); } catch { done = []; }
    if (!Array.isArray(done)) done = [];
    document.querySelectorAll('[data-maint-check-step]').forEach((box) => { box.checked = done.includes(box.dataset.maintCheckStep); });
  };
  const renderChangelog = (globalAudit = {}, reviewQueue = {}) => {
    const summary = globalAudit.summary || {};
    const queueSummary = reviewQueue.summary || {};
    const cycles = state.manifest?.cycles || [];
    const release = state.manifest?.release || '当前版本';
    return `<section class="maint-hero maint-hero--compact"><div>${viewEyebrow('changelog', `更新日志 · ${escapeHtml(release)}`)}<h1>更新日志，记录每一次数据变化。</h1><p>每次数据更新都会逐项核对官方来源，确认无误后才上线。</p></div></section><section class="maint-panel changelog-panel"><header><div><p class="maint-eyebrow">${escapeHtml(release)} · ${escapeHtml(state.manifest?.snapshot_date || '快照日期未提供')}</p><h2>长期维护升级</h2></div><span class="maint-audit-date">${number(cycles.length)} 个周期</span></header><div class="changelog-list"><article><strong>数据组织</strong><p>岗位、专业目录、成绩等数据按年份分层存放，读取更快，也便于逐项核对。</p></article><article><strong>用户路径</strong><p>地图、岗位榜单、逐岗检索、岗位详情、收藏/对比和筛选快照在同一入口完成，筛选状态会明确显示。</p></article><article><strong>审计可见</strong><p>当前三年共 ${number(summary.post_count)} 岗、${number(summary.recruit_count)} 人；已登记公开缺口事件 ${number(queueSummary.public_boundary_count || summary.gap_count || 0)} 项，成绩无法唯一匹配 ${number(queueSummary.unresolved_score_count || summary.unresolved_score_count || 0)} 条。未取得的数值一律留空，不用推测补齐。</p></article><article><strong>数据更新方式</strong><p>三年数据按周期独立存放，更新时逐周期替换，不会影响已有年份。</p></article></div></section><section class="maint-callout"><strong>下一次更新</strong><span>下一个周期官方公告发布后，我们会尽快核对并更新，请留意页面提示。</span></section>`;
  };

  const render = async (opts = {}) => {
    const instant = opts.instant === true;
    const token = ++state.renderToken;
    renderNav();
    if (!state.manifest || !state.cycle) return;
    try {
      const skeletonModules = { overview: ['overview', 'jobs_lite'], jobs_map: [], jobs_ranking: ['jobs_lite'], jobs_search: ['jobs_lite'], saved: ['jobs_lite'], changes: ['changes'] };
      const pendingSkeleton = (skeletonModules[state.view] || []).some((module) => !state.modules.has(`${state.cycle}:${module}`));
      if (pendingSkeleton) {
        main.innerHTML = skeletonMarkup(state.view);
        setStatus(`${state.cycle} 周期数据加载中…`, 'busy');
      }
      let markup = '';
      if (state.view === 'help') {
        markup = renderHelp();
      } else if (state.view === 'changelog') {
        const [globalAudit, reviewQueue] = await Promise.all([loadGlobalAudit(), loadReviewQueue()]);
        markup = renderChangelog(globalAudit, reviewQueue);
      } else if (state.view === 'cycle_compare') {
        const changeCycles = (state.manifest?.cycles || []).filter((item) => item.modules?.changes && item.cycle !== state.manifest?.cycles?.[0]?.cycle);
        const changes = await Promise.all(changeCycles.map((item) => loadModule(item.cycle, 'changes')));
        let derived = null;
        try { derived = await loadModule(state.cycle, 'derived'); } catch (error) { derived = null; }
        state.derivedData = derived; // 保存到state供事件处理使用
        // P0-9: 三年全量 jobs.json(36MB) 只在考试筛选激活时加载——无筛选时 slopeGraph 只用 2.4KB 的 derived 聚合
        const hasExamScope = (state.examFilter && state.examFilter !== '全部') || Boolean(state.examSub);
        if (hasExamScope) {
          const allCycles = state.manifest?.cycles || [];
          await Promise.all(allCycles.map(c => loadModule(c.cycle, 'jobs')));
        }
        await loadSalary(); // 加载待遇数据用于城市对比
        markup = renderCompare(changes, derived);
      } else if (state.view === 'saved') {
        await loadModule(state.cycle, 'jobs_lite');
        let savedChanges = null;
        try {
          const store0 = window.WanyuUserStore;
          if ((store0?.loadPositions?.() || []).length && moduleUrl(state.cycle, 'changes')) savedChanges = await loadModule(state.cycle, 'changes');
        } catch (error) { savedChanges = null; }
        markup = renderSaved(savedChanges);
      } else if (state.view === 'changes') {
        const hasChangesModule = Boolean(moduleUrl(state.cycle, 'changes'));
        const changes = hasChangesModule ? await loadModule(state.cycle, 'changes') : null;
        markup = renderChanges(changes);
      } else if (state.view === 'data_boundary') {
        const [globalAudit, cycleAudit, reviewQueue, supplement] = await Promise.all([loadGlobalAudit(), loadModule(state.cycle, 'audit'), loadReviewQueue(), loadSupplementEvidence()]);
        markup = `${renderAuditCenter(globalAudit, cycleAudit, reviewQueue)}${renderSupplementEvidence(supplement)}`;
      } else if (state.view === 'jobs_map') {
        const mapPromise = loadMap();
        let jobs = null;
        let majorIndex = null;
        const hasExamScope = (state.examFilter && state.examFilter !== '全部') || Boolean(state.examSub);
        if (state.mapMajor && !hasExamScope) {
          try { majorIndex = await loadModule(state.cycle, 'major_city'); } catch (error) { majorIndex = null; }
          const indexedKey = window.WanyuMajorCityIndex?.majorIndexKey?.(majorIndex, state.mapMajor) || '';
          if (!indexedKey) jobs = await loadModule(state.cycle, 'jobs_lite');
        } else {
          jobs = await loadModule(state.cycle, 'jobs_lite');
        }
        const map = await mapPromise;
        await loadSalary();
        const exam = state.examFilter || '全部';
        const examJobs = jobs ? scopeExamPayload(jobs) : null;
        markup = renderMap(map, examJobs, majorIndex);
      } else if (state.view === 'salary_map') {
        await loadMap();
        await loadSalary();
        markup = renderSalaryMap();
      } else if (state.view === 'match') {
        await loadModule(state.cycle, 'jobs_lite');
        const matchCatalog = await loadModule(state.cycle, 'catalog');
        let matchIndex = null;
        try { matchIndex = await loadModule(state.cycle, 'major_index'); } catch (error) { matchIndex = null; }
        let matchReq = null;
        const mp = readProfile();
        if (profileActive(mp)) {
          matchReq = state.modules.get(`${state.cycle}:req_fields`) || null;
          if (!matchReq) void loadModule(state.cycle, 'req_fields').then(() => { if (state.view === 'match') render(); }).catch(() => {});
        }
        markup = renderMatch(scopeExamPayload(state.modules.get(`${state.cycle}:jobs_lite`)), matchCatalog, matchIndex, matchReq);
      } else if (state.view === 'calendar') {
        let cal = null;
        try { cal = await state.dataStore.loadGlobal('calendar'); } catch (error) { cal = null; }
        markup = renderCalendar(cal);
      } else {
        const overview = await loadModule(state.cycle, 'overview');
        const jobs = await loadModule(state.cycle, 'jobs_lite');
        let derived = null;
        try { derived = await loadModule(state.cycle, 'derived'); } catch (error) { derived = null; }
        const catalog = ['jobs_ranking', 'jobs_search'].includes(state.view) ? await loadModule(state.cycle, 'catalog') : null;
        let majorIndex = null;
        if (state.view === 'jobs_search' && normalize(state.searchMajor)) {
          majorIndex = state.modules.get(`${state.cycle}:major_index`) || null;
          if (!majorIndex) {
            void loadModule(state.cycle, 'major_index').then(() => { if (state.view === 'jobs_search' && normalize(state.searchMajor)) render(); }).catch(() => {});
          }
        }
        const scopedJobs = scopeExamPayload(jobs);
        let reqFields = null;
        if (state.view === 'jobs_search') {
          const activeProfile = readProfile();
          if (profileActive(activeProfile)) {
            reqFields = state.modules.get(`${state.cycle}:req_fields`) || null;
            if (!reqFields) {
              void loadModule(state.cycle, 'req_fields').then(() => { if (state.view === 'jobs_search') render(); }).catch(() => {});
            }
          }
        }
        const views = { overview: () => renderOverview(overview, scopedJobs, derived), jobs_ranking: () => renderRanking(scopedJobs, catalog), jobs_search: () => renderSearch(scopedJobs, catalog, majorIndex, reqFields) };
        markup = (views[state.view] || views.overview)();
      }
      if (token !== state.renderToken) return;
      state.detail = null;
      main.innerHTML = markup;
      if (state.view === 'jobs_search') main.querySelector('.maint-toolbar--search')?.insertAdjacentHTML('beforebegin', searchFlowMarkup());
      state.notice = '';
      if (instant) main.querySelectorAll(REVEAL_SELECTOR).forEach((node) => node.classList.add('is-in'));
      hydrateMotion();
      if (state.view === 'help') restoreUpdateChecklist();
      // 在三年对照页面插入竞争热力图和城市对比工具
      if (state.view === 'cycle_compare') {
        const container = document.querySelector('#v17-tools-container');
        if (container && window.renderCompetitionHeatmap && window.renderCityComparison) {
          const jobs = state.modules.get(`${state.cycle}:jobs`) || state.modules.get(`${state.cycle}:jobs_lite`);
          const salary = state.salaryData;
          if (jobs) {
            let toolsHtml = '';
            if (window.renderCompetitionHeatmap) toolsHtml += window.renderCompetitionHeatmap(jobs, state.cycle, state.examFilter || '全部', state.examSub || '');
            if (window.renderCityComparison) toolsHtml += window.renderCityComparison(jobs, salary, state.cycle, state.examFilter || '全部', state.examSub || '');
            container.innerHTML = toolsHtml;
          }
        }
      }
      const rowsPayload = state.modules.get(`${state.cycle}:jobs_lite`) || state.modules.get(`${state.cycle}:jobs`);
      setStatus(`${state.cycle} · 数据已就绪 · ${rowsPayload ? `${number(rowsFor(rowsPayload).length)} 个岗位` : '审计数据'}`, 'ready');
    } catch (error) {
      if (token === state.renderToken) showError(error);
    }
  };
  const setView = async (view) => {
    state.view = validViews.has(view) ? view : 'overview';
    if (location.hash.slice(1) !== state.view) history.replaceState({}, '', `${location.pathname}${location.search}#${state.view}`);
    await render();
  };
  const viewTitles = Object.fromEntries(Object.entries(VIEW_META).map(([view, names]) => [view, names.full]));
  const skeletonMarkup = (view) => `<section class="maint-hero maint-hero--compact"><div><p class="maint-eyebrow">${escapeHtml(state.cycle)} · 加载中</p><h1>正在加载${escapeHtml(viewTitles[view] || '数据')}…</h1><p>数据按需加载，马上就好。</p></div></section><section class="maint-panel maint-skeleton" role="status" aria-label="数据加载中"><i></i><i style="animation-delay:.15s"></i><i style="animation-delay:.3s"></i><i style="animation-delay:.45s"></i></section>`;
  const showError = (error) => {
    setStatus('数据加载失败', 'error');
    main.innerHTML = `<section class="maint-error"><strong>维护站暂时无法加载数据</strong><p>${escapeHtml(error.message || error)}</p><small>若您以本地文件方式打开本页，请改用在线地址访问；技术细节请联系站点维护者。</small><div><button type="button" class="maint-primary-action" data-maint-retry>重试加载</button></div></section>`;
  };
  const renderPreservingInput = async (id, update) => {
    const input = document.querySelector(`#${id}`); const start = input?.selectionStart; const end = input?.selectionEnd;
    update(); await render({ instant: true }); const next = document.querySelector(`#${id}`);
    if (next) { next.focus(); const length = next.value.length; next.setSelectionRange(Math.min(start ?? length, length), Math.min(end ?? length, length)); }
  };
  let inputRenderTimer = null;
  const debouncedInputRender = (id, update) => {
    update();
    clearTimeout(inputRenderTimer);
    inputRenderTimer = setTimeout(() => { renderPreservingInput(id, () => {}); }, 180);
  };
  const onAppClick = async (event) => {
    const mobileMoreToggle = event.target.closest('[data-maint-mobile-more-toggle]');
    if (mobileMoreToggle) {
      const menu = document.querySelector('[data-maint-mobile-more]');
      if (menu) {
        const nextOpen = menu.hidden;
        menu.hidden = !nextOpen;
        mobileMoreToggle.setAttribute('aria-expanded', String(nextOpen));
        if (nextOpen) document.querySelector('[data-maint-mobile-more-close]')?.focus();
      }
      return;
    }
    if (event.target.closest('[data-maint-mobile-more-close]') || event.target.matches('[data-maint-mobile-more]')) {
      closeMobileMore();
      return;
    }
    if (event.target.closest('[data-maint-retry]')) { await render(); return; }
    const copyCmdTrigger = event.target.closest('[data-maint-copy-cmd]');
    if (copyCmdTrigger) {
      const command = copyCmdTrigger.dataset.maintCopyCmd || '';
      navigator.clipboard?.writeText(command)
        .then(() => setStatus('命令已复制到剪贴板', 'ready'))
        .catch(() => setStatus('复制失败，请手动选择命令文本', 'error'));
      return;
    }
    if (event.target.closest('[data-maint-export-workspace]')) {
      const store = window.WanyuUserStore;
      if (!store) return;
      const blob = new Blob([store.exportAll()], { type: 'application/json' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `wanyu-workspace-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(link.href), 0);
      state.notice = '工作台已导出（快照/收藏/对比）';
      await render();
      return;
    }
    if (event.target.closest('[data-maint-import-workspace]')) {
      const picker = document.createElement('input');
      picker.type = 'file';
      picker.accept = 'application/json,.json';
      picker.onchange = async () => {
        const file = picker.files?.[0];
        if (!file) return;
        try {
          const counts = window.WanyuUserStore.importAll(await file.text());
          state.notice = `工作台已导入：快照 ${number(counts.snapshots)} · 收藏 ${number(counts.positions)} · 对比 ${number(counts.compare)}`;
        } catch (error) {
          state.notice = `导入失败：${error.message}`;
        }
        await render();
      };
      picker.click();
      return;
    }
    if (event.target.matches('[data-maint-palette]')) { closePalette(); return; }
    const paletteItem = event.target.closest('[data-maint-palette-item]');
    if (paletteItem) { void paletteExecute(palette.items[Number(paletteItem.dataset.index)]); return; }
    if (event.target.closest('[data-maint-detail-close]') || event.target.matches('[data-maint-detail-drawer]')) { closeDetail(); return; }
    const detailTrigger = event.target.closest('[data-maint-position-detail]');
    if (detailTrigger) { await openDetail(detailTrigger.dataset.recordId); return; }
    const mapMetricTrigger = event.target.closest('[data-maint-map-metric]');
    if (mapMetricTrigger) { const next = mapMetricTrigger.dataset.maintMapMetric; state.mapMetric = next === 'recruits' || next === 'salary' ? next : 'jobs'; await render({ instant: true }); return; }
    const salaryTypeTrigger = event.target.closest('[data-maint-salary-type]');
    if (salaryTypeTrigger) { state.salaryType = salaryTypeTrigger.dataset.maintSalaryType === '事业编' ? '事业编' : '公务员'; await render({ instant: true }); return; }
    const salaryStageTrigger = event.target.closest('[data-maint-salary-stage]');
    if (salaryStageTrigger) { state.salaryStage = salaryStageTrigger.dataset.maintSalaryStage || state.salaryStage; await render({ instant: true }); return; }
    const mapQuickMajor = event.target.closest('[data-maint-map-quick-major]');
    if (mapQuickMajor) { state.mapMajor = mapQuickMajor.dataset.maintMapQuickMajor || ''; if (state.mapMetric === 'salary') state.mapMetric = 'jobs'; await render({ instant: true }); return; }
    if (event.target.closest('[data-maint-map-clear-major]')) { state.mapMajor = ''; await render({ instant: true }); return; }
    const mapCityTrigger = event.target.closest('[data-maint-map-city]');
    if (mapCityTrigger) { const value = mapCityTrigger.dataset.maintMapCity || ''; state.mapCity = state.mapCity === value ? '' : value; await render({ instant: true }); return; }
    const mapOpenCityTrigger = event.target.closest('[data-maint-map-open-city]');
    if (mapOpenCityTrigger) {
      state.keyword = '';
      state.searchMajor = state.mapMajor || '';
      state.city = '';
      state.exam = '';
      state.searchSort = 'source';
      state.searchPageSize = 60;
      state.searchCityGroup = mapOpenCityTrigger.dataset.maintMapOpenCity || '';
      state.searchPage = 0;
      state.notice = `已按${cityDisplay(state.searchCityGroup)}地图汇总筛选`;
      await setView('jobs_search');
      return;
    }
    if (event.target.closest('[data-maint-clear-city-group]')) { state.searchCityGroup = ''; state.searchPage = 0; await render(); return; }
    // 三年对照图表城市选择器
    if (event.target.closest('[data-maint-slope-update]')) {
      const select = document.querySelector('[data-maint-slope-cities]');
      if (select) {
        const selected = Array.from(select.selectedOptions).slice(0, 5).map(opt => opt.value);
        if (selected.length > 0) {
          const trend = state.derivedData?.city_trend || {};
          const cycles = state.manifest?.cycles || [];
          const width = 640; const height = 280; const pad = 40;
          const allValues = selected.flatMap(city => cycles.map(c => Number(trend[city]?.posts?.[c.cycle]))).filter(v => Number.isFinite(v));
          if (allValues.length > 0) {
            const max = Math.max(...allValues);
            const xs = cycles.map((_, i) => pad + i * ((width - pad * 2) / (cycles.length - 1)));
            const y = (v) => height - pad - (v / max) * (height - pad * 2);
            const colors = ['var(--viz-1)', 'var(--viz-2)', 'var(--viz-3)', 'var(--viz-4)', 'var(--viz-5)', 'var(--viz-6)', 'var(--viz-7)', 'var(--viz-8)'];
            const lines = selected.map((city, idx) => {
              const points = cycles.map((c, i) => {
                const v = Number(trend[city]?.posts?.[c.cycle]);
                return Number.isFinite(v) ? `${xs[i].toFixed(1)},${y(v).toFixed(1)}` : null;
              }).filter(Boolean);
              if (points.length < 2) return '';
              return `<polyline points="${points.join(' ')}" style="stroke:${colors[idx % colors.length]}" stroke-width="2" fill="none"><title>${cityDisplay(city)}：${cycles.map(c => `${c.year}年 ${number(trend[city]?.posts?.[c.cycle])}个岗位`).join('、')}</title></polyline>`;
            }).join('');
            const yearLabels = cycles.map((c, i) => `<text x="${xs[i]}" y="${pad - 15}" text-anchor="${i === 0 ? 'start' : i === cycles.length - 1 ? 'end' : 'middle'}" font-size="14" style="fill:var(--text-muted)">${c.year}年</text>`).join('');
            const legend = selected.map((city, idx) => {
              const vals = cycles.map(c => Number(trend[city]?.posts?.[c.cycle]));
              if (vals.some(v => !Number.isFinite(v))) return '';
              const first = vals[0]; const last = vals[vals.length - 1];
              const arrow = last > first ? '↑' : last < first ? '↓' : '→';
              return `<span style="margin-right:12px"><i style="display:inline-block;width:12px;height:12px;background:${colors[idx % colors.length]};margin-right:4px;border-radius:2px"></i>${cityDisplay(city)} ${vals.map(number).join(' → ')} ${arrow}</span>`;
            }).join('');
            const chartDiv = document.querySelector('.maint-slope-chart');
            if (chartDiv) {
              chartDiv.innerHTML = `<svg viewBox="0 0 ${width} ${height}" style="width:100%;max-width:${width}px">${yearLabels}${lines}</svg><div style="margin-top:12px;font-size:13px">${legend}</div>`;
            }
          }
        }
      }
      return;
    }
    const rankingCityTrigger = event.target.closest('[data-maint-ranking-city]');
    if (rankingCityTrigger) {
      state.keyword = '';
      state.city = rankingCityTrigger.dataset.maintRankingCity || '';
      state.exam = state.ranking.exam || '';
      state.searchMajor = state.ranking.major || '';
      state.searchCityGroup = '';
      state.searchSort = 'source';
      state.searchPageSize = 60;
      state.searchPage = 0;
      await setView('jobs_search');
      return;
    }
    const quickMajor = event.target.closest('[data-maint-quick-major]');
    if (quickMajor) {
      const value = quickMajor.dataset.maintQuickMajor || '';
      if (quickMajor.dataset.maintQuickTarget === 'ranking') state.ranking.major = value;
      else state.searchMajor = value;
      state.searchPage = 0;
      await render();
      return;
    }
    const clearFilter = event.target.closest('[data-maint-clear-filter]');
    if (clearFilter) {
      const key = clearFilter.dataset.maintClearFilter || '';
      if (key === 'search.keyword') state.keyword = '';
      if (key === 'search.major') state.searchMajor = '';
      if (key === 'search.city') state.city = '';
      if (key === 'search.cityGroup') state.searchCityGroup = '';
      if (key === 'search.exam') state.exam = '';
      state.searchPage = 0;
      await render();
      return;
    }
    if (event.target.closest('[data-maint-steal-toggle]')) {
      state.searchSteal = !state.searchSteal;
      state.searchPage = 0;
      await render({ instant: true });
      return;
    }
    if (event.target.closest('[data-maint-share-job]')) {
      const btn = event.target.closest('[data-maint-share-job]');
      const row = rowsFor(state.modules.get(`${state.cycle}:jobs`) || state.modules.get(`${state.cycle}:jobs_lite`) || null).find((item) => String(item.job_id || item.code) === String(btn.dataset.recordId));
      if (!row) { setStatus('分享失败：岗位数据未加载', 'error'); return; }
      const num = Number(row.num ?? row.recruits ?? 0);
      const examinees = Number(row.competition_observations?.examinees?.value ?? row.bm ?? 0);
      const lineVal = row.score_observation?.status === 'comparable' ? row.score_observation.value : null;
      const url = `${location.origin}${location.pathname}?cycle=${encodeURIComponent(state.cycle)}#job/${encodeURIComponent(String(row.job_id || row.code))}`;
      const text = `${row.unit || ''} ${row.zw || row.display_title || ''}（${row.city || ''} · ${row.code || ''}）招${num || '?'}人，官方报名${examinees > 0 ? examinees : '未公布'}人，入围线${lineVal != null ? lineVal : '未公布'} ${url}`;
      navigator.clipboard?.writeText(text).then(() => setStatus('分享文本已复制，可粘贴给研友', 'ready')).catch(() => setStatus('复制失败：浏览器未授权剪贴板', 'error'));
      return;
    }
    if (event.target.closest('[data-maint-match-go]')) {
      const input = document.getElementById('maint-match-major');
      state.matchMajor = normalize(input?.value || '');
      render();
      return;
    }
    if (event.target.closest('[data-maint-profile-toggle]')) {
      state.profileOpen = !state.profileOpen;
      render();
      return;
    }
    if (event.target.closest('[data-maint-profile-clear]')) {
      writeProfile({ gender: '', fresh: '', party: '', legal: '', age: '' });
      state.profileOpen = true;
      render();
      return;
    }
    if (event.target.closest('[data-maint-clear-search]')) {
      state.keyword = '';
      state.searchMajor = '';
      state.city = '';
      state.searchCityGroup = '';
      state.exam = '';
      state.searchSteal = false;
      state.searchPage = 0;
      state.notice = '筛选已清空';
      await render();
      return;
    }
    const savePositionButton = event.target.closest('[data-maint-save-position]');
    if (savePositionButton) {
      window.WanyuUserStore?.savePosition(savePositionButton.dataset.recordId);
      savePositionButton.textContent = '已收藏';
      setStatus('岗位已收藏', 'ready');
      return;
    }
    const compareButton = event.target.closest('[data-maint-position-compare]');
    if (compareButton) {
      const recordId = compareButton.dataset.recordId || '';
      const current = window.WanyuUserStore?.loadCompare?.() || [];
      const next = current.includes(recordId)
        ? window.WanyuUserStore?.removeCompare?.(recordId)
        : window.WanyuUserStore?.saveCompare?.(recordId);
      compareButton.textContent = (next || []).includes(recordId) ? '移出对比' : '加入对比';
      setStatus((next || []).includes(recordId) ? '已加入岗位对比' : '已移出岗位对比', 'ready');
      return;
    }
    const savedPosition = event.target.closest('[data-maint-saved-position]');
    if (savedPosition && !savedPosition.disabled) {
      await openDetail(savedPosition.dataset.recordId || '');
      return;
    }
    const removeCompare = event.target.closest('[data-maint-remove-compare]');
    if (removeCompare) {
      window.WanyuUserStore?.removeCompare?.(removeCompare.dataset.recordId || '');
      state.notice = '已移出岗位对比';
      await render();
      return;
    }
    const saveFilterButton = event.target.closest('[data-maint-save-filter]');
    if (saveFilterButton) { saveCurrentFilter(saveFilterButton.dataset.filterView || state.view); await render(); return; }
    if (event.target.closest('[data-maint-export-search]')) { exportCurrentSearch(); await render(); return; }
    if (event.target.closest('[data-maint-export-compare]')) { exportCompareCsv(); await render(); return; }
    const reviewFilterButton = event.target.closest('[data-maint-review-filter]');
    if (reviewFilterButton) { state.auditFilter = reviewFilterButton.dataset.maintReviewFilter || 'all'; await render(); return; }
    // 变更通报：状态筛选 chips（全部/新增/撤回/信息修订/待人工复核）
    const changesFilterTrigger = event.target.closest('[data-maint-changes-filter]');
    if (changesFilterTrigger) {
      const next = changesFilterTrigger.dataset.maintChangesFilter || 'all';
      state.changesFilter = ['added', 'withdrawn', 'revised', 'needs_review'].includes(next) ? next : 'all';
      await render({ instant: true });
      return;
    }
    const searchPageButton = event.target.closest('[data-maint-search-page]');
    if (searchPageButton && !searchPageButton.disabled) { state.searchPage += searchPageButton.dataset.maintSearchPage === 'next' ? 1 : -1; await render(); return; }
    const loadSnapshotButton = event.target.closest('[data-maint-load-snapshot]');
    if (loadSnapshotButton) {
      const snapshot = window.WanyuUserStore?.loadFilterSnapshots?.().find((item) => item.id === loadSnapshotButton.dataset.snapshotId);
      if (snapshot) {
        const filters = snapshot.filters || {};
        if ((snapshot.view || 'jobs_search') === 'jobs_ranking') state.ranking = { major: filters.major || '', city: filters.city || '', exam: filters.exam || '', category: filters.category || '', metric: filters.metric || snapshot.metric || 'jobs' };
        else { state.keyword = filters.keyword || ''; state.searchMajor = filters.major || ''; state.city = filters.city || ''; state.searchCityGroup = filters.cityGroup || ''; state.exam = filters.exam || ''; state.searchPage = 0; }
        await setView(snapshot.view || 'jobs_search'); state.notice = '筛选快照已恢复'; await render();
      }
      return;
    }
    const removePositionButton = event.target.closest('[data-maint-remove-position]');
    if (removePositionButton) { window.WanyuUserStore?.removePosition(removePositionButton.dataset.recordId); state.notice = '已移除收藏'; await render(); return; }
    const cycle = event.target.closest('[data-maintain-cycle]')?.dataset.maintainCycle;
    if (cycle) { try { await loadCycle(cycle); await render(); } catch (error) { showError(error); } return; }
    // 考试类别筛选
    const examFilter = event.target.closest('[data-maint-exam-filter]')?.dataset.maintExamFilter;
    if (examFilter) {
      state.examFilter = examFilter;
      state.examSub = '';
      await render();
      return;
    }
    const examSubFilter = event.target.closest('[data-maint-exam-sub]');
    if (examSubFilter && !examSubFilter.disabled) {
      state.examSub = examSubFilter.dataset.maintExamSub || '';
      state.searchPage = 0;
      await render({ instant: true });
      return;
    }
    if (event.target.closest('[data-maintain-clear-ranking]')) { state.ranking = { major: '', city: '', exam: '', category: '', metric: 'jobs' }; await render(); return; }
    const link = event.target.closest('[data-maintain-view]');
    if (link) { event.preventDefault(); closeMobileMore(); await setView(link.dataset.maintainView); }
  };
  app.addEventListener('click', (event) => { onAppClick(event).catch((error) => { showError(error); }); });
  addEventListener('unhandledrejection', (event) => { setStatus(`未处理的错误：${String((event.reason && (event.reason.message || event.reason)) || '未知').slice(0, 80)}`, 'error'); });
  addEventListener('keydown', async (event) => {
    if ((event.ctrlKey || event.metaKey) && String(event.key).toLowerCase() === 'k') {
      event.preventDefault();
      if (palette.open) closePalette(); else void openPalette();
      return;
    }
    if (palette.open) {
      if (event.key === 'Escape') { event.preventDefault(); closePalette(); return; }
      if (event.key === 'ArrowDown') { event.preventDefault(); palette.active = Math.min(palette.active + 1, Math.max(0, palette.items.length - 1)); paletteRender(); return; }
      if (event.key === 'ArrowUp') { event.preventDefault(); palette.active = Math.max(0, palette.active - 1); paletteRender(); return; }
      if (event.key === 'Enter') { event.preventDefault(); void paletteExecute(palette.items[palette.active]); return; }
      return;
    }
    if (event.key === '/' && !['INPUT', 'SELECT', 'TEXTAREA'].includes(event.target?.tagName || '') && !event.target?.isContentEditable) {
      event.preventDefault();
      void openPalette();
      return;
    }
    if (event.key === 'Escape' && state.detail) closeDetail();
    const mapCityTrigger = event.target.closest?.('[data-maint-map-city]');
    if (mapCityTrigger && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      const value = mapCityTrigger.dataset.maintMapCity || '';
      state.mapCity = state.mapCity === value ? '' : value;
      await render({ instant: true });
    }
  });
  app.addEventListener('input', (event) => {
    if (event.isComposing) return;
    if (event.target.matches('[data-maint-check-step]')) {
      const done = new Set(JSON.parse(localStorage.getItem('wanyu.update.checklist.v1') || '[]'));
      if (event.target.checked) done.add(event.target.dataset.maintCheckStep); else done.delete(event.target.dataset.maintCheckStep);
      localStorage.setItem('wanyu.update.checklist.v1', JSON.stringify([...done]));
      return;
    }
    if (event.target.id === 'maint-palette-input') { palette.query = event.target.value; palette.active = 0; paletteRender(); return; }
    const textInput = applyTextInputValue(event.target.id, event.target.value);
    if (textInput) return;
  });
  // 专业/关键词类输入框:键入期间只记值,不重建页面——否则原生建议下拉会被关掉,没法选专业。
  // 结果刷新时机:选中建议(change)、按回车(change自动触发)、离开输入框(focusout 延迟150ms,先让点击落地)。
  const applyTextInputValue = (id, value) => {
    switch (id) {
      case 'maint-ranking-major': state.ranking.major = value; return true;
      case 'maint-map-major': state.mapMajor = value; if (state.mapMetric === 'salary') state.mapMetric = 'jobs'; return true;
      case 'maint-search-keyword': state.keyword = value; state.searchPage = 0; return true;
      case 'maint-search-major': state.searchMajor = value; state.searchPage = 0; return true;
      case 'maint-match-major': state.matchMajor = normalize(value); return true;
      case 'maint-profile-age':
      case 'maint-profile-gender':
      case 'maint-profile-fresh':
      case 'maint-profile-party':
      case 'maint-profile-legal': {
        const key = event.target.id.replace('maint-profile-', '');
        const next = readProfile();
        next[key] = value;
        writeProfile(next);
        state.searchPage = 0;
        return true;
      }
      default: return false;
    }
  };

  app.addEventListener('focusout', (event) => {
    if (!event.target?.id || !applyTextInputValue(event.target.id, event.target.value)) return;
    setTimeout(() => { void renderPreservingInput(event.target.id, () => {}); }, 150);
  });
  // 输入法组合结束后再处理一次输入,避免拼音候选被DOM重建打断成英文字母
  addEventListener('compositionend', (event) => {
    if (event.target && event.target.id) event.target.dispatchEvent(new Event('input', { bubbles: true }));
  });
  app.addEventListener('change', (event) => {
    if (applyTextInputValue(event.target.id, event.target.value)) { void renderPreservingInput(event.target.id, () => {}); return; }
    const rankingFields = { 'maint-ranking-city': 'city', 'maint-ranking-exam': 'exam', 'maint-ranking-category': 'category', 'maint-ranking-metric': 'metric' };
    if (rankingFields[event.target.id]) { state.ranking[rankingFields[event.target.id]] = event.target.value; void render({ instant: true }); }
    if (event.target.id === 'maint-search-city') { state.city = event.target.value; state.searchCityGroup = ''; state.searchPage = 0; void render({ instant: true }); }
    if (event.target.id === 'maint-search-exam') { state.exam = event.target.value; state.searchPage = 0; void render({ instant: true }); }
    if (event.target.id === 'maint-search-sort') { state.searchSort = event.target.value || 'source'; state.searchPage = 0; void render({ instant: true }); }
    if (event.target.id === 'maint-search-page-size') { state.searchPageSize = Number(event.target.value) || 60; state.searchPage = 0; void render({ instant: true }); }
    if (event.target.id === 'maint-search-density') { state.searchDensity = event.target.value === 'compact' ? 'compact' : 'comfortable'; void render({ instant: true }); }
    if (event.target.id === 'maint-search-education') { state.education = event.target.value; state.searchPage = 0; void render({ instant: true }); }
  });
  addEventListener('hashchange', () => {
    const hash = (location.hash || '#overview').slice(1);
    const jobMatch = hash.match(/^job\/(.+)$/);
    if (jobMatch) {
      if (state.manifest) void openDetail(decodeURIComponent(jobMatch[1]), { fromHash: true });
      return;
    }
    state.view = validViews.has(hash) ? hash : 'overview';
    void render();
  });
  main.addEventListener('pointermove', (event) => {
    if (!motion.enabled) return;
    const stamp = event.target?.closest?.('.maint-hero__stamp') || null;
    if (stamp !== motion.tiltTarget) {
      if (motion.tiltTarget) resetTilt(motion.tiltTarget);
      motion.tiltTarget = stamp;
    }
    if (stamp) applyTilt(stamp, event);
  });
  initMotion();
  const scrollProgress = document.querySelector('.maintain-scroll-progress');
  let progressQueued = false;
  const paintProgress = () => {
    progressQueued = false;
    if (!scrollProgress) return;
    const max = document.documentElement.scrollHeight - window.innerHeight;
    scrollProgress.style.transform = `scaleX(${max > 0 ? Math.min(1, window.scrollY / max) : 0})`;
  };
  const queueProgress = () => { if (progressQueued) return; progressQueued = true; requestAnimationFrame(paintProgress); };
  if (scrollProgress) {
    addEventListener('scroll', queueProgress, { passive: true });
    addEventListener('resize', queueProgress, { passive: true });
    paintProgress();
  }
  const headerEl = document.querySelector('.maintain-header');
  const setHeaderVar = () => { if (headerEl) document.documentElement.style.setProperty('--header-h', `${headerEl.offsetHeight}px`); };
  setHeaderVar();
  addEventListener('resize', setHeaderVar);
  const start = async () => {
    try {
      if (location.protocol === 'file:') throw new Error('当前以本地文件方式打开，无法读取数据；请通过在线地址访问本站。');
      const response = await fetch('data/site-manifest.json', { cache: 'no-cache' });
      if (!response.ok) throw new Error(`data/site-manifest.json · HTTP ${response.status}`);
      state.manifest = await response.json();
      if (!window.WanyuDataStore?.DataStore) throw new Error('维护站缺少 DataStore 资产');
      state.dataStore = new window.WanyuDataStore.DataStore(state.manifest);
      const startHash = (location.hash || '').slice(1);
      const startJob = startHash.match(/^job\/(.+)$/);
      state.view = validViews.has(startHash) ? startHash : 'overview';
      const params = new URL(location.href).searchParams;
      const requested = params.get('cycle');
      const requestedMajor = String(params.get('major') || '').trim();
      if (requestedMajor) state.mapMajor = requestedMajor;
      if (requestedMajor && (!startHash || startHash === 'overview')) state.view = 'jobs_map';
      const defaultCycle = state.manifest.default_cycle || '2026';
      await loadCycle(state.manifest.cycles.some((item) => item.cycle === requested) ? requested : defaultCycle);
      await render();
      if (startJob) await openDetail(decodeURIComponent(startJob[1]), { fromHash: true });
    } catch (error) { showError(error); }
  };
  window.WanyuMaintainableSite = Object.freeze({ loadCycle, render: setView, state });
  start();
})();
