// Service Worker para PWA - Sistema de Controle de Atendimento iConnect
// Versão: 1.0.0
// Data: 2024

const CACHE_NAME = 'iconnect-v1.0.0';
const STATIC_CACHE = 'iconnect-static-v1.0.0';
const DYNAMIC_CACHE = 'iconnect-dynamic-v1.0.0';

// Recursos essenciais para cache offline
const STATIC_ASSETS = [
    '/',
    '/dashboard/',
    '/dashboard/chat/',
    '/static/css/dashboard.css',
    '/static/js/dashboard.js',
    '/static/js/chat.js',
    '/static/img/logo-ct.png',
    '/static/img/favicon.png',
    'https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap',
    'https://fonts.googleapis.com/icon?family=Material+Icons'
];

// URLs que sempre devem buscar da rede
const NETWORK_FIRST_URLS = [
    '/api/',
    '/ws/',
    '/dashboard/api/',
    '/chat/api/'
];

// URLs que podem ser servidas do cache primeiro
const CACHE_FIRST_URLS = [
    '/static/',
    '/media/',
    'https://fonts.googleapis.com/',
    'https://fonts.gstatic.com/'
];

// Instalação do Service Worker
self.addEventListener('install', (event) => {
    console.log('[SW] Installing Service Worker...');
    
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then((cache) => {
                console.log('[SW] Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                console.log('[SW] Static assets cached successfully');
                return self.skipWaiting();
            })
            .catch((error) => {
                console.error('[SW] Error caching static assets:', error);
            })
    );
});

// Ativação do Service Worker
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating Service Worker...');
    
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
                        console.log('[SW] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => {
            console.log('[SW] Service Worker activated');
            return self.clients.claim();
        })
    );
});

// Interceptação de requisições
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Ignorar requisições de extensões do navegador
    if (url.protocol === 'chrome-extension:') {
        return;
    }

    // Network First para APIs e dados dinâmicos
    if (isNetworkFirstUrl(request.url)) {
        event.respondWith(networkFirst(request));
    }
    // Cache First para recursos estáticos
    else if (isCacheFirstUrl(request.url)) {
        event.respondWith(cacheFirst(request));
    }
    // Stale While Revalidate para páginas HTML
    else if (request.headers.get('accept').includes('text/html')) {
        event.respondWith(staleWhileRevalidate(request));
    }
    // Network with Cache Fallback para outros recursos
    else {
        event.respondWith(networkWithCacheFallback(request));
    }
});

// Estratégia Network First
async function networkFirst(request) {
    try {
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            const cache = await caches.open(DYNAMIC_CACHE);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.log('[SW] Network failed, trying cache for:', request.url);
        const cachedResponse = await caches.match(request);
        
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // Fallback para páginas offline
        if (request.headers.get('accept').includes('text/html')) {
            return caches.match('/offline/');
        }
        
        throw error;
    }
}

// Estratégia Cache First
async function cacheFirst(request) {
    const cachedResponse = await caches.match(request);
    
    if (cachedResponse) {
        return cachedResponse;
    }
    
    try {
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            const cache = await caches.open(DYNAMIC_CACHE);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.error('[SW] Cache and network failed for:', request.url);
        throw error;
    }
}

// Estratégia Stale While Revalidate
async function staleWhileRevalidate(request) {
    const cachedResponse = await caches.match(request);
    
    const fetchPromise = fetch(request).then((networkResponse) => {
        if (networkResponse.ok) {
            const cache = caches.open(DYNAMIC_CACHE);
            cache.then(c => c.put(request, networkResponse.clone()));
        }
        return networkResponse;
    }).catch(() => {
        // Se a rede falhar, retorna o cache se disponível
        return cachedResponse;
    });
    
    return cachedResponse || fetchPromise;
}

// Estratégia Network with Cache Fallback
async function networkWithCacheFallback(request) {
    try {
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            const cache = await caches.open(DYNAMIC_CACHE);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        throw error;
    }
}

// Utilitários para identificar tipos de URL
function isNetworkFirstUrl(url) {
    return NETWORK_FIRST_URLS.some(pattern => url.includes(pattern));
}

function isCacheFirstUrl(url) {
    return CACHE_FIRST_URLS.some(pattern => url.includes(pattern));
}

// Manipulador de mensagens do cliente
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    
    if (event.data && event.data.type === 'GET_VERSION') {
        event.ports[0].postMessage({ version: CACHE_NAME });
    }
    
    if (event.data && event.data.type === 'CLEAR_CACHE') {
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => caches.delete(cacheName))
            );
        }).then(() => {
            event.ports[0].postMessage({ success: true });
        });
    }
});

// Manipulador de notificações push
self.addEventListener('push', (event) => {
    console.log('[SW] Push message received');
    
    const options = {
        body: 'Você tem novas atualizações!',
        icon: '/static/img/logo-ct.png',
        badge: '/static/img/favicon.png',
        vibrate: [200, 100, 200],
        data: {
            dateOfArrival: Date.now(),
            primaryKey: 1
        },
        actions: [
            {
                action: 'explore',
                title: 'Ver detalhes',
                icon: '/static/img/logo-ct.png'
            },
            {
                action: 'close',
                title: 'Fechar',
                icon: '/static/img/logo-ct.png'
            }
        ]
    };
    
    if (event.data) {
        const data = event.data.json();
        options.body = data.body || options.body;
        options.title = data.title || 'iConnect';
        options.data = { ...options.data, ...data };
    }
    
    event.waitUntil(
        self.registration.showNotification('iConnect', options)
    );
});

// Manipulador de cliques em notificações
self.addEventListener('notificationclick', (event) => {
    console.log('[SW] Notification click received');
    
    event.notification.close();
    
    if (event.action === 'explore') {
        event.waitUntil(
            clients.openWindow('/dashboard/')
        );
    } else if (event.action === 'close') {
        // Apenas fecha a notificação
        return;
    } else {
        // Clique na notificação (não em uma ação)
        event.waitUntil(
            clients.matchAll().then((clientList) => {
                if (clientList.length > 0) {
                    return clientList[0].focus();
                }
                return clients.openWindow('/dashboard/');
            })
        );
    }
});

// Sincronização em background
self.addEventListener('sync', (event) => {
    console.log('[SW] Background sync:', event.tag);
    
    if (event.tag === 'background-sync') {
        event.waitUntil(doBackgroundSync());
    }
});

async function doBackgroundSync() {
    try {
        // Sincroniza dados pendentes quando a conexão for restaurada
        const pendingData = await getStoredPendingData();
        
        for (const data of pendingData) {
            try {
                await fetch(data.url, {
                    method: data.method,
                    headers: data.headers,
                    body: data.body
                });
                
                // Remove dados sincronizados com sucesso
                await removePendingData(data.id);
            } catch (error) {
                console.error('[SW] Failed to sync data:', error);
            }
        }
    } catch (error) {
        console.error('[SW] Background sync failed:', error);
    }
}

// Utilitários para dados pendentes (simples implementação)
async function getStoredPendingData() {
    // Implementação simples - na produção, usar IndexedDB
    return [];
}

async function removePendingData(id) {
    // Implementação simples - na produção, usar IndexedDB
    return true;
}

// Log de informações do Service Worker
console.log('[SW] Service Worker loaded successfully');
