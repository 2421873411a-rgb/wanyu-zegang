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
    if (module === 'major_city' && (payload.schema !== 'wanyu-maintainable-major-city/v1' || !payload.keywords || typeof payload.keywords !== 'object' || !Number.isFinite(Number(payload.rows_total)))) throw new Error(`${cycle} major_city.json 缺少专业城市索引`);
    return payload;
  };
  class DataStore {
    constructor(manifest, fetcher) {
      this.manifest = manifest || {};
      this.fetcher = fetcher || ((url, options) => globalThis.fetch(url, options));
      this.cache = new Map();
      this.inflight = new Map();
    }
    async requestJson(url, entry = null) {
      const response = await this.fetchWithRetry(url);
      if (typeof response.text !== 'function') return await response.json();
      const raw = await response.text();
      // 只编码一次，字节数与 SHA-256 校验复用同一份 Uint8Array，避免大文件重复拷贝
      const bytes = (entry?.bytes != null || entry?.sha256) && typeof TextEncoder !== 'undefined'
        ? new TextEncoder().encode(raw)
        : null;
      if (entry?.bytes != null && bytes && bytes.byteLength !== Number(entry.bytes)) {
        throw new Error(`${url} · 字节数与 manifest 不一致`);
      }
      if (entry?.sha256 && globalThis.crypto?.subtle && bytes) {
        const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
        const actual = [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, '0')).join('');
        if (actual !== String(entry.sha256)) throw new Error(`${url} · SHA-256 与 manifest 不一致`);
      }
      return JSON.parse(raw);
    }
    async fetchWithRetry(url) {
      let lastError;
      for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
          const response = await this.fetcher(url, { cache: 'no-cache' });
          if (!response?.ok) throw new Error(`${url} · HTTP ${response?.status ?? 'unknown'}`);
          return response;
        } catch (error) {
          lastError = error;
          if (attempt === 0) await Promise.resolve();
        }
      }
      throw lastError || new Error(`${url} · JSON 加载失败`);
    }
    async load(cycle, module) {
      const entry = moduleEntry(this.manifest, cycle, module);
      const key = `${cycle}:${module}:${entry?.sha256 || 'unhashed'}`;
      if (this.cache.has(key)) return this.cache.get(key);
      if (this.inflight.has(key)) return this.inflight.get(key);
      const url = modulePath(this.manifest, cycle, module);
      if (!url) throw new Error(`manifest 未登记 ${cycle} ${module} 模块`);
      const pending = this.requestJson(url, entry).then((payload) => {
        const validated = validatePayload(payload, cycle, module);
        this.cache.set(key, validated);
        this.inflight.delete(key);
        return validated;
      }).catch((error) => {
        this.inflight.delete(key);
        throw error;
      });
      this.inflight.set(key, pending);
      return pending;
    }
    async loadGlobal(name) {
      const key = `global:${name}`;
      if (this.cache.has(key)) return this.cache.get(key);
      if (this.inflight.has(key)) return this.inflight.get(key);
      const entry = this.manifest?.[name];
      const url = entry?.data;
      if (!url) throw new Error(`manifest 未登记全局 ${name} 模块`);
      const pending = this.requestJson(url, entry).then((payload) => {
        if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error(`${name} JSON 不是对象`);
        this.cache.set(key, payload);
        this.inflight.delete(key);
        return payload;
      }).catch((error) => {
        this.inflight.delete(key);
        throw error;
      });
      this.inflight.set(key, pending);
      return pending;
    }
    clear() {
      this.cache.clear();
      this.inflight.clear();
    }
  }
  const api = Object.freeze({ DataStore, modulePath, validatePayload });
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.WanyuDataStore = api;
})();
