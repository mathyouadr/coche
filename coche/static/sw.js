/* Coche service worker: the app shell works offline; the API is live, except the bootstrap (all tasks),
   which falls back to its last copy when the server does not answer within 4 s (marked X-Cached-At, so the app
   shows its offline banner). Writes made offline wait in the app's queue (outbox.js), not here.
   {type: "warm"} from a page refreshes the shell and the bootstrap copy, so Coche works offline even if it was
   never opened (the host page registers this worker). */
const V = "coche-{{VERSION}}";
const DATA = "coche-data";                     // kept across versions
const BASE = "{{BASE}}";
const TIMEOUT = 4000;
const BOOT = BASE + "/api/coche/bootstrap";
const SHELL = [BASE + "/today", BASE + "/static/app.css?v={{VERSION}}", BASE + "/static/app.js?v={{VERSION}}",
  BASE + "/static/outbox.js?v={{VERSION}}", BASE + "/static/i18n.js?v={{VERSION}}", BASE + "/static/icon.svg?v={{VERSION}}"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(V).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith("coche-") && k !== V && k !== DATA).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

const stamp = res => { const h = new Headers(res.headers); h.set("X-Cached-At", String(Date.now()));
  return new Response(res.body, { status: res.status, statusText: res.statusText, headers: h }); };

// Network first; after 4 s (or no answer, or the proxy says the app is down) the cached copy.
function netOrCache(e, cacheName, key, onFresh) {
  const net = fetch(e.request).then(async res => { if (res.ok && onFresh) await onFresh(res.clone()); return res; });
  e.waitUntil(net.catch(() => {}));
  return new Promise(resolve => {
    let done = false;
    const fallback = async () => {
      if (done) return false;
      const hit = await caches.open(cacheName).then(c => c.match(key));
      if (done || !hit) return false;
      done = true; resolve(hit); return true;
    };
    const timer = setTimeout(fallback, TIMEOUT);
    net.then(async res => { clearTimeout(timer); if (res.status >= 502 && await fallback()) return; if (!done) { done = true; resolve(res); } },
      async () => { clearTimeout(timer); if (await fallback() || done) return; done = true; resolve(Response.error()); });
  });
}

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname === BOOT) {
    e.respondWith(netOrCache(e, DATA, BOOT, res => caches.open(DATA).then(c => c.put(BOOT, stamp(res)))));
    return;
  }
  if (url.pathname.startsWith(BASE + "/api/") || url.pathname.endsWith("/calendar.ics")) return;
  if (e.request.mode === "navigate") {
    e.respondWith(netOrCache(e, V, BASE + "/today"));
    return;
  }
  if (url.pathname.startsWith(BASE + "/static/")) {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request).then(res => {
      const copy = res.clone(); caches.open(V).then(c => c.put(e.request, copy)); return res;
    })));
  }
});

self.addEventListener("message", e => {
  if (!e.data || e.data.type !== "warm") return;
  e.waitUntil(fetch(BOOT, { cache: "no-store", credentials: "same-origin" })
    .then(res => res.ok && caches.open(DATA).then(c => c.put(BOOT, stamp(res)))).catch(() => {}));
});
