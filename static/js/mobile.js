// PWA Mobile Functionality - iConnect
// Funcionalidades específicas para dispositivos móveis e PWA

class MobileManager {
    constructor() {
        this.isTouch = 'ontouchstart' in window;
        this.isStandalone = window.matchMedia('(display-mode: standalone)').matches;
        this.isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
        this.isAndroid = /Android/.test(navigator.userAgent);
        
        this.init();
    }

    init() {
        this.setupMobileNavigation();
        this.setupTouchGestures();
        this.setupPullToRefresh();
        this.setupOfflineHandling();
        this.setupInstallPrompt();
        this.setupKeyboardHandling();
        this.setupOrientationHandling();
        
        console.log('Mobile Manager inicializado');
    }

    setupMobileNavigation() {
        // Toggle sidebar
        document.addEventListener('click', (e) => {
            if (e.target.matches('.menu-toggle, .menu-toggle *')) {
                e.preventDefault();
                this.toggleSidebar();
            }
            
            // Fecha sidebar quando clica fora
            if (e.target.matches('.sidebar-overlay')) {
                this.closeSidebar();
            }
        });

        // Fecha sidebar em mudança de rota
        window.addEventListener('popstate', () => {
            this.closeSidebar();
        });
    }

    toggleSidebar() {
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.querySelector('.sidebar-overlay');
        
        if (!sidebar) return;
        
        if (sidebar.classList.contains('active')) {
            this.closeSidebar();
        } else {
            this.openSidebar();
        }
    }

    openSidebar() {
        const sidebar = document.querySelector('.sidebar');
        let overlay = document.querySelector('.sidebar-overlay');
        
        if (!sidebar) return;
        
        // Cria overlay se não existir
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'sidebar-overlay';
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.5);
                z-index: 1040;
                opacity: 0;
                transition: opacity 0.3s ease;
            `;
            document.body.appendChild(overlay);
        }
        
        sidebar.classList.add('active');
        overlay.style.display = 'block';
        
        // Fade in overlay
        requestAnimationFrame(() => {
            overlay.style.opacity = '1';
        });
        
        // Previne scroll do body
        document.body.style.overflow = 'hidden';
    }

    closeSidebar() {
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.querySelector('.sidebar-overlay');
        
        if (!sidebar) return;
        
        sidebar.classList.remove('active');
        
        if (overlay) {
            overlay.style.opacity = '0';
            setTimeout(() => {
                overlay.style.display = 'none';
            }, 300);
        }
        
        // Restaura scroll do body
        document.body.style.overflow = '';
    }

    setupTouchGestures() {
        // Swipe gestures para cards
        this.setupSwipeActions();
        
        // Long press simulation
        this.setupLongPress();
        
        // Touch feedback
        this.setupTouchFeedback();
    }

    setupSwipeActions() {
        let startX, startY, currentX, currentY;
        let isSwipe = false;
        let swipeTarget = null;

        document.addEventListener('touchstart', (e) => {
            const swipeContainer = e.target.closest('.swipe-container');
            if (!swipeContainer) return;

            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
            swipeTarget = swipeContainer;
            isSwipe = false;
        }, { passive: true });

        document.addEventListener('touchmove', (e) => {
            if (!swipeTarget) return;

            currentX = e.touches[0].clientX;
            currentY = e.touches[0].clientY;

            const deltaX = startX - currentX;
            const deltaY = Math.abs(startY - currentY);

            // Só considera swipe se movimento horizontal > vertical
            if (Math.abs(deltaX) > deltaY && Math.abs(deltaX) > 50) {
                isSwipe = true;
                
                if (deltaX > 0) {
                    // Swipe left - show actions
                    swipeTarget.classList.add('swiped');
                } else {
                    // Swipe right - hide actions
                    swipeTarget.classList.remove('swiped');
                }
            }
        }, { passive: true });

        document.addEventListener('touchend', () => {
            if (swipeTarget && !isSwipe) {
                swipeTarget.classList.remove('swiped');
            }
            swipeTarget = null;
            isSwipe = false;
        }, { passive: true });
    }

    setupLongPress() {
        let pressTimer = null;

        document.addEventListener('touchstart', (e) => {
            const longPressTarget = e.target.closest('[data-long-press]');
            if (!longPressTarget) return;

            pressTimer = setTimeout(() => {
                const event = new CustomEvent('longpress', {
                    detail: { target: longPressTarget }
                });
                longPressTarget.dispatchEvent(event);
                
                // Vibração se disponível
                if (navigator.vibrate) {
                    navigator.vibrate(50);
                }
            }, 500);
        });

        document.addEventListener('touchend', () => {
            if (pressTimer) {
                clearTimeout(pressTimer);
                pressTimer = null;
            }
        });

        document.addEventListener('touchmove', () => {
            if (pressTimer) {
                clearTimeout(pressTimer);
                pressTimer = null;
            }
        });
    }

    setupTouchFeedback() {
        // Adiciona classe de feedback visual em touch
        document.addEventListener('touchstart', (e) => {
            const button = e.target.closest('.btn, .nav-link, .card, [role="button"]');
            if (button) {
                button.classList.add('touch-active');
            }
        });

        document.addEventListener('touchend', () => {
            document.querySelectorAll('.touch-active').forEach(el => {
                el.classList.remove('touch-active');
            });
        });
    }

    setupPullToRefresh() {
        let startY = 0;
        let currentY = 0;
        let isPulling = false;
        
        const pullContainer = document.querySelector('.pull-to-refresh');
        if (!pullContainer) return;

        pullContainer.addEventListener('touchstart', (e) => {
            if (pullContainer.scrollTop === 0) {
                startY = e.touches[0].clientY;
            }
        }, { passive: true });

        pullContainer.addEventListener('touchmove', (e) => {
            if (pullContainer.scrollTop > 0) return;

            currentY = e.touches[0].clientY;
            const pullDistance = currentY - startY;

            if (pullDistance > 0 && pullDistance < 100) {
                isPulling = true;
                pullContainer.classList.add('pulling');
                
                // Atualiza indicador visual
                const indicator = pullContainer.querySelector('.pull-indicator');
                if (indicator) {
                    indicator.style.transform = `translateX(-50%) translateY(${pullDistance/2}px)`;
                }
            }
        }, { passive: true });

        pullContainer.addEventListener('touchend', () => {
            if (isPulling && (currentY - startY) > 80) {
                this.performRefresh();
            }
            
            pullContainer.classList.remove('pulling');
            isPulling = false;
            
            // Reset indicator
            const indicator = pullContainer.querySelector('.pull-indicator');
            if (indicator) {
                indicator.style.transform = 'translateX(-50%)';
            }
        });
    }

    async performRefresh() {
        const pullContainer = document.querySelector('.pull-to-refresh');
        if (!pullContainer) return;

        pullContainer.classList.add('refreshing');
        
        try {
            // Recarrega dados da página atual
            await this.refreshCurrentPage();
            
            // Mostra feedback de sucesso
            this.showToast('Página atualizada!', 'success');
        } catch (error) {
            console.error('Erro ao atualizar:', error);
            this.showToast('Erro ao atualizar', 'error');
        } finally {
            setTimeout(() => {
                pullContainer.classList.remove('refreshing');
            }, 1000);
        }
    }

    async refreshCurrentPage() {
        // Identifica o tipo de página e recarrega dados específicos
        const path = window.location.pathname;
        
        if (path.includes('/dashboard/tickets/')) {
            await this.refreshTickets();
        } else if (path.includes('/dashboard/chat/')) {
            await this.refreshChat();
        } else if (path.includes('/dashboard/')) {
            await this.refreshDashboard();
        } else {
            // Recarrega página completa como fallback
            window.location.reload();
        }
    }

    async refreshTickets() {
        // Recarrega lista de tickets via AJAX
        try {
            const response = await fetch('/dashboard/api/tickets/');
            const data = await response.json();
            
            // Atualiza elementos na página
            const ticketList = document.querySelector('.ticket-list');
            if (ticketList && data.html) {
                ticketList.innerHTML = data.html;
            }
        } catch (error) {
            throw error;
        }
    }

    async refreshChat() {
        // Recarrega mensagens de chat
        const roomId = this.getCurrentChatRoom();
        if (!roomId) return;

        try {
            const response = await fetch(`/dashboard/api/chat/${roomId}/messages/`);
            const data = await response.json();
            
            // Atualiza lista de mensagens
            const messagesContainer = document.querySelector('.chat-messages');
            if (messagesContainer && data.html) {
                messagesContainer.innerHTML = data.html;
            }
        } catch (error) {
            throw error;
        }
    }

    async refreshDashboard() {
        // Recarrega estatísticas do dashboard
        try {
            const response = await fetch('/dashboard/api/stats/');
            const data = await response.json();
            
            // Atualiza cards de estatísticas
            Object.keys(data).forEach(key => {
                const element = document.querySelector(`[data-stat="${key}"]`);
                if (element) {
                    element.textContent = data[key];
                }
            });
        } catch (error) {
            throw error;
        }
    }

    setupOfflineHandling() {
        // Só ativa offline handling em contexto mobile
        const isMobilePage = document.body.classList.contains('mobile-layout') || 
                           document.querySelector('.mobile-header') || 
                           window.location.pathname.includes('/mobile/') ||
                           document.querySelector('[data-mobile="true"]');
        
        if (!isMobilePage) {
            return; // Não ativa em páginas desktop
        }
        
        // Garante que só um offline-indicator exista
        let offlineIndicator = this.createOfflineIndicator();

        // Função para mostrar o banner
        const showOffline = () => {
            offlineIndicator.classList.add('show');
        };
        // Função para esconder/remover o banner
        const hideOffline = () => {
            offlineIndicator.classList.remove('show');
            // Opcional: remove do DOM após 1s (se quiser sumir de vez)
            // setTimeout(() => { if (offlineIndicator.parentNode) offlineIndicator.parentNode.removeChild(offlineIndicator); }, 1000);
        };

        window.addEventListener('online', () => {
            hideOffline();
            this.showToast('Conexão restaurada!', 'success');
            // Sincroniza dados pendentes
            this.syncPendingData();
        });

        window.addEventListener('offline', () => {
            showOffline();
            this.showToast('Você está offline', 'warning');
        });

        // Verifica status inicial
        if (!navigator.onLine) {
            showOffline();
        } else {
            hideOffline();
        }
    }

    createOfflineIndicator() {
        // Garante que só um .offline-indicator exista
        let indicator = document.querySelector('.offline-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.className = 'offline-indicator';
            indicator.innerHTML = `
                <i class="material-icons" style="font-size: 16px; margin-right: 8px;">wifi_off</i>
                Você está offline. Algumas funcionalidades podem não estar disponíveis.
            `;
            document.body.appendChild(indicator);
        }
        // Sempre retorna o mesmo elemento
        return indicator;
    }

    async syncPendingData() {
        // Sincroniza dados armazenados localmente durante offline
        const pendingData = this.getPendingData();
        
        for (const item of pendingData) {
            try {
                await fetch(item.url, {
                    method: item.method,
                    headers: item.headers,
                    body: item.body
                });
                
                // Remove item sincronizado
                this.removePendingData(item.id);
            } catch (error) {
                console.error('Erro ao sincronizar:', error);
            }
        }
    }

    setupInstallPrompt() {
        this.deferredPrompt = null;

        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            this.deferredPrompt = e;
            // Mostra prompt de instalação personalizado
            this.showInstallPrompt();
        });

        // Tracked install
        window.addEventListener('appinstalled', () => {
            console.log('PWA instalado com sucesso');
            this.hideInstallPrompt();
            this.showToast('App instalado com sucesso!', 'success');
        });
    }

    showInstallPrompt() {
        // Cria prompt customizado se não existir
        let installBanner = document.querySelector('.install-banner');
        
        if (!installBanner) {
            installBanner = document.createElement('div');
            installBanner.className = 'install-banner';
            installBanner.innerHTML = `
                <div class="install-banner-content">
                    <div class="install-banner-info">
                        <i class="material-icons">get_app</i>
                        <div>
                            <strong>Instalar iConnect</strong>
                            <small>Adicione à tela inicial para acesso rápido</small>
                        </div>
                    </div>
                    <div class="install-banner-actions">
                        <button class="btn-install">Instalar</button>
                        <button class="btn-dismiss">×</button>
                    </div>
                </div>
            `;
            
            // Styles
            installBanner.style.cssText = `
                position: fixed;
                bottom: 16px;
                left: 16px;
                right: 16px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                z-index: 1050;
                transform: translateY(100%);
                transition: transform 0.3s ease;
            `;
            
            document.body.appendChild(installBanner);
        }

        // Event listeners
        installBanner.querySelector('.btn-install').addEventListener('click', async () => {
            if (this.deferredPrompt) {
                this.deferredPrompt.prompt();
                const { outcome } = await this.deferredPrompt.userChoice;
                if (outcome === 'accepted') {
                    console.log('Usuário aceitou instalar PWA');
                } else {
                    console.log('Usuário rejeitou instalar PWA');
                }
                this.deferredPrompt = null;
            }
            this.hideInstallPrompt();
        });

        installBanner.querySelector('.btn-dismiss').addEventListener('click', () => {
            this.hideInstallPrompt();
            // Guarda preferência para não mostrar novamente por um tempo
            localStorage.setItem('installPromptDismissed', Date.now().toString());
        });

        // Verifica se foi dispensado recentemente
        const dismissed = localStorage.getItem('installPromptDismissed');
        const daysSinceDismissed = dismissed ? (Date.now() - parseInt(dismissed)) / (1000 * 60 * 60 * 24) : 999;
        
        if (daysSinceDismissed > 7) { // Mostra novamente após 7 dias
            // Anima entrada
            requestAnimationFrame(() => {
                installBanner.style.transform = 'translateY(0)';
            });
        }
    }

    hideInstallPrompt() {
        const installBanner = document.querySelector('.install-banner');
        if (installBanner) {
            installBanner.style.transform = 'translateY(100%)';
            setTimeout(() => {
                installBanner.remove();
            }, 300);
        }
    }

    setupKeyboardHandling() {
        // Ajusta viewport quando teclado virtual aparece
        if (this.isIOS) {
            this.handleIOSKeyboard();
        } else if (this.isAndroid) {
            this.handleAndroidKeyboard();
        }
    }

    handleIOSKeyboard() {
        // iOS já gerencia bem o viewport
        // Apenas ajusta scroll para inputs focados
        document.addEventListener('focusin', (e) => {
            if (e.target.matches('input, textarea, select')) {
                setTimeout(() => {
                    e.target.scrollIntoView({ 
                        behavior: 'smooth', 
                        block: 'center' 
                    });
                }, 300);
            }
        });
    }

    handleAndroidKeyboard() {
        // Detecta mudanças no viewport para Android
        const viewport = window.visualViewport;
        
        if (viewport) {
            viewport.addEventListener('resize', () => {
                document.documentElement.style.setProperty(
                    '--viewport-height', 
                    `${viewport.height}px`
                );
            });
        }
    }

    setupOrientationHandling() {
        window.addEventListener('orientationchange', () => {
            // Aguarda animação de rotação completar
            setTimeout(() => {
                // Recalcula layouts que dependem de dimensões
                this.recalculateLayouts();
                
                // Reposiciona elementos fixos se necessário
                this.repositionFixedElements();
            }, 500);
        });
    }

    recalculateLayouts() {
        // Força recálculo de elementos com height: 100vh
        const fullHeightElements = document.querySelectorAll('.full-height, .chat-container, .main-content');
        
        fullHeightElements.forEach(el => {
            el.style.height = 'auto';
            requestAnimationFrame(() => {
                el.style.height = '';
            });
        });
    }

    repositionFixedElements() {
        // Reposiciona elementos que podem ficar mal posicionados após rotação
        const fixedElements = document.querySelectorAll('.fixed-bottom, .floating-button, .install-banner');
        
        fixedElements.forEach(el => {
            const rect = el.getBoundingClientRect();
            if (rect.bottom > window.innerHeight || rect.right > window.innerWidth) {
                el.style.position = 'absolute';
                requestAnimationFrame(() => {
                    el.style.position = 'fixed';
                });
            }
        });
    }

    // Utility methods
    getCurrentChatRoom() {
        const match = window.location.pathname.match(/\/chat\/room\/([^\/]+)/);
        return match ? match[1] : null;
    }

    getPendingData() {
        const stored = localStorage.getItem('pendingData');
        return stored ? JSON.parse(stored) : [];
    }

    addPendingData(data) {
        const pending = this.getPendingData();
        pending.push({
            id: Date.now().toString(),
            timestamp: Date.now(),
            ...data
        });
        localStorage.setItem('pendingData', JSON.stringify(pending));
    }

    removePendingData(id) {
        const pending = this.getPendingData();
        const filtered = pending.filter(item => item.id !== id);
        localStorage.setItem('pendingData', JSON.stringify(filtered));
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        
        toast.style.cssText = `
            position: fixed;
            top: ${this.isStandalone ? '20px' : '80px'};
            left: 50%;
            transform: translateX(-50%) translateY(-100%);
            background: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : type === 'warning' ? '#ffc107' : '#007bff'};
            color: ${type === 'warning' ? '#000' : '#fff'};
            padding: 12px 24px;
            border-radius: 24px;
            font-size: 14px;
            font-weight: 500;
            z-index: 9999;
            transition: transform 0.3s ease;
            max-width: calc(100% - 32px);
            text-align: center;
        `;
        
        document.body.appendChild(toast);
        
        // Anima entrada
        requestAnimationFrame(() => {
            toast.style.transform = 'translateX(-50%) translateY(0)';
        });
        
        // Remove após 3 segundos
        setTimeout(() => {
            toast.style.transform = 'translateX(-50%) translateY(-100%)';
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, 3000);
    }

    // Getters
    get deviceInfo() {
        return {
            isTouch: this.isTouch,
            isStandalone: this.isStandalone,
            isIOS: this.isIOS,
            isAndroid: this.isAndroid,
            userAgent: navigator.userAgent,
            viewport: {
                width: window.innerWidth,
                height: window.innerHeight
            }
        };
    }
}

// Inicializa quando DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    window.mobileManager = new MobileManager();
});

// Adiciona CSS necessário para touch feedback
const mobileStyle = document.createElement('style');
mobileStyle.textContent = `
    .touch-active {
        transform: scale(0.98);
        opacity: 0.8;
        transition: all 0.1s ease;
    }
    
    .install-banner-content {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 16px;
    }
    
    .install-banner-info {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .install-banner-info i {
        color: #e91e63;
        font-size: 24px;
    }
    
    .install-banner-actions {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .btn-install {
        background: #e91e63;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 14px;
        font-weight: 500;
    }
    
    .btn-dismiss {
        background: none;
        border: none;
        font-size: 20px;
        color: #6c757d;
        padding: 4px 8px;
        cursor: pointer;
    }
`;
document.head.appendChild(mobileStyle);
