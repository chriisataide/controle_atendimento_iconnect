// Service Worker para iConnect PWA
// Versão do cache para forçar atualizações
const CACHE_NAME = 'iconnect-v1.0.0';
const STATIC_CACHE = 'iconnect-static-v1.0.0';
const DYNAMIC_CACHE = 'iconnect-dynamic-v1.0.0';

// URLs para cache offline
const STATIC_URLS = [
  '/',
  '/dashboard/',
  '/dashboard/tickets/',
  '/dashboard/tickets/novo/',
  '/dashboard/profile/',
  '/static/css/material-dashboard.min.css',
  '/static/js/core/bootstrap.bundle.min.js',
  '/static/img/icodev-logo.png',
  '/static/img/icodev-favicon.ico',
  'https://fonts.googleapis.com/css2?family=Inter:300,400,500,600,700,900',
  'https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0',
  'https://cdn.jsdelivr.net/npm/chart.js',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css'
];

// Páginas offline fallback
const OFFLINE_PAGE = '/offline/';

// Install event - cache recursos estáticos
self.addEventListener('install', event => {
  console.log('🚀 Service Worker instalando...');
  
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => {
        console.log('📦 Cache estático criado');
        return cache.addAll(STATIC_URLS.map(url => new Request(url, {credentials: 'same-origin'})));
      })
      .then(() => {
        console.log('✅ Recursos estáticos cacheados');
        return self.skipWaiting();
      })
      .catch(error => {
        console.error('❌ Erro ao cachear recursos:', error);
      })
  );
});

// Activate event - limpeza de caches antigos
self.addEventListener('activate', event => {
  console.log('🔄 Service Worker ativando...');
  
  event.waitUntil(
    caches.keys()
      .then(cacheNames => {
        return Promise.all(
          cacheNames.map(cacheName => {
            if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
              console.log('🗑️ Removendo cache antigo:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        console.log('✅ Service Worker ativo');
        return self.clients.claim();
      })
  );
});

// Fetch event - estratégia de cache
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  
  // Ignorar requisições não-HTTP
  if (!request.url.startsWith('http')) return;
  
  // Estratégia para diferentes tipos de recursos
  if (request.method === 'GET') {
    // Recursos estáticos - Cache First
    if (isStaticResource(request)) {
      event.respondWith(cacheFirstStrategy(request));
    }
    // APIs - Network First
    else if (isApiRequest(request)) {
      event.respondWith(networkFirstStrategy(request));
    }
    // Páginas - Stale While Revalidate
    else if (isPageRequest(request)) {
      event.respondWith(staleWhileRevalidateStrategy(request));
    }
    // Outros recursos - Network First com fallback
    else {
      event.respondWith(networkWithFallbackStrategy(request));
    }
  }
});

// Estratégia Cache First (para recursos estáticos)
async function cacheFirstStrategy(request) {
  try {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    const networkResponse = await fetch(request);
    const cache = await caches.open(STATIC_CACHE);
    cache.put(request, networkResponse.clone());
    return networkResponse;
  } catch (error) {
    console.error('Cache First falhou:', error);
    return new Response('Offline', { status: 503 });
  }
}

// Estratégia Network First (para APIs)
async function networkFirstStrategy(request) {
  try {
    const networkResponse = await fetch(request);
    
    // Cache apenas respostas OK
    if (networkResponse.ok) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.log('Network falhou, tentando cache:', request.url);
    const cachedResponse = await caches.match(request);
    
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Fallback para APIs
    return new Response(JSON.stringify({
      error: 'Offline',
      message: 'Você está offline. Verifique sua conexão.'
    }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

// Estratégia Stale While Revalidate (para páginas)
async function staleWhileRevalidateStrategy(request) {
  const cache = await caches.open(DYNAMIC_CACHE);
  const cachedResponse = await cache.match(request);
  
  const fetchPromise = fetch(request).then(networkResponse => {
    cache.put(request, networkResponse.clone());
    return networkResponse;
  }).catch(() => {
    // Se network falhar e não tiver cache, mostrar página offline
    if (!cachedResponse) {
      return caches.match(OFFLINE_PAGE);
    }
  });
  
  return cachedResponse || fetchPromise;
}

// Estratégia Network with Fallback
async function networkWithFallbackStrategy(request) {
  try {
    const networkResponse = await fetch(request);
    return networkResponse;
  } catch (error) {
    const cachedResponse = await caches.match(request);
    return cachedResponse || caches.match(OFFLINE_PAGE);
  }
}

// Utilitários para classificar requisições
function isStaticResource(request) {
  const url = new URL(request.url);
  return url.pathname.includes('/static/') ||
         url.pathname.includes('.css') ||
         url.pathname.includes('.js') ||
         url.pathname.includes('.png') ||
         url.pathname.includes('.jpg') ||
         url.pathname.includes('.svg') ||
         url.pathname.includes('.woff') ||
         url.hostname.includes('fonts.googleapis.com') ||
         url.hostname.includes('fonts.gstatic.com') ||
         url.hostname.includes('cdn.jsdelivr.net');
}

function isApiRequest(request) {
  const url = new URL(request.url);
  return url.pathname.includes('/api/') || 
         url.pathname.includes('/ajax/') ||
         request.headers.get('Accept')?.includes('application/json');
}

function isPageRequest(request) {
  return request.destination === 'document';
}

// Push Notifications
self.addEventListener('push', event => {
  console.log('📬 Push notification recebida');
  
  if (!event.data) return;
  
  const data = event.data.json();
  const options = {
    body: data.body,
    icon: '/static/img/icons/icon-192x192.png',
    badge: '/static/img/icons/badge-72x72.png',
    image: data.image,
    vibrate: [200, 100, 200],
    tag: data.tag || 'iconnect-notification',
    renotify: true,
    requireInteraction: true,
    actions: [
      {
        action: 'view',
        title: '👀 Ver',
        icon: '/static/img/icons/action-view.png'
      },
      {
        action: 'dismiss',
        title: '❌ Dispensar',
        icon: '/static/img/icons/action-dismiss.png'
      }
    ],
    data: {
      url: data.url || '/',
      ticketId: data.ticketId
    }
  };
  
  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Clique em notificação
self.addEventListener('notificationclick', event => {
  console.log('🖱️ Clique em notificação:', event.action);
  
  event.notification.close();
  
  if (event.action === 'dismiss') {
    return;
  }
  
  const urlToOpen = event.notification.data.url || '/';
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then(clientList => {
        // Tentar focar em uma aba existente
        for (const client of clientList) {
          if (client.url.includes(urlToOpen) && 'focus' in client) {
            return client.focus();
          }
        }
        
        // Se não encontrar, abrir nova aba
        if (clients.openWindow) {
          return clients.openWindow(urlToOpen);
        }
      })
  );
});

// Background Sync para sincronizar dados offline
self.addEventListener('sync', event => {
  console.log('🔄 Background sync:', event.tag);
  
  if (event.tag === 'sync-tickets') {
    event.waitUntil(syncTickets());
  }
  
  if (event.tag === 'sync-interactions') {
    event.waitUntil(syncInteractions());
  }
});

// Sincronizar tickets criados offline
async function syncTickets() {
  try {
    // Buscar tickets pendentes no IndexedDB
    const pendingTickets = await getItemsFromIndexedDB('pending-tickets');
    
    for (const ticket of pendingTickets) {
      try {
        const response = await fetch('/api/tickets/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': ticket.csrfToken
          },
          body: JSON.stringify(ticket.data)
        });
        
        if (response.ok) {
          await removeFromIndexedDB('pending-tickets', ticket.id);
          console.log('✅ Ticket sincronizado:', ticket.id);
        }
      } catch (error) {
        console.error('❌ Erro ao sincronizar ticket:', error);
      }
    }
  } catch (error) {
    console.error('❌ Erro no sync de tickets:', error);
  }
}

// Sincronizar interações criadas offline
async function syncInteractions() {
  try {
    const pendingInteractions = await getItemsFromIndexedDB('pending-interactions');
    
    for (const interaction of pendingInteractions) {
      try {
        const response = await fetch(`/api/tickets/${interaction.ticketId}/interactions/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': interaction.csrfToken
          },
          body: JSON.stringify(interaction.data)
        });
        
        if (response.ok) {
          await removeFromIndexedDB('pending-interactions', interaction.id);
          console.log('✅ Interação sincronizada:', interaction.id);
        }
      } catch (error) {
        console.error('❌ Erro ao sincronizar interação:', error);
      }
    }
  } catch (error) {
    console.error('❌ Erro no sync de interações:', error);
  }
}

// Utilitários para IndexedDB (implementação simplificada)
async function getItemsFromIndexedDB(storeName) {
  // Implementação simplificada - na prática usaria IndexedDB API
  return [];
}

async function removeFromIndexedDB(storeName, id) {
  // Implementação simplificada
  return true;
}

// Cleanup periódico do cache
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'CLEANUP_CACHE') {
    event.waitUntil(cleanupCache());
  }
});

async function cleanupCache() {
  const cache = await caches.open(DYNAMIC_CACHE);
  const keys = await cache.keys();
  
  // Remove entradas antigas (mais de 1 dia)
  const oneDayAgo = Date.now() - (24 * 60 * 60 * 1000);
  
  for (const request of keys) {
    const response = await cache.match(request);
    const dateHeader = response?.headers.get('date');
    
    if (dateHeader && new Date(dateHeader).getTime() < oneDayAgo) {
      await cache.delete(request);
    }
  }
  
  console.log('🧹 Cache limpo');
}
