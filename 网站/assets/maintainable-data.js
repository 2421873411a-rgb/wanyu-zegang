(() => {
  const cycleEntry = (manifest, cycle) => (manifest?.cycles || []).find((item) => String(item.cycle) === String(cycle));
  const moduleEntry = (manifest, cycle, module) => cycleEntry(manifest, cycle)?.modules?.[module] || (module === 'jobs' ? cycleEntry(manifest, cycle) : null);
  const modulePath = (manifest, cycle, module) => {
    if (cycle === 'audit' && module === 'three-year') return manifest?.audit?.data || null;
    if (cycle === 'review_queue' && module === 'queue') return manifest?.review_queue?.data || null;
    const entry = cycleEntry(manifest, cycle);
    return entry?.modules?.[module]?.data || (module === 'jobs' ? entry?.data : null);
  };
  const validatePayload = (payload, cycle, module) => {
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error(`${cycle} ${module} JSON 不是对象`);
    if (module === 'jobs' && (!payload.allMajors?.meta || !Array.isArray(payload.allMajors.rows))) throw new Error(`${cycle} jobs.json 缺少 allMajors.rows`);
    if (module === 'jobs_lite' && (!payload.allMajors?.meta || !Array.isArray(payload.allMajors.rows))) throw new Error(`${cycle} jobs_lite.json 缺少 allMajors.rows`);
    if (module === 'overview' && !payload.allMajors?.meta) throw new Error(`${cycle} overview.json 缺少摘要`);
    if (module === 'catalog' && (!Array.isArray(payload.majors) || !payload.facets)) throw new Error(`${cycle} catalog.json 缺少专业目录或筛选面`);
    if (module === 'positions' && (!Array.isArray(payload.rows) || payload.source_module !== 'jobs.json')) throw new Error(`${cycle} positions.json 缺少岗位索引`);
    if (module === 'changes' && (!Array.isArray(payload.changes) || !payload.summary || !payload.target_cycle)) throw new Error(`${cycle} changes.json 缺少跨周期变化摘要`);
    if (module === 'scores' && (!payload.summary || !payload.keyed)) throw new Error(`${cycle} scores.json 缺少成绩索引摘要`);
    if (module === 'audit' && !payload.audit) throw new Error(`${cycle} audit.json 缺少周期审计`);
    if (module === 'req_fields' && payload.schema !== 'wanyu-req-fields/v1') throw new Error(`${cycle} req-fields 结构不符`);
    if (module === 'major_index' && (!payload.postings?.explicit || !Array.isArray(payload.majors))) throw new Error(`${cycle} major-index.json 缺少倒排索引`);
    if (module === 'major_city' && (payload.schema !== 'wanyu-maintainable-major-city/v1' || !payload.keywords || typeof payload.keywords !== 'object' || !Number.isFinite(Number(payload.rows_total)))) throw new Error(`${cycle} major_city.json 缺少专业城市索引`);
    return payload;
  };

  // 完整性失败与普通网络/结构错误分开：UI 与测试都能按 code 区分“文件被改了”还是“没加载到”
  class IntegrityError extends Error {
    constructor(message, code) {
      super(message);
      this.name = 'IntegrityError';
      this.code = code;
    }
  }
  const hexOf = (buffer) => [...new Uint8Array(buffer)].map((value) => value.toString(16).padStart(2, '0')).join('');

  // 两个语义彻底分开，互不代替：
  //   cacheAddressed  —— URL 带 ?sha=<prefix>，只是 Service Worker 的缓存键/版本号
  //   verifyIntegrity —— manifest 给了 sha256 就必须对响应字节做 SHA-256 digest 比对
  // 完整性状态三态：verified / unverified-compatible / unhashed；失败直接抛 IntegrityError（fail closed）
  class DataStore {
    constructor(manifest, fetcher, options = {}) {
      this.manifest = manifest || {};
      this.fetcher = fetcher || ((url, init) => globalThis.fetch(url, init));
      this.cache = new Map();
      this.inflight = new Map();
      this.integrity = new Map();
      // strict（默认）：有 SHA 但当前环境无法校验 → 拒绝加载；compatible：明确标记为 unverified-compatible 后继续
      this.integrityPolicy = options.integrityPolicy || this.manifest?.integrity_policy || 'strict';
      this.subtle = options.subtle === undefined ? (globalThis.crypto?.subtle || null) : options.subtle;
    }
    degradeOrThrow(message, code) {
      if (this.integrityPolicy === 'compatible') return 'unverified-compatible';
      throw new IntegrityError(message, code);
    }
    async requestJson(url, entry = null, options = {}) {
      const cacheAddressed = typeof options === 'boolean' ? options : Boolean(options?.cacheAddressed);
      const verifyIntegrity = options && typeof options === 'object' && options.verifyIntegrity !== undefined
        ? Boolean(options.verifyIntegrity)
        : Boolean(entry?.sha256);
      const response = await this.fetchWithRetry(url, cacheAddressed);
      if (typeof response.text !== 'function') {
        // 只有 json() 的响应无法做字节级核对：manifest 给了 SHA 就不能假装 verified
        let integrity = 'unhashed';
        if (verifyIntegrity && entry?.sha256) integrity = this.degradeOrThrow(`${url} · 响应不支持字节级完整性校验`, 'unverifiable');
        return { payload: await response.json(), integrity };
      }
      const raw = await response.text();
      const needBytes = entry?.bytes != null || (verifyIntegrity && entry?.sha256);
      // 只编码一次，字节数与 SHA-256 校验复用同一份 Uint8Array，避免大文件重复拷贝
      const bytes = needBytes && typeof TextEncoder !== 'undefined' ? new TextEncoder().encode(raw) : null;
      let integrity = 'unhashed';
      if (entry?.bytes != null) {
        if (!bytes) integrity = this.degradeOrThrow(`${url} · 当前环境无法核对字节数`, 'unverifiable');
        else if (bytes.byteLength !== Number(entry.bytes)) throw new IntegrityError(`${url} · 字节数与 manifest 不一致`, 'bytes-mismatch');
      }
      if (verifyIntegrity && entry?.sha256) {
        if (!this.subtle || !bytes) {
          integrity = this.degradeOrThrow(`${url} · 当前环境不支持 SHA-256 校验（Web Crypto 不可用），已拒绝加载`, 'integrity-unavailable');
        } else {
          const digest = await this.subtle.digest('SHA-256', bytes);
          if (hexOf(digest) !== String(entry.sha256).toLowerCase()) throw new IntegrityError(`${url} · SHA-256 与 manifest 不一致`, 'sha256-mismatch');
          integrity = 'verified';
        }
      }
      return { payload: JSON.parse(raw), integrity };
    }
    async fetchWithRetry(url, cacheAddressed = false) {
      let lastError;
      for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
          const response = await this.fetcher(url, { cache: cacheAddressed ? 'default' : 'no-cache' });
          if (!response?.ok) throw new Error(`${url} · HTTP ${response?.status ?? 'unknown'}`);
          return response;
        } catch (error) {
          lastError = error;
          if (attempt === 0) await Promise.resolve();
        }
      }
      throw lastError || new Error(`${url} · JSON 加载失败`);
    }
    addressedUrl(base, entry) {
      const cacheAddressed = Boolean(entry?.sha256);
      return { cacheAddressed, url: cacheAddressed ? `${base}?sha=${String(entry.sha256).slice(0, 16)}` : base };
    }
    trackPending(key, pending) {
      const tracked = pending.then((result) => {
        this.inflight.delete(key);
        return result;
      }).catch((error) => {
        this.inflight.delete(key);
        throw error;
      });
      this.inflight.set(key, tracked);
      return tracked;
    }
    async load(cycle, module) {
      const entry = moduleEntry(this.manifest, cycle, module);
      const key = `${cycle}:${module}:${entry?.sha256 || 'unhashed'}`;
      if (this.cache.has(key)) return this.cache.get(key);
      if (this.inflight.has(key)) return this.inflight.get(key);
      const base = modulePath(this.manifest, cycle, module);
      if (!base) throw new Error(`manifest 未登记 ${cycle} ${module} 模块`);
      const { cacheAddressed, url } = this.addressedUrl(base, entry);
      return this.trackPending(key, this.requestJson(url, entry, { cacheAddressed, verifyIntegrity: Boolean(entry?.sha256) }).then(({ payload, integrity }) => {
        const validated = validatePayload(payload, cycle, module);
        this.cache.set(key, validated);
        this.integrity.set(key, integrity);
        return validated;
      }));
    }
    async loadGlobal(name) {
      const key = `global:${name}`;
      if (this.cache.has(key)) return this.cache.get(key);
      if (this.inflight.has(key)) return this.inflight.get(key);
      const entry = this.manifest?.[name];
      const base = entry?.data;
      if (!base) throw new Error(`manifest 未登记全局 ${name} 模块`);
      const { cacheAddressed, url } = this.addressedUrl(base, entry);
      return this.trackPending(key, this.requestJson(url, entry, { cacheAddressed, verifyIntegrity: Boolean(entry?.sha256) }).then(({ payload, integrity }) => {
        if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error(`${name} JSON 不是对象`);
        this.cache.set(key, payload);
        this.integrity.set(key, integrity);
        return payload;
      }));
    }
    integrityStatus(cycle, module) {
      const entry = moduleEntry(this.manifest, cycle, module);
      return this.integrity.get(`${cycle}:${module}:${entry?.sha256 || 'unhashed'}`) || null;
    }
    integritySummary() {
      const summary = { verified: 0, 'unverified-compatible': 0, unhashed: 0 };
      this.integrity.forEach((status) => { summary[status] = (summary[status] || 0) + 1; });
      return summary;
    }
    clear() {
      this.cache.clear();
      this.inflight.clear();
      this.integrity.clear();
    }
  }
  const api = Object.freeze({ DataStore, IntegrityError, modulePath, validatePayload });
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.WanyuDataStore = api;
})();
