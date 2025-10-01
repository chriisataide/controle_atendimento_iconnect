// Service Worker básico para PWA offline e cache de assets
const CACHE_NAME = 'iconnect-cache-v1';
const urlsToCache = [
  '/',
  '/static/css/material-dashboard.css',
  '/static/css/dashboard-colors.css',
  '/static/css/mobile.css',
  '/static/js/main.js',
  '/static/img/icodev-logo.png',
  // Adicione outros assets importantes aqui
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
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
