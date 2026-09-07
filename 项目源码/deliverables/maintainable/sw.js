/* 皖域择岗维护站 Service Worker
   策略：页面导航与数据 JSON 一律 network-first（在线立即拿新，离线回退缓存）；
   其余静态资产 cache-first 并后台刷新（URL 带 ?v= 版本号，改版即失效）。 */
const VERSION = "wanyu-shell-v41";
const PRECACHE = [
  "index.html",
  "manifest.webmanifest",
  "assets/maintainable-tokens.css?v=17.7.1",
  "assets/maintainable-site.css?v=17.7.1",
  "assets/v17-ui-upgrade.css?v=17.7.1",
  "assets/v17-search.css?v=17.7.1",
  "assets/v17-tools.css?v=17.7.1",
  "assets/v17-exam-picker.css?v=17.7.1",
  "assets/maintainable-data.js?v=17.7.1",
  "assets/maintainable-major-city.js?v=17.7.1",
  "assets/maintainable-user-store.js?v=17.7.1",
  "assets/v17-tools.js?v=17.7.1",
  "assets/maintainable-site.js?v=17.7.1",
  "data/audit/supplement-20260904.json",
  "assets/wanyu-icon.svg?v=17.7.1",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(VERSION)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== VERSION).map((key) => caches.delete(key))))
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
          caches.open(VERSION).then((cache) => cache.put(request, copy)).catch(() => {});
          return response;
        })
        .catch(() => caches.match("index.html").then((hit) => hit || Response.error()))
    );
    return;
  }
  if (url.pathname.includes("/data/") || url.pathname.endsWith(".json")) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (!response || !response.ok) throw new Error("bad response");
          const copy = response.clone();
          caches.open(VERSION).then((cache) => cache.put(request, copy)).catch(() => {});
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
          caches.open(VERSION).then((cache) => cache.put(request, copy)).catch(() => {});
          return response;
        })
        .catch(() => hit);
      return hit || refresh;
    })
  );
});
