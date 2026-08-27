const CACHE_NAME = "maxcim-static-v1";
const STATIC_ASSETS = [
  "/static/css/dashboard.css",
  "/static/js/dashboard.js",
  "/static/js/material.js",
  "/static/js/sesiones.js",
  "/static/js/pwa.js",
  "/static/icons/maxcim.svg",
  "/static/icons/maxcim-192.png",
  "/static/icons/maxcim-512.png",
  "/static/offline.html",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)),
    )),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const requestUrl = new URL(event.request.url);
  if (event.request.method !== "GET" || requestUrl.origin !== self.location.origin) return;

  // Institutional and student information must never be persisted by the PWA cache.
  if (requestUrl.pathname.startsWith("/api/") || requestUrl.pathname.startsWith("/static/uploads/")) {
    return;
  }

  if (event.request.mode === "navigate") {
    event.respondWith(fetch(event.request).catch(() => caches.match("/static/offline.html")));
    return;
  }

  if (requestUrl.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request)),
    );
  }
});
