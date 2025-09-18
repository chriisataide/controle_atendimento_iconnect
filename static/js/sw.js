// Service Worker para PWA - Sistema de Controle de Atendimento iConnect
// Versão: 1.0.0 - Mobile Enhanced
// Data: 2024

const CACHE_NAME = 'iconnect-v1.0.0';
const STATIC_CACHE = 'iconnect-static-v1.0.0';
const DYNAMIC_CACHE = 'iconnect-dynamic-v1.0.0';
const MOBILE_CACHE = 'iconnect-mobile-v1.0.0';
const OFFLINE_URL = '/mobile/offline/';

// Recursos essenciais para cache offline
const STATIC_ASSETS = [
    '/',
    '/dashboard/',
    '/dashboard/chat/',
    '/mobile/',
    '/mobile/tickets/',
    '/mobile/offline/',
    '/static/css/dashboard.css',
    '/static/css/material-dashboard.min.css',
    '/static/js/dashboard.js',
    '/static/js/material-dashboard.min.js',
    '/static/js/chat.js',
    '/static/js/core/bootstrap.bundle.min.js',
    '/static/img/logo-ct.png',
    '/static/img/favicon.png',
    '/static/assets/fonts/nucleo-icons.woff2',
    '/static/assets/fonts/nucleo.woff2',
    'https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap',
    'https://fonts.googleapis.com/icon?family=Material+Icons',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css'
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

// Funcionalidades específicas para Mobile

// Lidar com requisições mobile offline
function handleMobileOffline(request) {
    const url = new URL(request.url);
    
    // Se é uma requisição mobile e estamos offline
    if (url.pathname.startsWith('/mobile/')) {
        // Para páginas HTML, redirecionar para página offline
        if (request.headers.get('accept').includes('text/html')) {
            return caches.match(OFFLINE_URL) || 
                   caches.match('/mobile/') ||
                   new Response('Offline', { status: 503 });
        }
        
        // Para APIs, retornar resposta JSON offline
        return new Response(JSON.stringify({
            offline: true,
            message: 'Dados não disponíveis offline',
            timestamp: Date.now()
        }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' }
        });
    }
    
    return new Response('Not Found', { status: 404 });
}

// Estratégia específica para dados de tickets mobile
async function handleMobileTicketData(request) {
    const cache = await caches.open(MOBILE_CACHE);
    const cachedResponse = await cache.match(request);
    
    try {
        // Network first para dados atualizados
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            cache.put(request, networkResponse.clone());
            return networkResponse;
        }
        
        // Se network falha mas temos cache, usar cache
        if (cachedResponse) {
            return cachedResponse;
        }
        
        return handleMobileOffline(request);
        
    } catch (error) {
        // Offline - usar cache se disponível
        if (cachedResponse) {
            return cachedResponse;
        }
        
        return handleMobileOffline(request);
    }
}

// Armazenar dados mobile para sincronização posterior
async function storeMobilePendingData(request, data) {
    try {
        // Usar IndexedDB para armazenamento persistente
        // Implementação simplificada aqui
        const pendingKey = `mobile_pending_${Date.now()}`;
        
        // Em implementação real, usar IndexedDB
        console.log('[SW] Storing mobile pending data:', pendingKey, data);
        
        // Agendar sincronização
        if ('serviceWorker' in navigator && 'sync' in window.ServiceWorkerRegistration.prototype) {
            await self.registration.sync.register('mobile-sync');
        }
        
        return true;
    } catch (error) {
        console.error('[SW] Error storing mobile pending data:', error);
        return false;
    }
}

// Sincronização específica para mobile
self.addEventListener('sync', (event) => {
    if (event.tag === 'mobile-sync') {
        console.log('[SW] Mobile background sync triggered');
        event.waitUntil(syncMobilePendingData());
    }
});

async function syncMobilePendingData() {
    try {
        console.log('[SW] Syncing mobile pending data...');
        
        // Aqui você implementaria a lógica para:
        // 1. Recuperar dados pendentes do IndexedDB
        // 2. Tentar enviar para o servidor
        // 3. Remover dados sincronizados com sucesso
        
        // Por agora, apenas log
        console.log('[SW] Mobile sync completed');
    } catch (error) {
        console.error('[SW] Mobile sync failed:', error);
    }
}

// Notificações push para mobile
self.addEventListener('push', (event) => {
    if (event.data) {
        const data = event.data.json();
        
        const options = {
            body: data.body || 'Nova atualização no iConnect',
            icon: '/static/img/logo-ct.png',
            badge: '/static/img/favicon.png',
            tag: data.tag || 'iconnect-mobile',
            vibrate: [200, 100, 200], // Padrão de vibração para mobile
            actions: [
                { action: 'open', title: 'Abrir', icon: '/static/img/logo-ct.png' },
                { action: 'close', title: 'Fechar' }
            ],
            data: data.url || '/mobile/'
        };
        
        event.waitUntil(
            self.registration.showNotification(data.title || 'iConnect', options)
        );
    }
});

// Lidar com cliques em notificações mobile
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    
    const urlToOpen = event.notification.data || '/mobile/';
    
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((clientList) => {
                // Se já tem uma janela aberta, focar nela
                for (const client of clientList) {
                    if (client.url.includes('/mobile/') && 'focus' in client) {
                        return client.focus();
                    }
                }
                
                // Senão, abrir nova janela
                if (clients.openWindow) {
                    return clients.openWindow(urlToOpen);
                }
            })
    );
});

// Log de informações do Service Worker
console.log('[SW] Service Worker loaded successfully - Mobile Enhanced');
