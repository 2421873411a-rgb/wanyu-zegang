const assert = require('node:assert/strict');
const { test } = require('node:test');

const store = require('../tools/anhui_web/templates/maintainable-user-store.js');

// 与正式 positions.json 一致的稳定 ID 形态：job-YYYY-20hex（三周期 28,568 条 100% 命中）
const ID_A = 'job-2026-a3b96e08cf15085d5ed9';
const ID_B = 'job-2026-03d29215064ec108aee8';
const ID_C = 'job-2025-43686c0243d1230125fd';
const ID_D = 'job-2024-74cc645b63fcb23d3671';
const ID_E = 'job-2024-bc041b0252427f35b5e5';

const memStorage = () => {
  const map = new Map();
  return {
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => { map.set(key, String(value)); },
    removeItem: (key) => { map.delete(key); },
    dump: () => Object.fromEntries(map),
  };
};

test('snapshot persists query, not full rows', () => {
  const snapshot = store.makeSnapshot('2026', { major: '软件工程', city: '合肥' }, 'recruits');
  assert.equal(Object.hasOwn(snapshot, 'rows'), false);
  assert.equal(snapshot.cycle, '2026');
  assert.equal(snapshot.metric, 'recruits');
});

test('CSV export has BOM and formula protection', () => {
  const csvText = store.serializeExport([{ unit: '=HYPERLINK("x")', note: 'a,b' }], 'csv');
  assert.equal(csvText.startsWith('\ufeff'), true);
  assert.equal(csvText.includes("'=HYPERLINK"), true);
  assert.equal(csvText.includes('"a,b"'), true);
});

test('local store saves and removes stable position IDs', () => {
  const storage = memStorage();
  store.savePosition(ID_A, '重点关注', storage);
  assert.equal(store.loadPositions(storage)[0].recordId, ID_A);
  store.removePosition(ID_A, storage);
  assert.deepEqual(store.loadPositions(storage), []);
});

test('workspace export round-trips through validated import', () => {
  const storage = memStorage();
  store.saveFilterSnapshot(store.makeSnapshot('2026', { major: '法学' }, 'jobs'), storage);
  store.savePosition(ID_B, '', storage);
  store.saveCompare(ID_B, storage);
  const exported = store.exportAll(storage);
  const fresh = memStorage();
  const counts = store.importAll(exported, fresh);
  assert.equal(counts.snapshots, 1);
  assert.equal(counts.positions, 1);
  assert.equal(counts.compare, 1);
  assert.equal(counts.deduplicated, 0);
  assert.equal(counts.ignored_invalid, 0);
  assert.equal(store.loadPositions(fresh)[0].recordId, ID_B);
  const json = JSON.parse(exported);
  assert.equal(json.version, 1);
  assert.equal(json.app, 'wanyu-maintainable');
});

test('workspace import rejects wrong versions and malformed payloads', () => {
  const storage = memStorage();
  assert.throws(() => store.importAll('not json', storage));
  assert.throws(() => store.importAll('{"version":9,"snapshots":[],"positions":[],"compare":[]}', storage), /版本/);
  assert.throws(() => store.importAll('[]', storage));
  const counts = store.importAll('{"version":1,"snapshots":[{"id":"s1","cycle":"2026"},{"bad":1}],"positions":[{}],"compare":[""]}', storage);
  assert.equal(counts.snapshots, 1);
  assert.equal(counts.positions, 0);
  assert.equal(counts.compare, 0);
});

// ---------------------------------------------------------------------------
// A2 · profile 输入 ID → 字段映射必须是纯函数，不依赖任何 DOM 事件对象
// ---------------------------------------------------------------------------
test('profileFieldFromInputId maps only the five known profile inputs', () => {
  assert.equal(store.profileFieldFromInputId('maint-profile-age'), 'age');
  assert.equal(store.profileFieldFromInputId('maint-profile-gender'), 'gender');
  assert.equal(store.profileFieldFromInputId('maint-profile-fresh'), 'fresh');
  assert.equal(store.profileFieldFromInputId('maint-profile-party'), 'party');
  assert.equal(store.profileFieldFromInputId('maint-profile-legal'), 'legal');
  assert.equal(store.profileFieldFromInputId('foo'), null);
  assert.equal(store.profileFieldFromInputId(''), null);
  assert.equal(store.profileFieldFromInputId(null), null);
  assert.equal(store.profileFieldFromInputId(undefined), null);
  assert.equal(store.profileFieldFromInputId('maint-profile-'), null);
  assert.equal(store.profileFieldFromInputId('maint-profile-unknown'), null);
  assert.equal(store.profileFieldFromInputId('maint-search-major'), null);
  assert.deepEqual([...store.PROFILE_FIELDS], ['gender', 'fresh', 'party', 'legal', 'age']);
});

test('profile store round-trips five string fields and survives corrupt JSON', () => {
  const storage = memStorage();
  assert.deepEqual(store.readProfile(storage), { gender: '', fresh: '', party: '', legal: '', age: '' });
  store.writeProfile({ gender: 'male', age: 27, party: 'yes', extra: 'dropped' }, storage);
  assert.deepEqual(store.readProfile(storage), { gender: 'male', fresh: '', party: 'yes', legal: '', age: '27' });
  assert.equal(store.profileActive(store.readProfile(storage)), true);
  assert.equal(store.profileActive({ gender: '', fresh: '', party: '', legal: '', age: '' }), false);
  storage.setItem('wanyu.profile.v1', '{not json');
  assert.deepEqual(store.readProfile(storage), { gender: '', fresh: '', party: '', legal: '', age: '' });
  assert.equal(store.storageStatus(), 'corrupt');
});

// ---------------------------------------------------------------------------
// B1/B2 · StorageAdapter：blocked / quota / corrupt / unavailable 全部降级而非抛出
// ---------------------------------------------------------------------------
const securityError = () => { const error = new Error('The operation is insecure.'); error.name = 'SecurityError'; return error; };
const quotaError = () => { const error = new Error('QuotaExceededError'); error.name = 'QuotaExceededError'; return error; };

test('blocked storage (SecurityError on access) degrades to empty state with status=blocked', () => {
  const blocked = {
    getItem: () => { throw securityError(); },
    setItem: () => { throw securityError(); },
    removeItem: () => { throw securityError(); },
  };
  const detailed = store.readStateDetailed(blocked);
  assert.deepEqual(detailed.state, { version: 1, snapshots: [], positions: [], compare: [] });
  assert.equal(detailed.status, 'blocked');
  assert.doesNotThrow(() => store.savePosition(ID_A, '', blocked));
  assert.equal(store.storageStatus(), 'blocked');
  assert.equal(store.storageAvailable(blocked), false);
});

test('quota exhaustion on setItem is reported, never thrown from save helpers', () => {
  const storage = memStorage();
  store.savePosition(ID_A, '', storage);
  const exhausted = { ...storage, setItem: () => { throw quotaError(); } };
  assert.doesNotThrow(() => store.savePosition(ID_B, '', exhausted));
  assert.equal(store.storageStatus(), 'quota');
  // 旧数据仍可读：写失败不破坏已存内容
  assert.equal(store.loadPositions(exhausted)[0].recordId, ID_A);
  assert.equal(store.storageStatus(), 'ok');
});

test('corrupt stored JSON reads as empty state with status=corrupt and keeps the raw bytes', () => {
  const storage = memStorage();
  storage.setItem('wanyu-maintainable-user-store-v1', '{"snapshots":[');
  const detailed = store.readStateDetailed(storage);
  assert.deepEqual(detailed.state, { version: 1, snapshots: [], positions: [], compare: [] });
  assert.equal(detailed.status, 'corrupt');
  // 审计 F-012：损坏原文必须留档，后续保存不得静默销毁现场
  assert.equal(storage.getItem('wanyu-maintainable-user-store-v1.corrupt-backup'), '{"snapshots":[');
});

test('storageAvailable probes write+remove and reports true for a working store', () => {
  const storage = memStorage();
  assert.equal(store.storageAvailable(storage), true);
  assert.equal(store.storageAvailable(null), false);
});

// ---------------------------------------------------------------------------
// B3 · import 规范化：去重 + ID 形态校验 + 统计
// ---------------------------------------------------------------------------
test('workspace import deduplicates positions by recordId keeping the latest updatedAt', () => {
  const storage = memStorage();
  const counts = store.importAll(JSON.stringify({
    version: 1,
    snapshots: [],
    positions: [
      { recordId: ID_A, note: 'old', updatedAt: '2026-01-01T00:00:00.000Z' },
      { recordId: ID_A, note: 'new', updatedAt: '2026-02-01T00:00:00.000Z' },
      { recordId: ID_B, note: 'b', updatedAt: '2026-01-15T00:00:00.000Z' },
    ],
    compare: [],
  }), storage);
  assert.equal(counts.positions, 2);
  assert.equal(counts.deduplicated, 1);
  const positions = store.loadPositions(storage);
  assert.equal(positions.find((item) => item.recordId === ID_A).note, 'new');
});

test('workspace import deduplicates snapshots by id keeping the latest createdAt', () => {
  const storage = memStorage();
  const counts = store.importAll(JSON.stringify({
    version: 1,
    snapshots: [
      { id: 's1', cycle: '2026', createdAt: '2026-01-01T00:00:00.000Z', metric: 'jobs' },
      { id: 's1', cycle: '2026', createdAt: '2026-03-01T00:00:00.000Z', metric: 'recruits' },
    ],
    positions: [],
    compare: [],
  }), storage);
  assert.equal(counts.snapshots, 1);
  assert.equal(counts.deduplicated, 1);
  assert.equal(store.loadFilterSnapshots(storage)[0].metric, 'recruits');
});

test('workspace import keeps compare stable-unique and capped at four', () => {
  const storage = memStorage();
  const counts = store.importAll(JSON.stringify({
    version: 1,
    snapshots: [],
    positions: [],
    compare: [ID_A, ID_B, ID_A, ID_C, ID_D, ID_E],
  }), storage);
  assert.equal(counts.compare, 4);
  assert.equal(counts.deduplicated, 1);
  assert.deepEqual(store.loadCompare(storage), [ID_A, ID_B, ID_C, ID_D]);
});

test('workspace import ignores malformed record IDs and counts them', () => {
  const storage = memStorage();
  const counts = store.importAll(JSON.stringify({
    version: 1,
    snapshots: [],
    positions: [{ recordId: 'job-2026-abc' }, { recordId: '<script>' }, { recordId: ID_A }],
    compare: ['nope', ID_A],
  }), storage);
  assert.equal(counts.positions, 1);
  assert.equal(counts.compare, 1);
  assert.equal(counts.ignored_invalid, 3);
  assert.equal(store.loadPositions(storage)[0].recordId, ID_A);
});

// ---------------------------------------------------------------------------
// B4 · 原子导入：任何一步失败，旧 workspace 完全不变
// ---------------------------------------------------------------------------
test('failed import leaves the existing workspace byte-identical', () => {
  const storage = memStorage();
  store.savePosition(ID_A, 'keep', storage);
  store.saveCompare(ID_A, storage);
  const before = JSON.stringify(storage.dump());
  assert.throws(() => store.importAll('{"version":2}', storage), /版本/);
  assert.throws(() => store.importAll('{bad', storage));
  assert.throws(() => store.importAll('[]', storage));
  assert.equal(JSON.stringify(storage.dump()), before);
});

test('import into a store that rejects writes throws and leaves prior state intact', () => {
  const storage = memStorage();
  store.savePosition(ID_A, 'keep', storage);
  const before = JSON.stringify(storage.dump());
  const exhausted = { ...storage, setItem: () => { throw quotaError(); } };
  assert.throws(() => store.importAll(JSON.stringify({ version: 1, snapshots: [], positions: [{ recordId: ID_B }], compare: [] }), exhausted), /本地存储/);
  assert.equal(JSON.stringify(storage.dump()), before);
});
