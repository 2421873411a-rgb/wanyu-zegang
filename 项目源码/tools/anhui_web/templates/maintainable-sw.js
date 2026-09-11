/* 皖域择岗维护站 Service Worker
   策略（v17.9.2 审计 FE-005/006 起双缓存分层）：
   - wanyu-shell-<VERSION>：页面导航、静态资产、无 sha 的 JSON——network-first/stale-while-revalidate，
     activate 时随版本整体换代；
   - wanyu-data：带 ?sha= 的 JSON——cache-first，跨 shell 版本保留（URL 即版本，内容不变就永远命中），
     同路径旧 sha 条目按需清理；数据完整性由 DataStore 的 SHA-256 digest 校验保证，
     URL 里的 sha 只是缓存键/版本号，不证明内容正确。 */
const VERSION = "__SW_VERSION__";
const SHELL_CACHE = `wanyu-shell-${VERSION}`;
const DATA_CACHE = "wanyu-data-v1";
const PRECACHE = [
  "index.html",
  "manifest.webmanifest",
  "assets/maintainable-tokens.css?v=__ASSET_VERSION__",
  "assets/maintainable-site.css?v=__ASSET_VERSION__",
  "assets/v17-ui-upgrade.css?v=__ASSET_VERSION__",
  "assets/v17-search.css?v=__ASSET_VERSION__",
  "assets/v17-tools.css?v=__ASSET_VERSION__",
  "assets/v17-exam-picker.css?v=__ASSET_VERSION__",
  "assets/maintainable-data.js?v=__ASSET_VERSION__",
  "assets/maintainable-major-city.js?v=__ASSET_VERSION__",
  "assets/maintainable-user-store.js?v=__ASSET_VERSION__",
  "assets/v17-tools.js?v=__ASSET_VERSION__",
  "assets/maintainable-site.js?v=__ASSET_VERSION__",
  "assets/wanyu-icon.svg?v=__ASSET_VERSION__",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      // 审计 FE-006：只换代 shell 缓存；wanyu-data 跨版本保留，未变化的 ?sha= 数据不再重复下载
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith("wanyu-shell-") && key !== SHELL_CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (request.mode === "navigate" || url.pathname.endsWith(".html")) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (!response || !response.ok) throw new Error("bad response");
          const copy = response.clone();
          caches.open(SHELL_CACHE).then((cache) => cache.put(request, copy)).catch(() => {});
          return response;
        })
        .catch(() => caches.match("index.html").then((hit) => hit || Response.error()))
    );
    return;
  }
  if (url.pathname.includes("/data/") || url.pathname.endsWith(".json")) {
    // 内容寻址（?sha=）：URL 即版本，命中即回，miss 才回源；同路径旧 sha 条目顺手清理
    if (url.searchParams.has("sha")) {
      event.respondWith(
        caches.open(DATA_CACHE).then((cache) => cache.match(request)).then((hit) => {
          if (hit) return hit;
          return fetch(request).then((response) => {
            if (!response || !response.ok) throw new Error("bad response");
            const copy = response.clone();
            caches.open(DATA_CACHE).then((cache) => {
              cache.put(request, copy).catch(() => {});
              cache.keys().then((keys) => {
                for (const key of keys) {
                  const kUrl = new URL(key.url);
                  if (kUrl.pathname === url.pathname && kUrl.searchParams.get("sha") !== url.searchParams.get("sha")) {
                    cache.delete(key).catch(() => {});
                  }
                }
              }).catch(() => {});
            }).catch(() => {});
            return response;
          });
        })
      );
      return;
    }
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (!response || !response.ok) throw new Error("bad response");
          const copy = response.clone();
          caches.open(DATA_CACHE).then((cache) => cache.put(request, copy)).catch(() => {});
          return response;
        })
        .catch(() => caches.match(request).then((hit) => hit || Response.error()))
    );
    return;
  }
  event.respondWith(
    caches.match(request).then((hit) => {
      const refresh = fetch(request)
        .then((response) => {
          if (!response || !response.ok) throw new Error("bad response");
          const copy = response.clone();
          caches.open(SHELL_CACHE).then((cache) => cache.put(request, copy)).catch(() => {});
          return response;
        })
        .catch(() => hit);
      return hit || refresh;
    })
  );
});
