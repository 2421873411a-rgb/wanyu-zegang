const assert = require('node:assert/strict');
const { test } = require('node:test');

const store = require('../tools/anhui_web/templates/maintainable-user-store.js');

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
  const storage = new Map();
  storage.getItem = storage.get.bind(storage);
  storage.setItem = storage.set.bind(storage);
  storage.removeItem = storage.delete.bind(storage);
  store.savePosition('job-2026-abc', '重点关注', storage);
  assert.equal(store.loadPositions(storage)[0].recordId, 'job-2026-abc');
  store.removePosition('job-2026-abc', storage);
  assert.deepEqual(store.loadPositions(storage), []);
});

test('workspace export round-trips through validated import', () => {
  const storage = new Map();
  storage.getItem = storage.get.bind(storage);
  storage.setItem = storage.set.bind(storage);
  storage.removeItem = storage.delete.bind(storage);
  store.saveFilterSnapshot(store.makeSnapshot('2026', { major: '法学' }, 'jobs'), storage);
  store.savePosition('job-2026-xyz', '', storage);
  store.saveCompare('job-2026-xyz', storage);
  const exported = store.exportAll(storage);
  const fresh = new Map();
  fresh.getItem = fresh.get.bind(fresh);
  fresh.setItem = fresh.set.bind(fresh);
  fresh.removeItem = fresh.delete.bind(fresh);
  const counts = store.importAll(exported, fresh);
  assert.equal(counts.snapshots, 1);
  assert.equal(counts.positions, 1);
  assert.equal(counts.compare, 1);
  assert.equal(store.loadPositions(fresh)[0].recordId, 'job-2026-xyz');
  const json = JSON.parse(exported);
  assert.equal(json.version, 1);
  assert.equal(json.app, 'wanyu-maintainable');
});

test('workspace import rejects wrong versions and malformed payloads', () => {
  const storage = new Map();
  storage.getItem = storage.get.bind(storage);
  storage.setItem = storage.set.bind(storage);
  storage.removeItem = storage.delete.bind(storage);
  assert.throws(() => store.importAll('not json', storage));
  assert.throws(() => store.importAll('{"version":9,"snapshots":[],"positions":[],"compare":[]}', storage), /版本/);
  assert.throws(() => store.importAll('[]', storage));
  const counts = store.importAll('{"version":1,"snapshots":[{"id":"s1","cycle":"2026"},{"bad":1}],"positions":[{}],"compare":[""]}', storage);
  assert.equal(counts.snapshots, 1);
  assert.equal(counts.positions, 0);
  assert.equal(counts.compare, 0);
});
