(() => {
  const STORAGE_KEY = 'wanyu-maintainable-user-store-v1';
  const PROFILE_KEY = 'wanyu.profile.v1';
  const MAX_SNAPSHOTS = 40;
  const MAX_POSITIONS = 2000;
  const MAX_COMPARE = 4;
  const PROFILE_INPUT_PREFIX = 'maint-profile-';
  const PROFILE_FIELDS = Object.freeze(['gender', 'fresh', 'party', 'legal', 'age']);
  // 与正式 positions.json 的 record_id 形态一致（job-YYYY-20hex）；导入时只认这个形态
  const RECORD_ID_PATTERN = /^job-\d{4}-[0-9a-f]{20}$/;
  const emptyState = () => ({ version: 1, snapshots: [], positions: [], compare: [] });
  const emptyProfile = () => ({ gender: '', fresh: '', party: '', legal: '', age: '' });

  // ---- StorageAdapter：业务代码不再直接触达 localStorage，所有异常收敛为状态 ----
  // ok | unavailable（没有存储对象）| blocked（访问即抛 SecurityError）| quota（写满）| corrupt（已存内容不是合法 JSON）
  let lastStorageStatus = 'ok';
  const isQuotaError = (error) => {
    const name = String(error?.name || '');
    const code = Number(error?.code);
    return name === 'QuotaExceededError' || name === 'NS_ERROR_DOM_QUOTA_REACHED' || code === 22 || code === 1014;
  };
  const resolveStorage = (storage) => {
    if (storage) return { target: storage, status: 'ok' };
    try {
      // 严格隐私/嵌入环境里，读取 localStorage 属性本身就可能抛 SecurityError
      const target = typeof globalThis !== 'undefined' ? globalThis.localStorage : null;
      return target ? { target, status: 'ok' } : { target: null, status: 'unavailable' };
    } catch {
      return { target: null, status: 'blocked' };
    }
  };
  const storageGet = (key, storage) => {
    const { target, status } = resolveStorage(storage);
    if (!target || typeof target.getItem !== 'function') { lastStorageStatus = status === 'ok' ? 'unavailable' : status; return { ok: false, value: null }; }
    try {
      const value = target.getItem(key);
      lastStorageStatus = 'ok';
      return { ok: true, value: value == null ? null : String(value) };
    } catch {
      lastStorageStatus = 'blocked';
      return { ok: false, value: null };
    }
  };
  const storageSet = (key, value, storage) => {
    const { target, status } = resolveStorage(storage);
    if (!target || typeof target.setItem !== 'function') { lastStorageStatus = status === 'ok' ? 'unavailable' : status; return false; }
    try {
      target.setItem(key, value);
      lastStorageStatus = 'ok';
      return true;
    } catch (error) {
      lastStorageStatus = isQuotaError(error) ? 'quota' : 'blocked';
      return false;
    }
  };
  const storageRemove = (key, storage) => {
    const { target } = resolveStorage(storage);
    if (!target || typeof target.removeItem !== 'function') return false;
    try { target.removeItem(key); return true; } catch { return false; }
  };
  const storageStatus = () => lastStorageStatus;
  const storageAvailable = (storage) => {
    const { target } = resolveStorage(storage);
    if (!target || typeof target.setItem !== 'function' || typeof target.removeItem !== 'function') return false;
    const probe = `${STORAGE_KEY}.probe`;
    try { target.setItem(probe, '1'); target.removeItem(probe); return true; } catch { return false; }
  };

  const normalizeState = (parsed) => ({
    version: 1,
    snapshots: Array.isArray(parsed?.snapshots) ? parsed.snapshots : [],
    positions: Array.isArray(parsed?.positions) ? parsed.positions : [],
    compare: Array.isArray(parsed?.compare) ? parsed.compare.map((item) => String(item)).filter(Boolean).slice(0, MAX_COMPARE) : [],
  });
  const readStateDetailed = (storage) => {
    const { ok, value } = storageGet(STORAGE_KEY, storage);
    if (!ok) return { state: emptyState(), status: lastStorageStatus };
    if (!value) return { state: emptyState(), status: 'ok' };
    try {
      const parsed = JSON.parse(value);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('shape');
      return { state: normalizeState(parsed), status: 'ok' };
    } catch {
      lastStorageStatus = 'corrupt';
      return { state: emptyState(), status: 'corrupt' };
    }
  };
  const readState = (storage) => readStateDetailed(storage).state;
  const writeState = (state, storage) => storageSet(STORAGE_KEY, JSON.stringify(state), storage);

  // ---- 我的条件（profile）：仅五个字段、全部字符串；存储 key 与旧版页面共用 ----
  const normalizeProfile = (raw) => {
    const source = raw && typeof raw === 'object' ? raw : {};
    return Object.fromEntries(PROFILE_FIELDS.map((key) => [key, source[key] == null ? '' : String(source[key]).slice(0, 40)]));
  };
  const readProfile = (storage) => {
    const { ok, value } = storageGet(PROFILE_KEY, storage);
    if (!ok || !value) return emptyProfile();
    try {
      const parsed = JSON.parse(value);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('shape');
      return normalizeProfile(parsed);
    } catch {
      lastStorageStatus = 'corrupt';
      return emptyProfile();
    }
  };
  const writeProfile = (profile, storage) => storageSet(PROFILE_KEY, JSON.stringify(normalizeProfile(profile)), storage);
  const profileActive = (profile) => Boolean(profile && PROFILE_FIELDS.some((key) => profile[key]));
  const profileFieldFromInputId = (id) => {
    if (typeof id !== 'string' || !id.startsWith(PROFILE_INPUT_PREFIX)) return null;
    const key = id.slice(PROFILE_INPUT_PREFIX.length);
    return PROFILE_FIELDS.includes(key) ? key : null;
  };

  const safeFilters = (filters) => Object.fromEntries(Object.entries(filters || {})
    .filter(([key, value]) => ['major', 'city', 'cityGroup', 'exam', 'category', 'keyword', 'metric'].includes(key) && typeof value === 'string')
    .map(([key, value]) => [key, value.slice(0, 200)]));
  const makeSnapshot = (cycle, filters, metric, release = '') => ({
    id: `snapshot-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    cycle: String(cycle || ''),
    filters: safeFilters(filters),
    metric: String(metric || 'jobs'),
    release: String(release || ''),
    createdAt: new Date().toISOString(),
  });
  const saveFilterSnapshot = (snapshot, storage) => {
    if (!snapshot || !snapshot.id || !snapshot.cycle) throw new Error('筛选快照缺少周期或 ID');
    const state = readState(storage);
    state.snapshots = [snapshot, ...state.snapshots.filter((item) => item.id !== snapshot.id)].slice(0, MAX_SNAPSHOTS);
    writeState(state, storage);
    return snapshot;
  };
  const loadFilterSnapshots = (storage) => readState(storage).snapshots;
  const savePosition = (recordId, note = '', storage) => {
    const id = String(recordId || '').trim();
    if (!id) throw new Error('收藏岗位缺少稳定 ID');
    const state = readState(storage);
    const previous = state.positions.find((item) => item.recordId === id);
    const item = { recordId: id, note: String(note || '').slice(0, 500), savedAt: previous?.savedAt || new Date().toISOString(), updatedAt: new Date().toISOString() };
    state.positions = [item, ...state.positions.filter((entry) => entry.recordId !== id)].slice(0, MAX_POSITIONS);
    writeState(state, storage);
    return item;
  };
  const removePosition = (recordId, storage) => {
    const id = String(recordId || '').trim();
    const state = readState(storage);
    state.positions = state.positions.filter((item) => item.recordId !== id);
    writeState(state, storage);
  };
  const loadPositions = (storage) => readState(storage).positions;
  const saveCompare = (recordId, storage) => {
    const id = String(recordId || '').trim();
    if (!id) throw new Error('对比岗位缺少稳定 ID');
    const state = readState(storage);
    state.compare = [id, ...state.compare.filter((entry) => entry !== id)].slice(0, MAX_COMPARE);
    writeState(state, storage);
    return state.compare;
  };
  const removeCompare = (recordId, storage) => {
    const id = String(recordId || '').trim();
    const state = readState(storage);
    state.compare = state.compare.filter((entry) => entry !== id);
    writeState(state, storage);
    return state.compare;
  };
  const loadCompare = (storage) => readState(storage).compare;
  const escapeCsvCell = (value) => {
    let text = String(value ?? '');
    if (/^[=+\-@]/.test(text)) text = `'${text}`;
    return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const serializeExport = (rows, format = 'json') => {
    const list = Array.isArray(rows) ? rows : [];
    if (format === 'json') return JSON.stringify(list, null, 2);
    const headers = [];
    list.forEach((row) => Object.keys(row || {}).forEach((key) => { if (!headers.includes(key)) headers.push(key); }));
    const lines = [headers.map(escapeCsvCell).join(',')];
    list.forEach((row) => lines.push(headers.map((key) => escapeCsvCell(row?.[key])).join(',')));
    return `\ufeff${lines.join('\r\n')}`;
  };
  const exportAll = (storage) => {
    const state = readState(storage);
    return JSON.stringify({ ...state, exportedAt: new Date().toISOString(), app: 'wanyu-maintainable' }, null, 2);
  };

  // ---- 导入规范化：去重（latest wins）+ ID 形态校验 + 统计；纯函数，不触达存储 ----
  const laterOf = (a, b) => (String(b || '') > String(a || '') ? b : a);
  const dedupeLatest = (items, keyOf, stampOf) => {
    const byKey = new Map();
    let duplicates = 0;
    items.forEach((item) => {
      const key = keyOf(item);
      const existing = byKey.get(key);
      if (!existing) { byKey.set(key, item); return; }
      duplicates += 1;
      if (laterOf(stampOf(existing), stampOf(item)) === stampOf(item) && stampOf(item) !== stampOf(existing)) byKey.set(key, item);
    });
    return { items: [...byKey.values()], duplicates };
  };
  const normalizeWorkspace = (parsed) => {
    let deduplicated = 0;
    let ignoredInvalid = 0;
    const rawSnapshots = Array.isArray(parsed.snapshots)
      ? parsed.snapshots.filter((item) => item && item.id && item.cycle).map((item) => ({
        id: String(item.id).slice(0, 80),
        cycle: String(item.cycle).slice(0, 20),
        filters: safeFilters(item.filters),
        metric: String(item.metric || 'jobs').slice(0, 20),
        release: String(item.release || '').slice(0, 40),
        createdAt: String(item.createdAt || '').slice(0, 40),
      }))
      : [];
    const snapshotResult = dedupeLatest(rawSnapshots, (item) => item.id, (item) => item.createdAt);
    deduplicated += snapshotResult.duplicates;
    const snapshots = snapshotResult.items.slice(0, MAX_SNAPSHOTS);

    const rawPositions = [];
    (Array.isArray(parsed.positions) ? parsed.positions : []).forEach((item) => {
      if (!item || !item.recordId) return;
      const recordId = String(item.recordId).slice(0, 120);
      if (!RECORD_ID_PATTERN.test(recordId)) { ignoredInvalid += 1; return; }
      rawPositions.push({
        recordId,
        note: String(item.note || '').slice(0, 500),
        savedAt: String(item.savedAt || '').slice(0, 40),
        updatedAt: String(item.updatedAt || '').slice(0, 40),
      });
    });
    const positionResult = dedupeLatest(rawPositions, (item) => item.recordId, (item) => item.updatedAt);
    deduplicated += positionResult.duplicates;
    const positions = positionResult.items.slice(0, MAX_POSITIONS);

    const compare = [];
    (Array.isArray(parsed.compare) ? parsed.compare : []).forEach((item) => {
      const recordId = String(item || '').slice(0, 120);
      if (!recordId) return;
      if (!RECORD_ID_PATTERN.test(recordId)) { ignoredInvalid += 1; return; }
      if (compare.includes(recordId)) { deduplicated += 1; return; }
      compare.push(recordId);
    });

    return {
      state: { version: 1, snapshots, positions, compare: compare.slice(0, MAX_COMPARE) },
      stats: { deduplicated, ignored_invalid: ignoredInvalid },
    };
  };
  // 原子导入：parse → validate → normalize → serialize → 一次 setItem；任何一步失败旧 workspace 不变
  const importAll = (payload, storage) => {
    let parsed;
    try {
      parsed = typeof payload === 'string' ? JSON.parse(payload) : payload;
    } catch {
      throw new Error('导入文件不是有效 JSON');
    }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('导入文件结构不正确');
    if (Number(parsed.version) !== 1) throw new Error(`导入文件版本不支持：${String(parsed.version)}`);
    const { state, stats } = normalizeWorkspace(parsed);
    if (!writeState(state, storage)) throw new Error('本地存储不可用（被浏览器阻止或已满），导入未生效，原有工作台保持不变');
    return { snapshots: state.snapshots.length, positions: state.positions.length, compare: state.compare.length, ...stats };
  };

  const api = Object.freeze({
    makeSnapshot, saveFilterSnapshot, loadFilterSnapshots, savePosition, removePosition, loadPositions, saveCompare, removeCompare, loadCompare,
    escapeCsvCell, serializeExport, exportAll, importAll, normalizeWorkspace,
    readState, readStateDetailed, storageStatus, storageAvailable, storageRemove,
    readProfile, writeProfile, profileActive, profileFieldFromInputId, PROFILE_FIELDS, PROFILE_INPUT_PREFIX, RECORD_ID_PATTERN,
  });
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.WanyuUserStore = api;
})();
