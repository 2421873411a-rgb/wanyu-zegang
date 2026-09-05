(() => {
  /* v12 local state: keep legacy v1 readable while namespacing records by cycle. */
  const cycle = String(window.productData?.cycleRuntime?.cycle || '2026');
  const V1 = { saved: 'wanyu.jobSaved.v1', compare: 'wanyu.jobCompare.v1', notes: 'wanyu.jobNotes.v1' };
  const V2 = { saved: 'wanyu.jobSaved.v2', compare: 'wanyu.jobCompare.v2', notes: 'wanyu.jobNotes.v2' };
  const MIGRATION = 'wanyu.jobMigration.v12';
  const asGlobal = (value, targetCycle = cycle) => {
    const text = String(value ?? '').trim();
    if (!text) return '';
    return text.includes(':') ? text : `${targetCycle}:${text}`;
  };
  const read = (key, fallback) => {
    try { return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback)); } catch { return null; }
  };
  const recordMigrationError = (key, reason) => {
    try {
      const current = read('wanyu.migrationErrors.v12', []) || [];
      current.push({ key, reason, at: new Date().toISOString() });
      localStorage.setItem('wanyu.migrationErrors.v12', JSON.stringify(current));
    } catch {}
  };
  const unique = (items) => [...new Set((items || []).map((item) => String(item)).filter(Boolean))];
  const migrateV1ToV2 = () => {
    const marker = read(MIGRATION, null);
    if (marker?.completed) return marker;
    const saved = read(V1.saved, []);
    const compare = read(V1.compare, []);
    const notes = read(V1.notes, {});
    if (!Array.isArray(saved)) recordMigrationError(V1.saved, 'expected array');
    if (!Array.isArray(compare)) recordMigrationError(V1.compare, 'expected array');
    if (!notes || typeof notes !== 'object' || Array.isArray(notes)) recordMigrationError(V1.notes, 'expected object');
    const savedV2 = unique(Array.isArray(saved) ? saved : []).map((item) => asGlobal(item, '2026'));
    const compareV2 = unique(Array.isArray(compare) ? compare : []).map((item) => asGlobal(item, '2026'));
    const notesV2 = {};
    if (notes && typeof notes === 'object' && !Array.isArray(notes)) Object.entries(notes).forEach(([key, value]) => { notesV2[asGlobal(key, '2026')] = value; });
    try {
      localStorage.setItem(V2.saved, JSON.stringify(savedV2));
      localStorage.setItem(V2.compare, JSON.stringify(compareV2));
      localStorage.setItem(V2.notes, JSON.stringify(notesV2));
      const next = { completed: true, source: 'v1', defaultCycle: '2026', at: new Date().toISOString() };
      localStorage.setItem(MIGRATION, JSON.stringify(next));
      return next;
    } catch (error) {
      recordMigrationError('migration', error?.name || 'write failed');
      return null;
    }
  };
  const loadSet = (key) => {
    const value = read(key, []);
    return new Set(Array.isArray(value) ? value.map((item) => asGlobal(item)) : []);
  };
  const saveSet = (key, ids) => {
    try { localStorage.setItem(key, JSON.stringify(unique(ids).map((id) => asGlobal(id)))); return true; } catch { return false; }
  };
  const loadNotes = () => {
    const value = read(V2.notes, {});
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  };
  const saveNotes = (notes) => {
    try { localStorage.setItem(V2.notes, JSON.stringify(notes && typeof notes === 'object' ? notes : {})); return true; } catch { return false; }
  };
  const localForActive = (globalId) => {
    const prefix = `${cycle}:`;
    const value = String(globalId || '');
    return value.startsWith(prefix) ? value.slice(prefix.length) : null;
  };
  const api = {
    cycle,
    migrateV1ToV2,
    toGlobalId: asGlobal,
    loadSaved: () => [...loadSet(V2.saved)],
    saveSaved: (ids) => saveSet(V2.saved, ids),
    loadCompare: () => [...loadSet(V2.compare)],
    saveCompare: (ids) => saveSet(V2.compare, ids),
    loadNotes,
    saveNotes,
    activeSaved: () => loadSet(V2.saved),
    activeCompare: () => loadSet(V2.compare),
    activeLocalSaved: () => [...loadSet(V2.saved)].map(localForActive).filter(Boolean),
    activeLocalCompare: () => [...loadSet(V2.compare)].map(localForActive).filter(Boolean),
    saveActiveSaved: (ids) => saveSet(V2.saved, [...loadSet(V2.saved)].filter((id) => !localForActive(id)).concat([...ids].map((id) => asGlobal(id, cycle)))),
    saveActiveCompare: (ids) => saveSet(V2.compare, [...loadSet(V2.compare)].filter((id) => !localForActive(id)).concat([...ids].map((id) => asGlobal(id, cycle)))),
  };
  migrateV1ToV2();
  window.WanyuUserStore = Object.freeze(api);
})();
