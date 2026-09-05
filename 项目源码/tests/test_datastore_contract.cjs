const assert = require('assert');
const { DataStore, modulePath, validatePayload } = require('../tools/anhui_web/templates/maintainable-data.js');

const manifest = {
  cycles: [{ cycle: '2026', modules: { overview: { data: 'data/cycles/2026/overview.json' }, jobs: { data: 'data/cycles/2026/jobs.json' } } }],
  audit: { data: 'data/audit/three-year.json' },
  review_queue: { data: 'data/audit/review-queue.json' },
};

async function run() {
  assert.equal(modulePath(manifest, '2026', 'jobs'), 'data/cycles/2026/jobs.json');
  assert.equal(modulePath(manifest, '2026', 'missing'), null);
  assert.equal(modulePath(manifest, 'audit', 'three-year'), 'data/audit/three-year.json');
  assert.throws(() => validatePayload({}, '2026', 'jobs'), /allMajors/);

  const calls = [];
  const payloads = {
    'data/cycles/2026/jobs.json': { allMajors: { meta: { total: 1 }, rows: [{ code: 'x' }] } },
  };
  const store = new DataStore(manifest, async (url) => {
    calls.push(url);
    return { ok: true, status: 200, async json() { return payloads[url]; } };
  });
  const first = await store.load('2026', 'jobs');
  const second = await store.load('2026', 'jobs');
  assert.strictEqual(first, second);
  assert.deepEqual(calls, ['data/cycles/2026/jobs.json']);

  let attempts = 0;
  const retryStore = new DataStore(manifest, async () => {
    attempts += 1;
    if (attempts === 1) throw new Error('temporary');
    return { ok: true, status: 200, async json() { return payloads['data/cycles/2026/jobs.json']; } };
  });
  await retryStore.load('2026', 'jobs');
  assert.equal(attempts, 2);
  console.log('datastore contract: PASS');
}

run().catch((error) => { console.error(error.stack || error); process.exit(1); });
