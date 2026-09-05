(() => {
  const STORAGE_KEY = 'wanyu-maintainable-user-store-v1';
  const MAX_SNAPSHOTS = 40;
  const MAX_POSITIONS = 2000;
  const MAX_COMPARE = 4;
  const getStorage = (storage) => storage || (typeof globalThis !== 'undefined' ? globalThis.localStorage : null);
  const readState = (storage) => {
    const target = getStorage(storage);
    if (!target || typeof target.getItem !== 'function') return { version: 1, snapshots: [], positions: [], compare: [] };
    try {
      const parsed = JSON.parse(target.getItem(STORAGE_KEY) || '{}');
      return {
        version: 1,
        snapshots: Array.isArray(parsed.snapshots) ? parsed.snapshots : [],
        positions: Array.isArray(parsed.positions) ? parsed.positions : [],
        compare: Array.isArray(parsed.compare) ? parsed.compare.map((item) => String(item)).filter(Boolean).slice(0, MAX_COMPARE) : [],
      };
    } catch {
      return { version: 1, snapshots: [], positions: [], compare: [] };
    }
  };
  const writeState = (state, storage) => {
    const target = getStorage(storage);
    if (!target || typeof target.setItem !== 'function') return;
    target.setItem(STORAGE_KEY, JSON.stringify(state));
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
  const importAll = (payload, storage) => {
    let parsed;
    try {
      parsed = typeof payload === 'string' ? JSON.parse(payload) : payload;
    } catch {
      throw new Error('导入文件不是有效 JSON');
    }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('导入文件结构不正确');
    if (Number(parsed.version) !== 1) throw new Error(`导入文件版本不支持：${String(parsed.version)}`);
    const snapshots = Array.isArray(parsed.snapshots)
      ? parsed.snapshots.filter((item) => item && item.id && item.cycle).map((item) => ({
        id: String(item.id).slice(0, 80),
        cycle: String(item.cycle).slice(0, 20),
        filters: safeFilters(item.filters),
        metric: String(item.metric || 'jobs').slice(0, 20),
        release: String(item.release || '').slice(0, 40),
        createdAt: String(item.createdAt || '').slice(0, 40),
      })).slice(0, MAX_SNAPSHOTS)
      : [];
    const positions = Array.isArray(parsed.positions)
      ? parsed.positions.filter((item) => item && item.recordId).map((item) => ({
        recordId: String(item.recordId).slice(0, 120),
        note: String(item.note || '').slice(0, 500),
        savedAt: String(item.savedAt || '').slice(0, 40),
        updatedAt: String(item.updatedAt || '').slice(0, 40),
      })).slice(0, MAX_POSITIONS)
      : [];
    const compare = Array.isArray(parsed.compare)
      ? parsed.compare.map((item) => String(item || '').slice(0, 120)).filter(Boolean).slice(0, MAX_COMPARE)
      : [];
    writeState({ version: 1, snapshots, positions, compare }, storage);
    return { snapshots: snapshots.length, positions: positions.length, compare: compare.length };
  };
  const api = Object.freeze({ makeSnapshot, saveFilterSnapshot, loadFilterSnapshots, savePosition, removePosition, loadPositions, saveCompare, removeCompare, loadCompare, escapeCsvCell, serializeExport, exportAll, importAll });
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.WanyuUserStore = api;
})();
