// Sistema de Cache Inteligente - iConnect PWA
// Gerencia cache offline e sincronização de dados

class CacheManager {
    constructor() {
        this.cacheName = 'iconnect-cache-v1.0.0';
        this.apiCacheName = 'iconnect-api-cache-v1.0.0';
        this.maxCacheAge = 24 * 60 * 60 * 1000; // 24 horas
        this.maxApiCacheAge = 5 * 60 * 1000; // 5 minutos para APIs
        
        this.init();
    }

    async init() {
        try {
            await this.setupCache();
            await this.cleanupOldCache();
            this.setupCacheStrategies();
            
            console.log('Cache Manager inicializado');
        } catch (error) {
            console.error('Erro ao inicializar Cache Manager:', error);
        }
    }

    async setupCache() {
        if (!('caches' in window)) {
            console.warn('Cache API não suportada');
            return;
        }

        // Recursos essenciais para cache
        const staticResources = [
            '/static/css/material-dashboard.min.css',
            '/static/css/mobile.css',
            '/static/js/material-dashboard.min.js',
            '/static/js/mobile.js',
            '/static/js/push-notifications.js',
            '/static/img/logo-ct.png',
            '/static/img/favicon.png',
            '/static/manifest.json'
        ];

        try {
            const cache = await caches.open(this.cacheName);
            await cache.addAll(staticResources);
            console.log('Recursos estáticos cacheados');
        } catch (error) {
            console.error('Erro ao cachear recursos estáticos:', error);
        }
    }

    async cleanupOldCache() {
        const cacheNames = await caches.keys();
        const oldCaches = cacheNames.filter(name => 
            name.startsWith('iconnect-') && 
            name !== this.cacheName && 
            name !== this.apiCacheName
        );

        await Promise.all(
            oldCaches.map(cacheName => caches.delete(cacheName))
        );

        if (oldCaches.length > 0) {
            console.log(`Removidos ${oldCaches.length} caches antigos`);
        }
    }

    setupCacheStrategies() {
        // Intercepta requisições para aplicar estratégias de cache
        if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
            navigator.serviceWorker.addEventListener('message', (event) => {
                if (event.data.type === 'CACHE_UPDATED') {
                    console.log('Cache atualizado:', event.data.url);
                    this.notifyCacheUpdate(event.data.url);
                }
            });
        }
    }

    // Estratégias de Cache

    async cacheFirst(request) {
        const cachedResponse = await caches.match(request);
        
        if (cachedResponse) {
            // Verifica se o cache não está muito antigo
            const cacheDate = cachedResponse.headers.get('cached-date');
            if (cacheDate) {
                const age = Date.now() - new Date(cacheDate).getTime();
                if (age < this.maxCacheAge) {
                    return cachedResponse;
                }
            }
        }

        try {
            const networkResponse = await fetch(request);
            await this.updateCache(request, networkResponse.clone());
            return networkResponse;
        } catch (error) {
            return cachedResponse || this.createErrorResponse();
        }
    }

    async networkFirst(request) {
        try {
            const networkResponse = await fetch(request);
            await this.updateCache(request, networkResponse.clone());
            return networkResponse;
        } catch (error) {
            const cachedResponse = await caches.match(request);
            return cachedResponse || this.createErrorResponse();
        }
    }

    async staleWhileRevalidate(request) {
        const cachedResponse = await caches.match(request);
        
        const fetchPromise = fetch(request).then(networkResponse => {
            this.updateCache(request, networkResponse.clone());
            return networkResponse;
        }).catch(() => cachedResponse);

        return cachedResponse || fetchPromise;
    }

    // Gerenciamento de Cache de Dados

    async cacheApiResponse(url, data, maxAge = this.maxApiCacheAge) {
        const cache = await caches.open(this.apiCacheName);
        const response = new Response(JSON.stringify(data), {
            headers: {
                'Content-Type': 'application/json',
                'cached-date': new Date().toISOString(),
                'max-age': maxAge.toString()
            }
        });
        
        await cache.put(url, response);
    }

    async getCachedApiResponse(url) {
        const cache = await caches.open(this.apiCacheName);
        const cachedResponse = await cache.match(url);
        
        if (!cachedResponse) return null;

        const cacheDate = cachedResponse.headers.get('cached-date');
        const maxAge = parseInt(cachedResponse.headers.get('max-age')) || this.maxApiCacheAge;
        
        if (cacheDate) {
            const age = Date.now() - new Date(cacheDate).getTime();
            if (age > maxAge) {
                await cache.delete(url);
                return null;
            }
        }

        return await cachedResponse.json();
    }

    // Cache de Dados Específicos

    async cacheTickets(tickets) {
        const url = '/api/tickets/cached';
        await this.cacheApiResponse(url, tickets, 2 * 60 * 1000); // 2 minutos
        
        // Cache individual de cada ticket
        for (const ticket of tickets) {
            await this.cacheApiResponse(
                `/api/tickets/${ticket.id}/cached`, 
                ticket, 
                5 * 60 * 1000 // 5 minutos
            );
        }
    }

    async getCachedTickets() {
        return await this.getCachedApiResponse('/api/tickets/cached');
    }

    async getCachedTicket(ticketId) {
        return await this.getCachedApiResponse(`/api/tickets/${ticketId}/cached`);
    }

    async cacheChatMessages(roomId, messages) {
        const url = `/api/chat/${roomId}/messages/cached`;
        await this.cacheApiResponse(url, messages, 1 * 60 * 1000); // 1 minuto
    }

    async getCachedChatMessages(roomId) {
        return await this.getCachedApiResponse(`/api/chat/${roomId}/messages/cached`);
    }

    async cacheDashboardStats(stats) {
        const url = '/api/dashboard/stats/cached';
        await this.cacheApiResponse(url, stats, 5 * 60 * 1000); // 5 minutos
    }

    async getCachedDashboardStats() {
        return await this.getCachedApiResponse('/api/dashboard/stats/cached');
    }

    // Sincronização Offline

    async queueOfflineAction(action) {
        const offlineQueue = await this.getOfflineQueue();
        offlineQueue.push({
            id: this.generateId(),
            timestamp: Date.now(),
            ...action
        });
        
        localStorage.setItem('offlineQueue', JSON.stringify(offlineQueue));
        console.log('Ação enfileirada para sincronização:', action.type);
    }

    async getOfflineQueue() {
        const stored = localStorage.getItem('offlineQueue');
        return stored ? JSON.parse(stored) : [];
    }

    async processOfflineQueue() {
        if (!navigator.onLine) {
            console.log('Offline - aguardando conexão para sincronizar');
            return;
        }

        const queue = await this.getOfflineQueue();
        if (queue.length === 0) return;

        console.log(`Processando ${queue.length} ações offline`);
        
        const processed = [];
        const failed = [];

        for (const action of queue) {
            try {
                await this.processOfflineAction(action);
                processed.push(action.id);
                console.log('Ação sincronizada:', action.type);
            } catch (error) {
                console.error('Erro ao sincronizar ação:', error);
                failed.push(action);
            }
        }

        // Remove ações processadas
        const remainingQueue = queue.filter(action => 
            !processed.includes(action.id)
        );
        
        localStorage.setItem('offlineQueue', JSON.stringify(remainingQueue));
        
        if (processed.length > 0) {
            this.showSyncNotification(processed.length, failed.length);
        }
    }

    async processOfflineAction(action) {
        switch (action.type) {
            case 'create_ticket':
                return await this.syncCreateTicket(action.data);
            case 'update_ticket':
                return await this.syncUpdateTicket(action.data);
            case 'send_message':
                return await this.syncSendMessage(action.data);
            case 'update_profile':
                return await this.syncUpdateProfile(action.data);
            default:
                throw new Error(`Tipo de ação desconhecido: ${action.type}`);
        }
    }

    async syncCreateTicket(data) {
        const response = await fetch('/dashboard/tickets/novo/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            throw new Error('Erro ao criar ticket');
        }

        return await response.json();
    }

    async syncUpdateTicket(data) {
        const response = await fetch(`/dashboard/tickets/${data.id}/`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            throw new Error('Erro ao atualizar ticket');
        }

        return await response.json();
    }

    async syncSendMessage(data) {
        const response = await fetch(`/dashboard/api/chat/${data.roomId}/send/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            throw new Error('Erro ao enviar mensagem');
        }

        return await response.json();
    }

    async syncUpdateProfile(data) {
        const response = await fetch('/dashboard/profile/', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            throw new Error('Erro ao atualizar perfil');
        }

        return await response.json();
    }

    // Utilitários

    async updateCache(request, response) {
        const cache = await caches.open(this.cacheName);
        
        // Adiciona header de data de cache
        const responseToCache = new Response(response.body, {
            status: response.status,
            statusText: response.statusText,
            headers: {
                ...Object.fromEntries(response.headers.entries()),
                'cached-date': new Date().toISOString()
            }
        });

        await cache.put(request, responseToCache);
    }

    createErrorResponse() {
        return new Response(
            JSON.stringify({
                error: 'Conteúdo não disponível offline',
                offline: true
            }),
            {
                status: 503,
                headers: { 'Content-Type': 'application/json' }
            }
        );
    }

    notifyCacheUpdate(url) {
        // Emite evento para outros componentes
        document.dispatchEvent(new CustomEvent('cacheUpdated', {
            detail: { url }
        }));
    }

    showSyncNotification(processed, failed) {
        const message = failed > 0 
            ? `${processed} ações sincronizadas, ${failed} falharam`
            : `${processed} ações sincronizadas com sucesso`;
        
        if (window.mobileManager) {
            window.mobileManager.showToast(message, failed > 0 ? 'warning' : 'success');
        }
    }

    generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }

    getCSRFToken() {
        const tokenElement = document.querySelector('[name=csrfmiddlewaretoken]');
        if (tokenElement) {
            return tokenElement.value;
        }
        
        const cookie = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='));
        
        return cookie ? cookie.split('=')[1] : '';
    }

    // API Pública

    async preloadData() {
        // Pré-carrega dados importantes quando online
        if (!navigator.onLine) return;

        try {
            // Dashboard stats
            const statsResponse = await fetch('/dashboard/api/stats/');
            if (statsResponse.ok) {
                const stats = await statsResponse.json();
                await this.cacheDashboardStats(stats);
            }

            // Recent tickets
            const ticketsResponse = await fetch('/dashboard/api/tickets/recent/');
            if (ticketsResponse.ok) {
                const tickets = await ticketsResponse.json();
                await this.cacheTickets(tickets);
            }

            console.log('Dados pré-carregados no cache');
        } catch (error) {
            console.error('Erro ao pré-carregar dados:', error);
        }
    }

    async clearCache() {
        const cacheNames = await caches.keys();
        const iconnectCaches = cacheNames.filter(name => 
            name.startsWith('iconnect-')
        );

        await Promise.all(
            iconnectCaches.map(cacheName => caches.delete(cacheName))
        );

        localStorage.removeItem('offlineQueue');
        console.log('Cache limpo');
    }

    async getCacheSize() {
        if (!('storage' in navigator) || !('estimate' in navigator.storage)) {
            return { quota: 0, usage: 0 };
        }

        const estimate = await navigator.storage.estimate();
        return {
            quota: estimate.quota,
            usage: estimate.usage,
            usageDetails: estimate.usageDetails
        };
    }

    // Getters

    get isOnline() {
        return navigator.onLine;
    }

    get hasPendingSync() {
        const queue = localStorage.getItem('offlineQueue');
        return queue ? JSON.parse(queue).length > 0 : false;
    }
}

// Integração com eventos de conectividade
class ConnectivityManager {
    constructor(cacheManager) {
        this.cacheManager = cacheManager;
        this.setupEventListeners();
    }

    setupEventListeners() {
        window.addEventListener('online', () => {
            console.log('Conexão restaurada');
            this.cacheManager.processOfflineQueue();
            this.cacheManager.preloadData();
        });

        window.addEventListener('offline', () => {
            console.log('Conectividade perdida');
        });

        // Processa fila quando página é carregada
        document.addEventListener('DOMContentLoaded', () => {
            if (navigator.onLine) {
                this.cacheManager.processOfflineQueue();
            }
        });
    }
}

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    window.cacheManager = new CacheManager();
    window.connectivityManager = new ConnectivityManager(window.cacheManager);
    
    // Registra service worker se disponível
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/js/sw.js')
            .then(registration => {
                console.log('Service Worker registrado:', registration);
            })
            .catch(error => {
                console.error('Erro ao registrar Service Worker:', error);
            });
    }
});

// Exporta para uso em outros scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { CacheManager, ConnectivityManager };
}
