/**
 * Sistema de Notificações em Tempo Real - iConnect
 * WebSocket + UI Components
 */

class NotificationSystem {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
        this.heartbeatInterval = null;
        
        this.init();
    }
    
    init() {
        this.createNotificationContainer();
        this.setupWebSocket();
        this.setupEventListeners();
        this.startHeartbeat();
    }
    
    createNotificationContainer() {
        if (document.getElementById('notification-container')) return;
        
        const container = document.createElement('div');
        container.id = 'notification-container';
        container.className = 'notification-container';
        container.innerHTML = `
            <style>
                .notification-container {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    z-index: 9999;
                    max-width: 400px;
                }
                
                .notification-toast {
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.15);
                    margin-bottom: 10px;
                    overflow: hidden;
                    animation: slideInRight 0.3s ease;
                    position: relative;
                    border-left: 4px solid #007bff;
                }
                
                .notification-toast.success { border-left-color: #28a745; }
                .notification-toast.warning { border-left-color: #ffc107; }
                .notification-toast.error { border-left-color: #dc3545; }
                .notification-toast.info { border-left-color: #17a2b8; }
                .notification-toast.sla_warning { border-left-color: #ff9800; }
                .notification-toast.sla_breach { border-left-color: #f44336; }
                
                .notification-header {
                    padding: 15px 20px 10px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                
                .notification-title {
                    font-weight: 600;
                    font-size: 14px;
                    color: #333;
                    margin: 0;
                }
                
                .notification-close {
                    background: none;
                    border: none;
                    font-size: 18px;
                    cursor: pointer;
                    color: #999;
                    line-height: 1;
                }
                
                .notification-body {
                    padding: 0 20px 15px;
                    font-size: 13px;
                    color: #666;
                    line-height: 1.4;
                }
                
                .notification-meta {
                    padding: 10px 20px;
                    background: #f8f9fa;
                    border-top: 1px solid #e9ecef;
                    font-size: 11px;
                    color: #6c757d;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                
                .notification-actions {
                    display: flex;
                    gap: 10px;
                }
                
                .notification-btn {
                    padding: 4px 12px;
                    border: 1px solid #007bff;
                    background: white;
                    color: #007bff;
                    border-radius: 4px;
                    font-size: 11px;
                    cursor: pointer;
                    text-decoration: none;
                }
                
                .notification-btn:hover {
                    background: #007bff;
                    color: white;
                }
                
                @keyframes slideInRight {
                    from {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
                
                @keyframes fadeOut {
                    to {
                        opacity: 0;
                        transform: translateX(100%);
                    }
                }
                
                .notification-toast.removing {
                    animation: fadeOut 0.3s ease forwards;
                }
                
                /* Badge de notificação */
                .notification-badge {
                    background: #dc3545;
                    color: white;
                    border-radius: 50%;
                    padding: 2px 6px;
                    font-size: 11px;
                    min-width: 18px;
                    text-align: center;
                    animation: pulse 2s infinite;
                }
                
                .connection-indicator {
                    position: fixed;
                    bottom: 20px;
                    left: 20px;
                    padding: 8px 16px;
                    border-radius: 20px;
                    font-size: 12px;
                    font-weight: 500;
                    z-index: 9999;
                    transition: all 0.3s ease;
                }
                
                .connection-indicator.connected {
                    background: #d4edda;
                    color: #155724;
                    border: 1px solid #c3e6cb;
                }
                
                .connection-indicator.disconnected {
                    background: #f8d7da;
                    color: #721c24;
                    border: 1px solid #f5c6cb;
                }
                
                .connection-indicator.connecting {
                    background: #fff3cd;
                    color: #856404;
                    border: 1px solid #ffeaa7;
                }
            </style>
        `;
        
        document.body.appendChild(container);
        
        // Indicador de conexão
        const connectionIndicator = document.createElement('div');
        connectionIndicator.id = 'connection-indicator';
        connectionIndicator.className = 'connection-indicator connecting';
        connectionIndicator.textContent = 'Conectando...';
        document.body.appendChild(connectionIndicator);
    }
    
    setupWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/notifications/`;
        
        try {
            this.socket = new WebSocket(wsUrl);
            
            this.socket.onopen = () => {
                console.log('✅ WebSocket conectado');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.updateConnectionStatus('connected');
            };
            
            this.socket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            };
            
            this.socket.onclose = (event) => {
                console.log('❌ WebSocket desconectado:', event.code);
                this.isConnected = false;
                this.updateConnectionStatus('disconnected');
                this.handleReconnect();
            };
            
            this.socket.onerror = (error) => {
                console.error('❌ Erro no WebSocket:', error);
                this.updateConnectionStatus('disconnected');
            };
            
        } catch (error) {
            console.error('❌ Erro ao criar WebSocket:', error);
            this.updateConnectionStatus('disconnected');
        }
    }
    
    handleMessage(data) {
        switch (data.type) {
            case 'notification':
                this.showNotification(data.data);
                this.updateNotificationBadge();
                break;
                
            case 'sla_alert':
                this.showSLAAlert(data.data);
                break;
                
            case 'pong':
                // Heartbeat response
                break;
                
            default:
                console.log('Mensagem WebSocket não reconhecida:', data);
        }
    }
    
    showNotification(notification) {
        const container = document.getElementById('notification-container');
        const toast = document.createElement('div');
        toast.className = `notification-toast ${notification.type || 'info'}`;
        toast.id = `notification-${notification.id || Date.now()}`;
        
        const ticketAction = notification.ticket_id ? 
            `<a href="/dashboard/tickets/${notification.ticket_id}/" class="notification-btn">Ver Ticket</a>` : '';
        
        toast.innerHTML = `
            <div class="notification-header">
                <h5 class="notification-title">${notification.title}</h5>
                <button class="notification-close" onclick="notificationSystem.closeNotification('${toast.id}')">&times;</button>
            </div>
            <div class="notification-body">
                ${notification.message}
            </div>
            <div class="notification-meta">
                <span>${this.formatTime(notification.timestamp || new Date().toISOString())}</span>
                <div class="notification-actions">
                    ${ticketAction}
                    <button class="notification-btn" onclick="notificationSystem.markAsRead('${notification.id}')">Marcar como lida</button>
                </div>
            </div>
        `;
        
        container.appendChild(toast);
        
        // Auto-remove após 10 segundos para notificações normais
        if (!notification.priority || notification.priority !== 'critical') {
            setTimeout(() => {
                this.closeNotification(toast.id);
            }, 10000);
        }
        
        // Som de notificação
        this.playNotificationSound(notification.type);
        
        // Vibração (mobile)
        if ('vibrate' in navigator) {
            navigator.vibrate([100, 50, 100]);
        }
    }
    
    showSLAAlert(alert) {
        // SLA alerts são mais proeminentes
        const container = document.getElementById('notification-container');
        const toast = document.createElement('div');
        toast.className = `notification-toast ${alert.type}`;
        toast.id = `sla-alert-${alert.ticket_id}`;
        
        toast.innerHTML = `
            <div class="notification-header">
                <h5 class="notification-title">${alert.title}</h5>
                <button class="notification-close" onclick="notificationSystem.closeNotification('${toast.id}')">&times;</button>
            </div>
            <div class="notification-body">
                ${alert.message}
                ${alert.time_remaining ? `<br><strong>Tempo restante: ${alert.time_remaining}</strong>` : ''}
                ${alert.overdue_time ? `<br><strong>Atrasado: ${alert.overdue_time}</strong>` : ''}
            </div>
            <div class="notification-meta">
                <span>ALERTA SLA</span>
                <div class="notification-actions">
                    <a href="/dashboard/tickets/${alert.ticket_id}/" class="notification-btn">Atender Agora</a>
                </div>
            </div>
        `;
        
        container.appendChild(toast);
        
        // SLA críticos não se removem automaticamente
        this.playNotificationSound('sla_breach');
    }
    
    closeNotification(notificationId) {
        const toast = document.getElementById(notificationId);
        if (toast) {
            toast.classList.add('removing');
            setTimeout(() => {
                toast.remove();
            }, 300);
        }
    }
    
    markAsRead(notificationId) {
        if (this.isConnected && notificationId) {
            this.socket.send(JSON.stringify({
                type: 'mark_read',
                notification_id: notificationId
            }));
        }
    }
    
    updateNotificationBadge() {
        const badge = document.querySelector('.notification-badge');
        if (badge) {
            const currentCount = parseInt(badge.textContent) || 0;
            badge.textContent = currentCount + 1;
            badge.style.display = 'inline-block';
        }
    }
    
    updateConnectionStatus(status) {
        const indicator = document.getElementById('connection-indicator');
        if (indicator) {
            indicator.className = `connection-indicator ${status}`;
            
            switch (status) {
                case 'connected':
                    indicator.textContent = '🟢 Conectado';
                    setTimeout(() => {
                        indicator.style.opacity = '0';
                    }, 3000);
                    break;
                case 'disconnected':
                    indicator.textContent = '🔴 Desconectado';
                    indicator.style.opacity = '1';
                    break;
                case 'connecting':
                    indicator.textContent = '🟡 Reconectando...';
                    indicator.style.opacity = '1';
                    break;
            }
        }
    }
    
    handleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('❌ Máximo de tentativas de reconexão atingido');
            return;
        }
        
        this.updateConnectionStatus('connecting');
        this.reconnectAttempts++;
        
        setTimeout(() => {
            console.log(`🔄 Tentativa de reconexão ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
            this.setupWebSocket();
        }, this.reconnectDelay * this.reconnectAttempts);
    }
    
    startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            if (this.isConnected) {
                this.socket.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000); // 30 segundos
    }
    
    playNotificationSound(type) {
        // Sons diferentes para tipos diferentes
        const sounds = {
            'new_ticket': '/static/sounds/new-ticket.mp3',
            'sla_warning': '/static/sounds/warning.mp3', 
            'sla_breach': '/static/sounds/alert.mp3',
            'new_message': '/static/sounds/message.mp3'
        };
        
        const soundFile = sounds[type] || '/static/sounds/notification.mp3';
        
        try {
            const audio = new Audio(soundFile);
            audio.volume = 0.5;
            audio.play().catch(e => {
                // Ignore errors - sound might not be available
                console.log('Som não pôde ser reproduzido:', e);
            });
        } catch (e) {
            // Ignore audio errors
        }
    }
    
    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) return 'Agora mesmo';
        if (diff < 3600000) return `${Math.floor(diff/60000)}min atrás`;
        if (diff < 86400000) return `${Math.floor(diff/3600000)}h atrás`;
        
        return date.toLocaleDateString('pt-BR') + ' ' + date.toLocaleTimeString('pt-BR', {
            hour: '2-digit',
            minute: '2-digit'
        });
    }
    
    setupEventListeners() {
        // Detectar quando a página fica visível/oculta
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible' && !this.isConnected) {
                this.setupWebSocket();
            }
        });
        
        // Detectar reconexão de rede
        window.addEventListener('online', () => {
            console.log('🌐 Rede reconectada');
            this.setupWebSocket();
        });
        
        window.addEventListener('offline', () => {
            console.log('🌐 Rede desconectada');
            this.updateConnectionStatus('disconnected');
        });
    }
    
    // Métodos públicos
    sendAgentStatus(status) {
        if (this.isConnected) {
            this.socket.send(JSON.stringify({
                type: 'agent_status',
                status: status
            }));
        }
    }
    
    destroy() {
        if (this.socket) {
            this.socket.close();
        }
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
        }
    }
}

// Inicializar sistema quando DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    // Verificar se usuário está logado
    if (document.querySelector('[data-user-authenticated]') || 
        document.body.classList.contains('authenticated')) {
        
        console.log('🚀 Inicializando Sistema de Notificações');
        window.notificationSystem = new NotificationSystem();
    }
});

// Limpar ao sair da página
window.addEventListener('beforeunload', function() {
    if (window.notificationSystem) {
        window.notificationSystem.destroy();
    }
});
