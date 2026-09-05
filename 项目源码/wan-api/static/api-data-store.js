/**
 * APIDataStore - 动态网站数据加载层
 * 封装现有DataStore，优先从API获取数据，失败时fallback到静态JSON
 * 
 * 使用方式：
 * 1. 在maintainable-data.js之后加载此文件
 * 2. 初始化时传入API基础URL
 * 3. 自动替换原有的数据加载逻辑
 */
(() => {
  'use strict';
  
  // API配置
  const API_CONFIG = {
    baseUrl: '/api/v1',
    timeout: 10000,
    retryCount: 2
  };
  
  // 缓存键前缀
  const CACHE_PREFIX = 'wanyu_api_';
  
  /**
   * APIDataStore类
   */
  class APIDataStore {
    constructor(manifest, fetcher) {
      this.manifest = manifest || {};
      this.fetcher = fetcher || ((url, options) => globalThis.fetch(url, options));
      this.cache = new Map();
      this.inflight = new Map();
      this.apiEnabled = true;
      this.userToken = null;
    }
    
    /**
     * 设置用户令牌（用于需要认证的API）
     */
    setToken(token) {
      this.userToken = token;
    }
    
    /**
     * 获取请求头
     */
    getHeaders() {
      const headers = {
        'Content-Type': 'application/json'
      };
      if (this.userToken) {
        headers['Authorization'] = `Bearer ${this.userToken}`;
      }
      return headers;
    }
    
    /**
     * 从API获取数据
     */
    async fetchFromApi(url, options = {}) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), API_CONFIG.timeout);
      
      try {
        const response = await this.fetcher(url, {
          ...options,
          headers: this.getHeaders(),
          signal: controller.signal
        });
        
        if (!response.ok) {
          throw new Error(`API请求失败: ${response.status}`);
        }
        
        return await response.json();
      } finally {
        clearTimeout(timeoutId);
      }
    }
    
    /**
     * 从静态JSON获取数据（fallback）
     */
    async fetchFromStatic(url, entry = null) {
      let lastError;
      for (let attempt = 0; attempt < API_CONFIG.retryCount; attempt++) {
        try {
          const response = await this.fetcher(url, { cache: 'no-cache' });
          if (!response?.ok) throw new Error(`${url} · HTTP ${response?.status ?? 'unknown'}`);
          const raw = await response.text();
          return JSON.parse(raw);
        } catch (error) {
          lastError = error;
          if (attempt === 0) await Promise.resolve();
        }
      }
      throw lastError || new Error(`${url} · JSON 加载失败`);
    }
    
    /**
     * 加载周期模块数据
     */
    async load(cycle, module) {
      const key = `${cycle}:${module}`;
      if (this.cache.has(key)) return this.cache.get(key);
      if (this.inflight.has(key)) return this.inflight.get(key);
      
      const pending = this._loadInternal(cycle, module).then((payload) => {
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
    
    async _loadInternal(cycle, module) {
      // 尝试从API获取
      if (this.apiEnabled) {
        try {
          const apiUrl = `${API_CONFIG.baseUrl}/cycles/${cycle}/${module}`;
          const data = await this.fetchFromApi(apiUrl);
          console.log(`[APIDataStore] 从API加载成功: ${cycle}/${module}`);
          return data;
        } catch (error) {
          console.warn(`[APIDataStore] API请求失败，回退到静态文件: ${error.message}`);
        }
      }
      
      // 回退到静态JSON
      const entry = this._getModuleEntry(cycle, module);
      const url = entry?.data;
      if (!url) throw new Error(`manifest 未登记 ${cycle} ${module} 模块`);
      
      const data = await this.fetchFromStatic(url, entry);
      console.log(`[APIDataStore] 从静态文件加载: ${cycle}/${module}`);
      return data;
    }
    
    /**
     * 加载全局模块数据
     */
    async loadGlobal(name) {
      const key = `global:${name}`;
      if (this.cache.has(key)) return this.cache.get(key);
      if (this.inflight.has(key)) return this.inflight.get(key);
      
      const pending = this._loadGlobalInternal(name).then((payload) => {
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
    
    async _loadGlobalInternal(name) {
      // 尝试从API获取
      if (this.apiEnabled) {
        try {
          let apiUrl;
          if (name === 'salary') {
            apiUrl = `${API_CONFIG.baseUrl}/salary`;
          } else if (name === 'map') {
            apiUrl = `${API_CONFIG.baseUrl}/map`;
          } else if (name === 'audit') {
            apiUrl = `${API_CONFIG.baseUrl}/audit/three-year`;
          }
          
          if (apiUrl) {
            const data = await this.fetchFromApi(apiUrl);
            console.log(`[APIDataStore] 从API加载全局模块成功: ${name}`);
            return data;
          }
        } catch (error) {
          console.warn(`[APIDataStore] API请求失败，回退到静态文件: ${error.message}`);
        }
      }
      
      // 回退到静态JSON
      const entry = this.manifest?.[name];
      const url = entry?.data;
      if (!url) throw new Error(`manifest 未登记全局 ${name} 模块`);
      
      const data = await this.fetchFromStatic(url, entry);
      console.log(`[APIDataStore] 从静态文件加载全局模块: ${name}`);
      return data;
    }
    
    /**
     * 搜索岗位（使用API）
     */
    async searchJobs(params) {
      if (!this.apiEnabled) {
        throw new Error('API未启用');
      }
      
      const queryString = new URLSearchParams(params).toString();
      const url = `${API_CONFIG.baseUrl}/jobs/search?${queryString}`;
      return await this.fetchFromApi(url);
    }
    
    /**
     * 获取模块条目
     */
    _getModuleEntry(cycle, module) {
      const cycleEntry = (this.manifest?.cycles || []).find(
        (item) => String(item.cycle) === String(cycle)
      );
      return cycleEntry?.modules?.[module] || (module === 'jobs' ? cycleEntry : null);
    }
    
    /**
     * 清除缓存
     */
    clear() {
      this.cache.clear();
      this.inflight.clear();
    }
    
    /**
     * 启用/禁用API
     */
    setApiEnabled(enabled) {
      this.apiEnabled = enabled;
    }
  }
  
  /**
   * SyncUserStore - 用户数据同步
   * 封装localStorage，支持与API双写同步
   */
  class SyncUserStore {
    constructor(apiBaseUrl) {
      this.apiBaseUrl = apiBaseUrl || '/api/v1';
      this.userToken = null;
      this.localStore = {
        positions: [],
        snapshots: [],
        compare: []
      };
      this._loadFromLocal();
    }
    
    setToken(token) {
      this.userToken = token;
    }
    
    _loadFromLocal() {
      try {
        const stored = localStorage.getItem('wanyu.v15.positions');
        if (stored) this.localStore.positions = JSON.parse(stored);
        
        const snapshots = localStorage.getItem('wanyu.v15.snapshots');
        if (snapshots) this.localStore.snapshots = JSON.parse(snapshots);
        
        const compare = localStorage.getItem('wanyu.v15.compare');
        if (compare) this.localStore.compare = JSON.parse(compare);
      } catch (e) {
        console.warn('[SyncUserStore] 加载本地数据失败:', e);
      }
    }
    
    _saveToLocal() {
      try {
        localStorage.setItem('wanyu.v15.positions', JSON.stringify(this.localStore.positions));
        localStorage.setItem('wanyu.v15.snapshots', JSON.stringify(this.localStore.snapshots));
        localStorage.setItem('wanyu.v15.compare', JSON.stringify(this.localStore.compare));
      } catch (e) {
        console.warn('[SyncUserStore] 保存本地数据失败:', e);
      }
    }
    
    async _apiRequest(method, path, data = null) {
      if (!this.userToken) return null;
      
      const url = `${this.apiBaseUrl}${path}`;
      const options = {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.userToken}`
        }
      };
      
      if (data) {
        options.body = JSON.stringify(data);
      }
      
      const response = await fetch(url, options);
      if (!response.ok) return null;
      
      if (response.status === 204) return true;
      return await response.json();
    }
    
    // 收藏管理
    async addPosition(recordId, cycle, note = '') {
      // 本地立即生效
      const exists = this.localStore.positions.find(p => p.record_id === recordId);
      if (!exists) {
        this.localStore.positions.unshift({
          record_id: recordId,
          cycle,
          note,
          created_at: new Date().toISOString()
        });
        this._saveToLocal();
      }
      
      // 异步同步到API
      if (this.userToken) {
        this._apiRequest('POST', '/user/positions', { record_id: recordId, cycle, note });
      }
      
      return true;
    }
    
    async removePosition(recordId) {
      this.localStore.positions = this.localStore.positions.filter(p => p.record_id !== recordId);
      this._saveToLocal();
      
      if (this.userToken) {
        this._apiRequest('DELETE', `/user/positions/${recordId}`);
      }
      
      return true;
    }
    
    getPositions() {
      return this.localStore.positions;
    }
    
    // 快照管理
    async addSnapshot(snapshot) {
      this.localStore.snapshots.unshift({
        ...snapshot,
        id: Date.now().toString(),
        created_at: new Date().toISOString()
      });
      
      // 限制数量
      if (this.localStore.snapshots.length > 40) {
        this.localStore.snapshots = this.localStore.snapshots.slice(0, 40);
      }
      
      this._saveToLocal();
      
      if (this.userToken) {
        this._apiRequest('POST', '/user/snapshots', snapshot);
      }
      
      return true;
    }
    
    async removeSnapshot(id) {
      this.localStore.snapshots = this.localStore.snapshots.filter(s => s.id !== id);
      this._saveToLocal();
      
      if (this.userToken) {
        this._apiRequest('DELETE', `/user/snapshots/${id}`);
      }
      
      return true;
    }
    
    getSnapshots() {
      return this.localStore.snapshots;
    }
    
    // 对比列表管理
    async addToCompare(recordId, cycle) {
      const exists = this.localStore.compare.find(c => c.record_id === recordId);
      if (!exists && this.localStore.compare.length < 4) {
        this.localStore.compare.push({
          record_id: recordId,
          cycle,
          position: this.localStore.compare.length
        });
        this._saveToLocal();
        
        if (this.userToken) {
          this._apiRequest('POST', '/user/compare', { record_id: recordId, cycle });
        }
      }
      return true;
    }
    
    async removeFromCompare(recordId) {
      this.localStore.compare = this.localStore.compare.filter(c => c.record_id !== recordId);
      this._saveToLocal();
      
      if (this.userToken) {
        this._apiRequest('DELETE', `/user/compare/${recordId}`);
      }
      
      return true;
    }
    
    getCompareList() {
      return this.localStore.compare;
    }
    
    // 从API同步数据
    async syncFromApi() {
      if (!this.userToken) return;
      
      try {
        const [positions, snapshots, compare] = await Promise.all([
          this._apiRequest('GET', '/user/positions'),
          this._apiRequest('GET', '/user/snapshots'),
          this._apiRequest('GET', '/user/compare')
        ]);
        
        if (positions) this.localStore.positions = positions;
        if (snapshots) this.localStore.snapshots = snapshots;
        if (compare) this.localStore.compare = compare;
        
        this._saveToLocal();
        console.log('[SyncUserStore] 从API同步数据成功');
      } catch (e) {
        console.warn('[SyncUserStore] 从API同步数据失败:', e);
      }
    }
  }
  
  // 导出到全局
  const api = Object.freeze({
    APIDataStore,
    SyncUserStore,
    API_CONFIG
  });
  
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  if (typeof window !== 'undefined') {
    window.WanyuAPIDataStore = api;
  }
})();
