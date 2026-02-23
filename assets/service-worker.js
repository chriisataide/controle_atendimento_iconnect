// Service Worker básico para PWA offline e cache de assets
const CACHE_NAME = 'iconnect-cache-v2';
const urlsToCache = [
  '/',
  '/static/css/material-dashboard.css',
  '/static/img/icodev-logo.png',
  // Adicione outros assets importantes aqui
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return Promise.allSettled(
          urlsToCache.map(url => cache.add(url).catch(() => console.warn('SW: skip', url)))
        );
      })
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.filter(name => name !== CACHE_NAME)
          .map(name => caches.delete(name))
      );
    })
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});
