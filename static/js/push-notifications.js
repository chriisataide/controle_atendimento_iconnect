// Sistema de Push Notifications para iConnect PWA
// Gerencia notificações push para tickets e mensagens de chat

class PushNotificationManager {
    constructor() {
        this.isSupported = 'serviceWorker' in navigator && 'PushManager' in window;
        this.subscription = null;
        this.publicKey = null;
        this.isSubscribed = false;
        
        this.init();
    }

    async init() {
        if (!this.isSupported) {
            console.warn('Push notifications não são suportadas neste navegador');
            return;
        }

        try {
            // Obtém a chave pública do servidor
            await this.getPublicKey();
            
            // Verifica se já está inscrito
            await this.checkSubscription();
            
            // Configura listeners
            this.setupEventListeners();
            
            console.log('Push Notification Manager inicializado');
        } catch (error) {
            console.error('Erro ao inicializar Push Notifications:', error);
        }
    }

    async getPublicKey() {
        try {
            const response = await fetch('/dashboard/api/push/public-key/');
            const data = await response.json();
            this.publicKey = data.public_key;
        } catch (error) {
            console.error('Erro ao obter chave pública:', error);
            // Fallback para chave padrão (deve ser configurada no servidor)
            this.publicKey = 'BEl62iUYgUivxIkv69yViEuiBIa40HI0u' +
                           '2Zd43v_rYgL6-xfEkUNECDqJf0pv8VFJ' +
                           'dw4aBQQ1hvGsq-cDdfqjgI';
        }
    }

    async checkSubscription() {
        if (!this.isSupported) return;

        try {
            const registration = await navigator.serviceWorker.ready;
            const subscription = await registration.pushManager.getSubscription();
            
            this.subscription = subscription;
            this.isSubscribed = !!subscription;
            
            if (subscription) {
                console.log('Usuário já inscrito para push notifications');
                // Sincroniza com o servidor
                await this.syncSubscriptionWithServer(subscription);
            }
            
            this.updateUI();
        } catch (error) {
            console.error('Erro ao verificar inscrição:', error);
        }
    }

    async requestPermission() {
        if (!this.isSupported) {
            throw new Error('Push notifications não são suportadas');
        }

        const permission = await Notification.requestPermission();
        
        if (permission === 'granted') {
            console.log('Permissão para notificações concedida');
            return true;
        } else if (permission === 'denied') {
            console.log('Permissão para notificações negada');
            throw new Error('Permissão para notificações negada');
        } else {
            console.log('Permissão para notificações não definida');
            throw new Error('Permissão para notificações não definida');
        }
    }

    async subscribe() {
        try {
            // Solicita permissão
            await this.requestPermission();

            // Obtém o service worker registration
            const registration = await navigator.serviceWorker.ready;

            // Cria a inscrição
            const subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: this.urlBase64ToUint8Array(this.publicKey)
            });

            this.subscription = subscription;
            this.isSubscribed = true;

            // Envia para o servidor
            await this.syncSubscriptionWithServer(subscription);

            console.log('Inscrito para push notifications:', subscription);
            this.updateUI();
            
            // Mostra notificação de confirmação
            this.showLocalNotification(
                'Notificações ativadas!',
                'Você receberá notificações sobre novos tickets e mensagens.'
            );

            return subscription;
        } catch (error) {
            console.error('Erro ao se inscrever:', error);
            throw error;
        }
    }

    async unsubscribe() {
        if (!this.subscription) {
            console.log('Não há inscrição ativa');
            return;
        }

        try {
            // Remove do servidor
            await this.removeSubscriptionFromServer(this.subscription);

            // Remove localmente
            await this.subscription.unsubscribe();
            
            this.subscription = null;
            this.isSubscribed = false;
            
            console.log('Desinscrição realizada com sucesso');
            this.updateUI();
            
        } catch (error) {
            console.error('Erro ao desinscrever:', error);
            throw error;
        }
    }

    async syncSubscriptionWithServer(subscription) {
        try {
            const response = await fetch('/dashboard/api/push/subscribe/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    subscription: subscription.toJSON(),
                    user_agent: navigator.userAgent,
                    preferences: this.getNotificationPreferences()
                })
            });

            if (!response.ok) {
                throw new Error('Erro ao sincronizar com servidor');
            }

            const result = await response.json();
            console.log('Inscrição sincronizada com servidor:', result);
        } catch (error) {
            console.error('Erro ao sincronizar inscrição:', error);
            throw error;
        }
    }

    async removeSubscriptionFromServer(subscription) {
        try {
            const response = await fetch('/dashboard/api/push/unsubscribe/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    subscription: subscription.toJSON()
                })
            });

            if (!response.ok) {
                throw new Error('Erro ao remover inscrição do servidor');
            }
        } catch (error) {
            console.error('Erro ao remover inscrição:', error);
            throw error;
        }
    }

    getNotificationPreferences() {
        // Obtém preferências do localStorage ou configurações padrão
        const stored = localStorage.getItem('notificationPreferences');
        return stored ? JSON.parse(stored) : {
            tickets: true,
            chat: true,
            system: true,
            quiet_hours: false,
            quiet_start: '22:00',
            quiet_end: '08:00'
        };
    }

    setNotificationPreferences(preferences) {
        localStorage.setItem('notificationPreferences', JSON.stringify(preferences));
        
        // Sincroniza com servidor se inscrito
        if (this.isSubscribed && this.subscription) {
            this.updateServerPreferences(preferences);
        }
    }

    async updateServerPreferences(preferences) {
        try {
            await fetch('/dashboard/api/push/preferences/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ preferences })
            });
        } catch (error) {
            console.error('Erro ao atualizar preferências:', error);
        }
    }

    async testNotification() {
        if (!this.isSubscribed) {
            throw new Error('Não inscrito para notificações');
        }

        try {
            const response = await fetch('/dashboard/api/push/test/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                }
            });

            if (!response.ok) {
                throw new Error('Erro ao enviar notificação de teste');
            }

            console.log('Notificação de teste enviada');
        } catch (error) {
            console.error('Erro ao testar notificação:', error);
            throw error;
        }
    }

    showLocalNotification(title, body, options = {}) {
        if (!('Notification' in window)) {
            console.log('Este navegador não suporta notificações');
            return;
        }

        if (Notification.permission === 'granted') {
            const notification = new Notification(title, {
                body,
                icon: '/static/img/logo-ct.png',
                badge: '/static/img/favicon.png',
                vibrate: [200, 100, 200],
                ...options
            });

            // Auto-fecha após 5 segundos
            setTimeout(() => {
                notification.close();
            }, 5000);

            return notification;
        }
    }

    setupEventListeners() {
        // Listener para o botão de ativar/desativar notificações
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-action="toggle-notifications"]')) {
                e.preventDefault();
                this.toggleSubscription();
            }
            
            if (e.target.matches('[data-action="test-notification"]')) {
                e.preventDefault();
                this.testNotification();
            }
        });

        // Listener para mudanças de preferências
        document.addEventListener('change', (e) => {
            if (e.target.matches('[data-notification-preference]')) {
                this.updatePreferences();
            }
        });

        // Listener para eventos de push do service worker
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.addEventListener('message', (event) => {
                if (event.data && event.data.type === 'PUSH_RECEIVED') {
                    console.log('Push notification recebida:', event.data.payload);
                    this.handlePushMessage(event.data.payload);
                }
            });
        }
    }

    async toggleSubscription() {
        try {
            if (this.isSubscribed) {
                await this.unsubscribe();
            } else {
                await this.subscribe();
            }
        } catch (error) {
            console.error('Erro ao alterar inscrição:', error);
            this.showError('Erro ao configurar notificações: ' + error.message);
        }
    }

    updatePreferences() {
        const form = document.querySelector('[data-notification-form]');
        if (!form) return;

        const formData = new FormData(form);
        const preferences = {};

        for (const [key, value] of formData.entries()) {
            if (key.startsWith('notification_')) {
                const prefKey = key.replace('notification_', '');
                preferences[prefKey] = value === 'on' || value === 'true';
            }
        }

        this.setNotificationPreferences(preferences);
    }

    handlePushMessage(payload) {
        // Atualiza UI baseado na mensagem recebida
        if (payload.type === 'new_ticket') {
            this.updateTicketCount();
        } else if (payload.type === 'chat_message') {
            this.updateChatIndicator(payload.room_id);
        }

        // Emite evento customizado para outros componentes
        document.dispatchEvent(new CustomEvent('pushNotificationReceived', {
            detail: payload
        }));
    }

    updateUI() {
        // Atualiza botões e indicadores na interface
        const toggleButton = document.querySelector('[data-action="toggle-notifications"]');
        const statusElement = document.querySelector('[data-notification-status]');

        if (toggleButton) {
            toggleButton.textContent = this.isSubscribed ? 
                'Desativar Notificações' : 'Ativar Notificações';
            toggleButton.className = this.isSubscribed ? 
                'btn btn-outline-warning' : 'btn btn-success';
        }

        if (statusElement) {
            statusElement.textContent = this.isSubscribed ? 
                'Ativadas' : 'Desativadas';
            statusElement.className = this.isSubscribed ? 
                'badge bg-success' : 'badge bg-secondary';
        }
    }

    updateTicketCount() {
        // Atualiza contador de tickets na interface
        const counter = document.querySelector('[data-ticket-counter]');
        if (counter) {
            const current = parseInt(counter.textContent) || 0;
            counter.textContent = current + 1;
            counter.classList.add('pulse-animation');
        }
    }

    updateChatIndicator(roomId) {
        // Atualiza indicador de mensagens não lidas
        const indicator = document.querySelector(`[data-chat-room="${roomId}"] .unread-indicator`);
        if (indicator) {
            indicator.style.display = 'block';
        }
    }

    showError(message) {
        // Mostra erro na interface
        const errorContainer = document.querySelector('[data-error-container]');
        if (errorContainer) {
            errorContainer.innerHTML = `
                <div class="alert alert-danger alert-dismissible fade show" role="alert">
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            `;
        } else {
            alert(message);
        }
    }

    // Utilitários
    urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding)
            .replace(/-/g, '+')
            .replace(/_/g, '/');

        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);

        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
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

    // Getters para status
    get isNotificationSupported() {
        return this.isSupported;
    }

    get notificationPermission() {
        return Notification.permission;
    }

    get subscriptionStatus() {
        return {
            supported: this.isSupported,
            permission: this.notificationPermission,
            subscribed: this.isSubscribed,
            subscription: this.subscription
        };
    }
}

// Inicializa o gerenciador quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    window.pushManager = new PushNotificationManager();
});

// Exporta para uso em outros scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PushNotificationManager;
}
