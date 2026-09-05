(() => {
  const payloadNodes = [...document.querySelectorAll('script[data-cycle-payload]')];
  const templateNodes = [...document.querySelectorAll('template[data-cycle-template]')];
  const payloadCache = new Map();
  const templateCache = new Map(templateNodes.map((node) => [String(node.dataset.cycleTemplate), node]));
  const cycles = Object.freeze(payloadNodes.map((node) => String(node.dataset.cyclePayload)).filter((value, index, values) => values.indexOf(value) === index));
  const defaultCycle = document.documentElement.dataset.defaultCycle || '2026';
  const appSource = document.querySelector('script[data-v12-app]')?.textContent || '';
  const trackedListeners = [];
  let tracking = false;
  let appGeneration = 0;
  const eventTarget = window.EventTarget?.prototype;
  const nativeAddEventListener = eventTarget?.addEventListener;
  const nativeRemoveEventListener = eventTarget?.removeEventListener;
  if (eventTarget && nativeAddEventListener && nativeRemoveEventListener && !eventTarget.__wanyuCycleTracking) {
    const trackedAdd = function(type, listener, options) {
      const result = nativeAddEventListener.call(this, type, listener, options);
      if (tracking && listener) trackedListeners.push({ target: this, type, listener, options, generation: appGeneration });
      return result;
    };
    const trackedRemove = function(type, listener, options) {
      const result = nativeRemoveEventListener.call(this, type, listener, options);
      for (let index = trackedListeners.length - 1; index >= 0; index -= 1) {
        const entry = trackedListeners[index];
        if (entry.target === this && entry.type === type && entry.listener === listener) trackedListeners.splice(index, 1);
      }
      return result;
    };
    trackedAdd.__wanyuCycleTracking = true;
    eventTarget.addEventListener = trackedAdd;
    eventTarget.removeEventListener = trackedRemove;
  }
  const disposeApp = () => {
    tracking = false;
    subscribers?.clear();
    for (let index = trackedListeners.length - 1; index >= 0; index -= 1) {
      const entry = trackedListeners[index];
      if (entry.generation !== appGeneration) continue;
      nativeRemoveEventListener?.call(entry.target, entry.type, entry.listener, entry.options);
      trackedListeners.splice(index, 1);
    }
  };
  const appSourceForRun = () => document.querySelector('script[data-v12-app]')?.textContent || appSource;
  const runApp = () => {
    const source = appSourceForRun();
    if (!source.trim()) return;
    appGeneration += 1;
    tracking = true;
    try {
      new Function(source)();
    } catch (error) {
      console.error('[wanyu-cycle] app rehydrate failed', { cycle: active, message: error.message });
    }
  };
  let active = null;
  let warnedInvalid = false;

  const validCycle = (cycle) => cycles.includes(String(cycle));
  const readPayload = (cycle) => {
    const key = String(cycle);
    if (payloadCache.has(key)) return payloadCache.get(key);
    const node = payloadNodes.find((item) => String(item.dataset.cyclePayload) === key);
    if (!node) return null;
    try {
      const parsed = JSON.parse(node.textContent || '{}');
      payloadCache.set(key, parsed);
      return parsed;
    } catch (error) {
      console.error('[wanyu-cycle] payload parse failed', { cycle: key, message: error.message });
      return null;
    }
  };
  const readScoreLists = (bundle) => bundle?.scoreLists || {};
  const queryCycle = () => {
    const requested = new URL(location.href).searchParams.get('cycle');
    if (validCycle(requested)) return requested;
    if (requested && !warnedInvalid) {
      warnedInvalid = true;
      console.warn('[wanyu-cycle] invalid cycle, fallback to default', { requested, fallback: defaultCycle });
    }
    return validCycle(defaultCycle) ? defaultCycle : (cycles[cycles.length - 1] || '2026');
  };
  const queryView = () => (location.hash || '#overview').slice(1) || 'overview';
  const updateUrl = (cycle, mode = 'push') => {
    const url = new URL(location.href);
    if (cycle === defaultCycle) url.searchParams.delete('cycle');
    else url.searchParams.set('cycle', cycle);
    if (mode === 'replace') history.replaceState({ cycle }, '', url);
    else history.pushState({ cycle }, '', url);
  };
  const setText = (selector, value) => { const node = document.querySelector(selector); if (node) node.textContent = String(value ?? '—'); };
  const number = (value) => Number(value || 0).toLocaleString('en-US');
  const auditFor = (cycle) => ((window.productData || {}).threeYearAudit?.cycles || []).find((item) => String(item.cycle) === String(cycle)) || {};
  const statsFor = (cycle, bundle) => bundle?.cycleInfo?.stats || bundle?.allMajors?.meta || auditFor(cycle) || {};
  const renderChrome = (cycle, bundle) => {
    const info = statsFor(cycle, bundle);
    const audit = bundle?.audit || auditFor(cycle);
    document.documentElement.dataset.activeCycle = cycle;
    document.body.dataset.activeCycle = cycle;
    document.querySelectorAll('[data-cycle-tab]').forEach((tab) => {
      const selected = String(tab.dataset.cycleTab) === cycle;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
    });
    setText('[data-cycle-name]', bundle?.cycleInfo?.label || bundle?.allMajors?.meta?.cycle || `${cycle}年度`);
    const verifiedChecks = audit.checks_passed ?? audit.verified ?? audit.statuses?.verified;
    setText('[data-cycle-state]', `${verifiedChecks ?? '—'} 项内部核对通过 · ${Array.isArray(audit.gaps) ? audit.gaps.length : '—'} 项已登记边界`);
    setText('[data-cycle-posts]', number(info.total_posts ?? bundle?.allMajors?.meta?.total));
    setText('[data-cycle-recruits]', number(info.total_recruits ?? bundle?.allMajors?.meta?.recruits));
    const safeScoreJoin = audit.coverage?.score_by_key ?? audit.score_joined ?? bundle?.allMajors?.meta?.compJoined;
    setText('[data-cycle-joined]', number(safeScoreJoin));
    const sourceName = bundle?.source_file?.split?.('\\').pop?.() || bundle?.cycleRuntime?.source_file || '已封装';
    setText('[data-cycle-source]', `源页 ${sourceName} · v12.1`);
    document.querySelectorAll('[data-cycle-unavailable]').forEach((node) => {
      const requirement = node.dataset.cycleUnavailable || '';
      const unavailable = requirement && requirement.split(',').includes(cycle);
      node.dataset.cycleUnavailable = unavailable ? 'true' : 'false';
      node.title = unavailable ? '本周期未纳入该数据层，缺口已在页面说明' : '';
    });
  };
  const mountTemplate = (cycle) => {
    const target = document.querySelector('#cycle-view-container');
    const source = templateCache.get(cycle);
    if (!target || !source) return false;
    target.replaceChildren(source.content.cloneNode(true));
    target.dataset.activeCycle = cycle;
    return true;
  };
  const emit = (cycle, bundle, previous, source) => {
    document.dispatchEvent(new CustomEvent('wanyu:cyclechange', { detail: { cycle, bundle, previous, source } }));
  };
  const activate = (requested, options = {}) => {
    const cycle = validCycle(requested) ? String(requested) : queryCycle();
    const previous = active;
    if (active === cycle && !options.force) return getBundle(cycle);
    const bundle = getBundle(cycle);
    if (!bundle) return null;
    active = cycle;
    window.productData = bundle;
    window.__SCORE_LISTS__ = readScoreLists(bundle);
    mountTemplate(cycle);
    renderChrome(cycle, bundle);
    if (options.writeUrl !== false) updateUrl(cycle, options.historyMode || (previous ? 'push' : 'replace'));
    if (previous) {
      disposeApp();
      runApp();
    }
    emit(cycle, bundle, previous, options.source || 'activate');
    return bundle;
  };
  const getBundle = (cycle) => {
    const parsed = readPayload(cycle);
    if (!parsed) return null;
    return parsed;
  };
  const subscribers = new Set();
  const subscribe = (listener) => { subscribers.add(listener); const off = () => subscribers.delete(listener); return off; };
  document.addEventListener('wanyu:cyclechange', (event) => subscribers.forEach((listener) => { try { listener(event.detail); } catch (error) { console.error('[wanyu-cycle] subscriber failed', error); } }));
  const activateFromUrl = (source) => activate(queryCycle(), { writeUrl: false, force: true, source, historyMode: 'replace' });
  const onTabKey = (event) => {
    const tabs = [...document.querySelectorAll('[data-cycle-tab]')];
    const current = tabs.indexOf(event.currentTarget);
    if (current < 0) return;
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      activate(event.currentTarget.dataset.cycleTab, { source: 'keyboard' });
      return;
    }
    const next = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? (current + 1) % tabs.length
      : event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? (current - 1 + tabs.length) % tabs.length
      : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : -1;
    if (next < 0) return;
    event.preventDefault();
    tabs[next].focus();
    if (event.key !== 'Home' && event.key !== 'End' && !event.key.startsWith('Arrow')) return;
    if (event.key === 'Home' || event.key === 'End' || event.key.startsWith('Arrow')) activate(tabs[next].dataset.cycleTab, { source: 'keyboard' });
  };
  document.querySelectorAll('[data-cycle-tab]').forEach((tab) => {
    tab.addEventListener('click', () => activate(tab.dataset.cycleTab, { source: 'tab' }));
    tab.addEventListener('keydown', onTabKey);
  });
  /* v13: hash-only navigation must not remount a cycle */
  const onPopState = () => {
    if (String(queryCycle()) === String(active)) return;
    activateFromUrl('popstate');
  };
  addEventListener('popstate', onPopState);
  window.WanyuCycleStore = Object.freeze({ listCycles: () => cycles.slice(), getCycle: () => active, getBundle, activate, subscribe, toGlobalId: (recordId) => active && recordId != null ? `${active}:${String(recordId)}` : null });
  appGeneration = 1;
  tracking = true;
  activate(queryCycle(), { writeUrl: false, force: true, source: 'initial' });
})();
