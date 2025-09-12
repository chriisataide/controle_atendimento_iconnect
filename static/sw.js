// Service Worker para iConnect PWA
const CACHE_NAME = 'iconnect-pwa-v1.1';
const OFFLINE_URL = '/dashboard/';

// Recursos para cache (apenas arquivos estáticos para evitar erros de autenticação)
const CACHE_URLS = [
    '/static/css/material-dashboard.min.css',
    '/static/css/dashboard-colors.css',
    '/static/js/material-dashboard.min.js',
    '/static/js/plugins/chartjs.min.js',
    '/static/img/logo-ct-dark.png',
    '/static/img/icons/icon-192x192.png',
    '/static/manifest.json'
];

// Instalar Service Worker
self.addEventListener('install', event => {
    console.log('📦 Service Worker: Instalando...');
    
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('📦 Service Worker: Fazendo cache dos arquivos');
                return cache.addAll(CACHE_URLS);
            })
            .then(() => {
                console.log('📦 Service Worker: Instalado com sucesso');
                return self.skipWaiting();
            })
    );
});

// Ativar Service Worker
self.addEventListener('activate', event => {
    console.log('🚀 Service Worker: Ativando...');
    
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('🧹 Service Worker: Removendo cache antigo', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => {
            console.log('🚀 Service Worker: Ativado com sucesso');
            return self.clients.claim();
        })
    );
});

// Interceptar requisições
self.addEventListener('fetch', event => {
    const { request } = event;
    
    // Só lidar com requisições HTTP/HTTPS
    if (!request.url.startsWith('http')) return;
    
    // Estratégia de cache
    if (request.method === 'GET') {
        event.respondWith(
            caches.match(request)
                .then(response => {
                    // Se encontrou no cache, retorna
                    if (response) {
                        console.log('📋 Cache HIT:', request.url);
                        return response;
                    }
                    
                    // Se não encontrou, busca na rede
                    return fetch(request)
                        .then(response => {
                            // Se a resposta é válida, adiciona ao cache
                            if (response.status === 200) {
                                const responseClone = response.clone();
                                caches.open(CACHE_NAME)
                                    .then(cache => {
                                        cache.put(request, responseClone);
                                    });
                            }
                            return response;
                        })
                        .catch(() => {
                            // Se não conseguiu buscar na rede, mostra página offline
                            console.log('🔌 Offline:', request.url);
                            return caches.match(OFFLINE_URL);
                        });
                })
        );
    }
});

// Sync em background
self.addEventListener('sync', event => {
    console.log('🔄 Background Sync:', event.tag);
    
    if (event.tag === 'sync-tickets') {
        event.waitUntil(syncTickets());
    }
    
    if (event.tag === 'sync-messages') {
        event.waitUntil(syncChatMessages());
    }
});

// Push notifications
self.addEventListener('push', event => {
    console.log('📬 Push recebido:', event.data?.text());
    
    if (event.data) {
        const data = event.data.json();
        const options = {
            body: data.message,
            icon: '/static/img/icons/icon-192x192.png',
            badge: '/static/img/icons/icon-96x96.png',
            vibrate: [200, 100, 200],
            data: {
                dateOfArrival: Date.now(),
                primaryKey: data.id,
                url: data.url || '/mobile/'
            },
            actions: [
                {
                    action: 'explore',
                    title: 'Ver Detalhes',
                    icon: '/static/img/icons/view.png'
                },
                {
                    action: 'close',
                    title: 'Fechar',
                    icon: '/static/img/icons/close.png'
                }
            ],
            requireInteraction: true,
            tag: 'iconnect-notification'
        };
        
        event.waitUntil(
            self.registration.showNotification(data.title || 'iConnect', options)
        );
    }
});

// Click em notificações
self.addEventListener('notificationclick', event => {
    console.log('🖱️ Notificação clicada:', event.action);
    
    event.notification.close();
    
    if (event.action === 'explore') {
        // Abrir URL específica
        const url = event.notification.data.url || '/mobile/';
        event.waitUntil(
            clients.openWindow(url)
        );
    } else if (event.action === 'close') {
        // Apenas fechar
        return;
    } else {
        // Click padrão na notificação
        event.waitUntil(
            clients.openWindow('/mobile/')
        );
    }
});

// Funções auxiliares
async function syncTickets() {
    try {
        console.log('🔄 Sincronizando tickets...');
        
        // Buscar tickets pendentes no IndexedDB
        const pendingTickets = await getPendingTickets();
        
        for (const ticket of pendingTickets) {
            try {
                const response = await fetch('/api/tickets/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Token ${ticket.token}`
                    },
                    body: JSON.stringify(ticket.data)
                });
                
                if (response.ok) {
                    await removePendingTicket(ticket.id);
                    console.log('✅ Ticket sincronizado:', ticket.id);
                }
            } catch (error) {
                console.log('❌ Erro ao sincronizar ticket:', error);
            }
        }
    } catch (error) {
        console.log('❌ Erro na sincronização:', error);
    }
}

async function syncChatMessages() {
    try {
        console.log('🔄 Sincronizando mensagens...');
        
        const pendingMessages = await getPendingMessages();
        
        for (const message of pendingMessages) {
            try {
                const response = await fetch('/api/chatbot/response/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Token ${message.token}`
                    },
                    body: JSON.stringify(message.data)
                });
                
                if (response.ok) {
                    await removePendingMessage(message.id);
                    console.log('✅ Mensagem sincronizada:', message.id);
                }
            } catch (error) {
                console.log('❌ Erro ao sincronizar mensagem:', error);
            }
        }
    } catch (error) {
        console.log('❌ Erro na sincronização de mensagens:', error);
    }
}

// Placeholder functions para IndexedDB
async function getPendingTickets() {
    // TODO: Implementar IndexedDB
    return [];
}

async function removePendingTicket(id) {
    // TODO: Implementar IndexedDB
    return true;
}

async function getPendingMessages() {
    // TODO: Implementar IndexedDB
    return [];
}

async function removePendingMessage(id) {
    // TODO: Implementar IndexedDB
    return true;
}
