/* Coche service worker: the app shell works offline, the API is always live. */
const V = "coche-{{VERSION}}";
const BASE = "{{BASE}}";
const SHELL = [BASE + "/today", BASE + "/static/app.css?v={{VERSION}}", BASE + "/static/app.js?v={{VERSION}}",
  BASE + "/static/i18n.js?v={{VERSION}}", BASE + "/static/icon.svg?v={{VERSION}}"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(V).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith("coche-") && k !== V).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith(BASE + "/api/") || url.pathname.endsWith("/calendar.ics")) return;
  if (e.request.mode === "navigate") {
    e.respondWith(fetch(e.request).catch(() => caches.match(BASE + "/today")));
    return;
  }
  if (url.pathname.startsWith(BASE + "/static/")) {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request).then(res => {
      const copy = res.clone(); caches.open(V).then(c => c.put(e.request, copy)); return res;
    })));
  }
});
