/* DataStore 数据完整性契约：node tests/test_datastore_contract.cjs
 *
 * 两个语义彻底分开：
 *   - ?sha=<prefix>  → 缓存定位（Service Worker 内容寻址键）
 *   - SHA-256 digest → 内容完整性（manifest 给出 SHA 就必须逐字节验证）
 */
const assert = require('assert');
const { createHash } = require('node:crypto');
const { DataStore, modulePath, validatePayload, IntegrityError } = require('../tools/anhui_web/templates/maintainable-data.js');

const sha256 = (text) => createHash('sha256').update(Buffer.from(text, 'utf8')).digest('hex');
const bytesOf = (text) => Buffer.byteLength(text, 'utf8');

const JOBS_RAW = JSON.stringify({ allMajors: { meta: { total: 1 }, rows: [{ code: 'x' }] } });
const entryFor = (raw, overrides = {}) => ({ data: 'data/cycles/2026/jobs.json', bytes: bytesOf(raw), sha256: sha256(raw), ...overrides });

const manifestWith = (jobsEntry, extra = {}) => ({
  cycles: [{ cycle: '2026', modules: { overview: { data: 'data/cycles/2026/overview.json' }, jobs: jobsEntry } }],
  audit: { data: 'data/audit/three-year.json' },
  review_queue: { data: 'data/audit/review-queue.json' },
  ...extra,
});

const textFetcher = (raw, log = []) => async (url, init) => {
  log.push({ url, cache: init?.cache });
  return { ok: true, status: 200, async text() { return raw; }, async json() { return JSON.parse(raw); } };
};

async function rejects(promise, pattern, label) {
  let caught = null;
  try { await promise; } catch (error) { caught = error; }
  assert.ok(caught, `${label}: expected rejection`);
  assert.match(String(caught.message), pattern, `${label}: ${caught.message}`);
  return caught;
}

async function run() {
  // --- 路径与 schema（原有契约保留） ---
  const plain = manifestWith({ data: 'data/cycles/2026/jobs.json' });
  assert.equal(modulePath(plain, '2026', 'jobs'), 'data/cycles/2026/jobs.json');
  assert.equal(modulePath(plain, '2026', 'missing'), null);
  assert.equal(modulePath(plain, 'audit', 'three-year'), 'data/audit/three-year.json');
  assert.throws(() => validatePayload({}, '2026', 'jobs'), /allMajors/);

  // --- 1. 正确 JSON + 正确 bytes + 正确 SHA → PASS，状态 verified，URL 带 sha 前缀且 cache-first ---
  {
    const log = [];
    const store = new DataStore(manifestWith(entryFor(JOBS_RAW)), textFetcher(JOBS_RAW, log));
    const payload = await store.load('2026', 'jobs');
    assert.equal(payload.allMajors.meta.total, 1);
    assert.equal(store.integrityStatus('2026', 'jobs'), 'verified');
    assert.equal(log[0].url, `data/cycles/2026/jobs.json?sha=${sha256(JOBS_RAW).slice(0, 16)}`);
    assert.equal(log[0].cache, 'default');
  }

  // --- 2. 相同 bytes、错误内容（翻转一个字符）→ FAIL：这正是仅靠 bytes 长度抓不到的情况 ---
  {
    const tampered = JOBS_RAW.replace('"code":"x"', '"code":"y"');
    assert.equal(bytesOf(tampered), bytesOf(JOBS_RAW));
    const store = new DataStore(manifestWith(entryFor(JOBS_RAW)), textFetcher(tampered));
    const error = await rejects(store.load('2026', 'jobs'), /SHA-256/, 'same-size tamper');
    assert.equal(error.name, 'IntegrityError');
    assert.equal(error.code, 'sha256-mismatch');
    assert.equal(store.integrityStatus('2026', 'jobs'), null);
  }

  // --- 3. 正确 JSON + 错误 bytes 声明 → FAIL ---
  {
    const store = new DataStore(manifestWith(entryFor(JOBS_RAW, { bytes: bytesOf(JOBS_RAW) + 1 })), textFetcher(JOBS_RAW));
    await rejects(store.load('2026', 'jobs'), /字节数/, 'bytes mismatch');
  }

  // --- 4. manifest SHA 被改 → FAIL ---
  {
    const store = new DataStore(manifestWith(entryFor(JOBS_RAW, { sha256: '0'.repeat(64) })), textFetcher(JOBS_RAW));
    await rejects(store.load('2026', 'jobs'), /SHA-256/, 'manifest sha tampered');
  }

  // --- 5. SHA 正确但 schema 错 → FAIL（完整性通过 ≠ 结构合法） ---
  {
    const badSchema = JSON.stringify({ nope: true });
    const store = new DataStore(manifestWith(entryFor(badSchema)), textFetcher(badSchema));
    await rejects(store.load('2026', 'jobs'), /allMajors/, 'schema after integrity');
  }

  // --- 6. JSON 被截断（bytes 变化）→ FAIL，且错误来自完整性层而不是 JSON.parse ---
  {
    const truncated = JOBS_RAW.slice(0, -5);
    const store = new DataStore(manifestWith(entryFor(JOBS_RAW)), textFetcher(truncated));
    const error = await rejects(store.load('2026', 'jobs'), /字节数/, 'truncated');
    assert.equal(error.name, 'IntegrityError');
  }

  // --- 7. 网络第一次失败、第二次正常 → PASS（重试保留） ---
  {
    let attempts = 0;
    const store = new DataStore(manifestWith(entryFor(JOBS_RAW)), async () => {
      attempts += 1;
      if (attempts === 1) throw new Error('temporary');
      return { ok: true, status: 200, async text() { return JOBS_RAW; } };
    });
    await store.load('2026', 'jobs');
    assert.equal(attempts, 2);
  }

  // --- 8. 两个并发 load 同一模块 → 只发一次请求；已 cache → 返回同对象 ---
  {
    const log = [];
    const store = new DataStore(manifestWith(entryFor(JOBS_RAW)), textFetcher(JOBS_RAW, log));
    const [first, second] = await Promise.all([store.load('2026', 'jobs'), store.load('2026', 'jobs')]);
    assert.strictEqual(first, second);
    const third = await store.load('2026', 'jobs');
    assert.strictEqual(first, third);
    assert.equal(log.length, 1);
  }

  // --- 9. load 失败后再次 load 可以重新请求（inflight 已清理） ---
  {
    let serveBad = true;
    const store = new DataStore(manifestWith(entryFor(JOBS_RAW)), async () => ({
      ok: true, status: 200, async text() { return serveBad ? JOBS_RAW.replace('"code":"x"', '"code":"y"') : JOBS_RAW; },
    }));
    await rejects(store.load('2026', 'jobs'), /SHA-256/, 'first bad');
    serveBad = false;
    const payload = await store.load('2026', 'jobs');
    assert.equal(payload.allMajors.rows[0].code, 'x');
    assert.equal(store.integrityStatus('2026', 'jobs'), 'verified');
  }

  // --- 10. manifest 无 SHA → 兼容工作：不带 ?sha、no-cache、状态 unhashed ---
  {
    const log = [];
    const store = new DataStore(plain, textFetcher(JOBS_RAW, log));
    await store.load('2026', 'jobs');
    assert.equal(log[0].url, 'data/cycles/2026/jobs.json');
    assert.equal(log[0].cache, 'no-cache');
    assert.equal(store.integrityStatus('2026', 'jobs'), 'unhashed');
  }

  // --- 11. 无 SubtleCrypto：strict（默认）fail closed；manifest.integrity_policy=compatible → 明确 degraded ---
  {
    const strict = new DataStore(manifestWith(entryFor(JOBS_RAW)), textFetcher(JOBS_RAW), { subtle: null });
    const error = await rejects(strict.load('2026', 'jobs'), /Web Crypto/, 'no subtle strict');
    assert.equal(error.code, 'integrity-unavailable');

    const compatible = new DataStore(manifestWith(entryFor(JOBS_RAW), { integrity_policy: 'compatible' }), textFetcher(JOBS_RAW), { subtle: null });
    await compatible.load('2026', 'jobs');
    assert.equal(compatible.integrityStatus('2026', 'jobs'), 'unverified-compatible');
    assert.deepEqual(compatible.integritySummary(), { verified: 0, 'unverified-compatible': 1, unhashed: 0 });
  }

  // --- 12. 旧式 fetcher（只有 json()，无 text()）：无 SHA 时兼容；有 SHA 时不得假装 verified ---
  {
    const legacy = async () => ({ ok: true, status: 200, async json() { return JSON.parse(JOBS_RAW); } });
    const noSha = new DataStore(plain, legacy);
    await noSha.load('2026', 'jobs');
    assert.equal(noSha.integrityStatus('2026', 'jobs'), 'unhashed');
    const withSha = new DataStore(manifestWith(entryFor(JOBS_RAW)), legacy);
    const error = await rejects(withSha.load('2026', 'jobs'), /完整性/, 'legacy fetcher with sha');
    assert.equal(error.code, 'unverifiable');
  }

  // --- 13. loadGlobal 同样验证 SHA ---
  {
    const globalRaw = JSON.stringify({ schema: 'wanyu-calendar/v1', items: [] });
    const good = new DataStore({ calendar: { data: 'data/calendar.json', bytes: bytesOf(globalRaw), sha256: sha256(globalRaw) } }, textFetcher(globalRaw));
    await good.loadGlobal('calendar');
    assert.equal(good.integrity.get('global:calendar'), 'verified');
    const bad = new DataStore({ calendar: { data: 'data/calendar.json', bytes: bytesOf(globalRaw), sha256: sha256(globalRaw) } }, textFetcher(globalRaw.replace('[]', '{}')));
    await rejects(bad.loadGlobal('calendar'), /SHA-256/, 'global tamper');
  }

  // --- 14. SHA 大小写不敏感（manifest 可能大写） ---
  {
    const store = new DataStore(manifestWith(entryFor(JOBS_RAW, { sha256: sha256(JOBS_RAW).toUpperCase() })), textFetcher(JOBS_RAW));
    await store.load('2026', 'jobs');
    assert.equal(store.integrityStatus('2026', 'jobs'), 'verified');
  }

  assert.equal(typeof IntegrityError, 'function');
  console.log('datastore contract: PASS (14 integrity scenarios)');
}

run().catch((error) => { console.error(error.stack || error); process.exit(1); });
