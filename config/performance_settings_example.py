# Configurações de Performance Frontend para iConnect
# Adicione estas configurações ao seu settings.py

# ========== OTIMIZAÇÃO DE PERFORMANCE FRONTEND ==========

# Ativar otimizações de performance
PERFORMANCE_OPTIMIZATIONS_ENABLED = True

# Ativar tracking de métricas de performance
PERFORMANCE_TRACKING_ENABLED = not DEBUG  # Ativar apenas em produção

# Diretório para assets otimizados
OPTIMIZED_ASSETS_DIR = "optimized"

# ========== COMPRESSÃO E MINIFICAÇÃO ==========

# Ativar compressão gzip para assets
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True

# Algoritmos de compressão
COMPRESS_ALGO = "gzip"  # ou 'brotli' se disponível

# Minificação de CSS
CSS_MINIFY_ENABLED = True
CSS_MINIFY_EXCLUDE = [
    "admin/",  # Excluir CSS do admin
    "debug_toolbar/",  # Excluir debug toolbar
]

# Minificação de JavaScript
JS_MINIFY_ENABLED = True
JS_MINIFY_EXCLUDE = [
    "admin/",
    "debug_toolbar/",
    "min.js",  # Já minificados
]

# ========== CACHE DE ASSETS ==========

# Cache busting para assets
ASSET_CACHE_BUSTING = True

# Duração do cache de assets (em segundos)
ASSET_CACHE_DURATION = 31536000  # 1 ano

# Headers de cache para assets
ASSET_CACHE_HEADERS = {
    "Cache-Control": "public, max-age=31536000, immutable",
    "Expires": "Thu, 31 Dec 2025 23:59:59 GMT",
}

# ========== LAZY LOADING ==========

# Ativar lazy loading automático
LAZY_LOADING_ENABLED = True

# Threshold para iniciar carregamento (em pixels)
LAZY_LOADING_THRESHOLD = 50

# Placeholder para imagens lazy
LAZY_IMAGE_PLACEHOLDER = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"

# ========== BUNDLE CONFIGURATION ==========

# Bundles de CSS crítico
CRITICAL_CSS_BUNDLES = {
    "main": [
        "css/material-dashboard.min.css",
        "css/nucleo-icons.css",
    ],
    "mobile": [
        "css/mobile.css",
        "css/responsive.css",
    ],
}

# Bundles de JavaScript crítico
CRITICAL_JS_BUNDLES = {
    "core": [
        "js/core/bootstrap.bundle.min.js",
        "js/material-dashboard.min.js",
    ],
    "performance": [
        "js/performance-optimizer.js",
    ],
}

# Scripts não críticos (lazy load)
LAZY_JS_BUNDLES = {
    "plugins": [
        "js/plugins/perfect-scrollbar.min.js",
        "js/plugins/smooth-scrollbar.min.js",
        "js/plugins/chartjs.min.js",
    ],
    "pwa": [
        "js/mobile.js",
        "js/push-notifications.js",
        "js/cache.js",
    ],
}

# ========== IMAGE OPTIMIZATION ==========

# Ativar otimização de imagens
IMAGE_OPTIMIZATION_ENABLED = True

# Qualidade JPEG para otimização
JPEG_QUALITY = 85

# Formatos de imagem suportados
SUPPORTED_IMAGE_FORMATS = ["jpg", "jpeg", "png", "gif", "webp"]

# Ativar conversão automática para WebP
WEBP_CONVERSION_ENABLED = True

# Tamanhos de imagem responsivos
RESPONSIVE_IMAGE_SIZES = [320, 480, 768, 1024, 1200, 1920]

# ========== CDN CONFIGURATION ==========

# URLs de CDN para recursos externos
CDN_URLS = {
    "fonts.googleapis.com": "https://fonts.googleapis.com",
    "fonts.gstatic.com": "https://fonts.gstatic.com",
    "cdnjs.cloudflare.com": "https://cdnjs.cloudflare.com",
    "cdn.jsdelivr.net": "https://cdn.jsdelivr.net",
}

# Preconnect para CDNs
CDN_PRECONNECT = [
    "https://fonts.googleapis.com",
    "https://fonts.gstatic.com",
    "https://cdnjs.cloudflare.com",
]

# DNS Prefetch para domínios externos
DNS_PREFETCH = [
    "//fonts.googleapis.com",
    "//fonts.gstatic.com",
    "//cdnjs.cloudflare.com",
    "//cdn.jsdelivr.net",
    "//cdn.socket.io",
]

# ========== SERVICE WORKER ==========

# Ativar Service Worker para cache
SERVICE_WORKER_ENABLED = True

# Estratégia de cache
CACHE_STRATEGY = "stale-while-revalidate"  # ou 'cache-first', 'network-first'

# Recursos para cache offline
OFFLINE_CACHE_RESOURCES = [
    "/static/css/material-dashboard.min.css",
    "/static/js/material-dashboard.min.js",
    "/static/js/performance-optimizer.js",
    "/dashboard/",
    "/dashboard/tickets/",
]

# ========== PERFORMANCE MONITORING ==========

# Core Web Vitals thresholds
CORE_WEB_VITALS = {
    "FCP": {"good": 1800, "poor": 3000},  # First Contentful Paint (ms)
    "LCP": {"good": 2500, "poor": 4000},  # Largest Contentful Paint (ms)
    "FID": {"good": 100, "poor": 300},  # First Input Delay (ms)
    "CLS": {"good": 0.1, "poor": 0.25},  # Cumulative Layout Shift
}

# Métricas customizadas
CUSTOM_METRICS = {
    "dom_ready": {"good": 1000, "poor": 2000},
    "page_load": {"good": 2000, "poor": 4000},
    "memory_usage": {"good": 50, "poor": 100},  # MB
}

# ========== MIDDLEWARE DE PERFORMANCE ==========

# Adicionar ao MIDDLEWARE
# 'dashboard.middleware.PerformanceMiddleware',

# Configurações do middleware
PERFORMANCE_MIDDLEWARE_CONFIG = {
    "collect_metrics": True,
    "log_slow_requests": True,
    "slow_request_threshold": 1000,  # ms
    "enable_caching": True,
}

# ========== COMANDOS DE BUILD ==========

# Configuração para build de produção
PRODUCTION_BUILD_CONFIG = {
    "minify_css": True,
    "minify_js": True,
    "optimize_images": True,
    "create_bundles": True,
    "generate_service_worker": True,
    "compress_assets": True,
}

# ========== FERRAMENTAS EXTERNAS ==========

# Configuração para Lighthouse CI
LIGHTHOUSE_CONFIG = {
    "collect": {
        "numberOfRuns": 3,
        "startServerCommand": "python manage.py runserver",
        "url": ["http://localhost:8000/dashboard/"],
    },
    "assert": {
        "assertions": {
            "categories:performance": ["warn", {"minScore": 0.9}],
            "categories:accessibility": ["error", {"minScore": 0.9}],
            "categories:best-practices": ["warn", {"minScore": 0.9}],
            "categories:seo": ["warn", {"minScore": 0.9}],
        }
    },
}

# ========== EXEMPLOS DE USO ==========

# No template:
# {% load performance_tags %}
#
# <!-- CSS otimizado -->
# {% critical_css_bundle %}
# {% optimized_css 'css/custom.css' preload=True %}
#
# <!-- JavaScript otimizado -->
# {% critical_js_bundle defer=True %}
# {% optimized_js 'js/app.js' lazy=True %}
#
# <!-- Imagens otimizadas -->
# {% optimized_image 'img/hero.jpg' lazy=True webp=True alt='Hero Image' %}
#
# <!-- Monitor de performance -->
# {% performance_monitor %}

# ========== COMANDOS DISPONÍVEIS ==========

# Otimizar todos os assets:
# python manage.py optimize_assets

# Otimizar apenas CSS:
# python manage.py optimize_assets --css-only

# Otimizar apenas JavaScript:
# python manage.py optimize_assets --js-only

# Otimizar apenas imagens:
# python manage.py optimize_assets --images-only

# Forçar re-otimização:
# python manage.py optimize_assets --force

# Gerar relatório de performance:
# python manage.py performance_report

# ========== INTEGRAÇÃO COM WEBPACK (OPCIONAL) ==========

# Se usar Webpack, configurar para integração:
# WEBPACK_LOADER = {
#     'DEFAULT': {
#         'BUNDLE_DIR_NAME': 'webpack_bundles/',
#         'STATS_FILE': os.path.join(BASE_DIR, 'webpack-stats.json'),
#         'POLL_INTERVAL': 0.1,
#         'TIMEOUT': None,
#         'IGNORE': [r'.+\.hot-update.js', r'.+\.map'],
#         'LOADER_CLASS': 'webpack_loader.loader.WebpackLoader',
#     }
# }
