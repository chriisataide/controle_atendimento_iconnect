"""
Configurações base do Django para o projeto Controle de Atendimento iConnect.
Configurações compartilhadas entre desenvolvimento e produção.
"""
import os
from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
# Gerado pelo Django: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
SECRET_KEY = config('SECRET_KEY')  # OBRIGATÓRIO — defina no .env ou variável de ambiente

try:
    from config.sentry_settings_example import *  # type: ignore
except ImportError:
    pass

# Application definition
INSTALLED_APPS = [
    'daphne',  # ASGI server — deve vir antes de staticfiles
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'dashboard',
    
    # Terceiros
    'django_extensions',
    'rest_framework',
    'django_filters',
    'corsheaders',
    'channels',  # WebSocket & real-time
    'axes',
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Para arquivos estáticos
    'corsheaders.middleware.CorsMiddleware',  # CORS antes do CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',  # i18n
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'dashboard.middleware.CSPNonceMiddleware',  # Gera nonce CSP por request
    'dashboard.security.SecurityHeadersMiddleware',  # Headers de seguranca
    'dashboard.audit_system.AuditMiddleware',  # Audit trail de requests
    'dashboard.monitoring.MonitoringMiddleware',  # Monitoramento customizado
    'dashboard.tenants.TenantMiddleware',  # Multi-tenancy — injeta tenant no request
    'axes.middleware.AxesMiddleware',  # Brute-force protection (deve ser ultimo)
]

# Seguranca: configuracoes agora estao no final deste arquivo (AXES_*, AUTHENTICATION_BACKENDS)
# As configuracoes legadas em config/ nao sao mais importadas.

ROOT_URLCONF = 'controle_atendimento.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'dashboard.rbac.rbac_context',
                'dashboard.sso.sso_context',
                'dashboard.tenants.tenant_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'controle_atendimento.wsgi.application'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ('pt-br', 'Português (Brasil)'),
    ('en', 'English'),
    ('es', 'Español'),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'assets', BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# --- Ativação segura do compressor (após definição de STATICFILES_FINDERS) ---
try:
    from config.compressor_settings_example import *  # type: ignore
    if 'compressor' not in INSTALLED_APPS:
        INSTALLED_APPS += ['compressor']
    if 'compressor.finders.CompressorFinder' not in STATICFILES_FINDERS:
        STATICFILES_FINDERS = list(STATICFILES_FINDERS) + ['compressor.finders.CompressorFinder']
except ImportError:
    # Compressor não instalado, pular configuração
    pass

# Media files (user uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Login and logout URLs
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_URL = '/logout/'
LOGOUT_REDIRECT_URL = '/login/'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@iconnect.com')

# Redis/Cache Configuration (base — pode ser sobrescrita em dev/prod)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache' if config('REDIS_URL', default='') else 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': config('REDIS_URL', default='unique-snowflake'),
        'KEY_PREFIX': 'iconnect',
        'TIMEOUT': 300,
    }
}

# Session configuration — cached_db garante que sessões sobrevivem a restarts do cache
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# Cache key prefixes
CACHE_KEYS = {
    'tickets': 'tickets',
    'dashboard_stats': 'dashboard_stats',
    'user_permissions': 'user_perms',
    'ml_predictions': 'ml_pred',
}

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
        },
        'dashboard': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Sistema de SLA (Service Level Agreement)
SLA_CONFIG = {
    'RESPONSE_TIMES': {
        'critica': {'hours': 1},    # 1 hora
        'alta': {'hours': 4},       # 4 horas
        'media': {'hours': 24},     # 24 horas
        'baixa': {'hours': 72},     # 72 horas
    },
    'ESCALATION_LEVELS': [
        {'level': 1, 'delay_hours': 2},
        {'level': 2, 'delay_hours': 8},
        {'level': 3, 'delay_hours': 24},
    ]
}

# Workflow Configuration
WORKFLOW_CONFIG = {
    'DEFAULT_WORKFLOWS': {
        'suporte_tecnico': [
            'aberto', 'em_analise', 'aguardando_cliente', 
            'em_desenvolvimento', 'teste', 'resolvido', 'fechado'
        ],
        'comercial': [
            'aberto', 'qualificacao', 'proposta', 
            'negociacao', 'fechado_ganho', 'fechado_perdido'
        ],
        'financeiro': [
            'aberto', 'em_analise', 'aprovado', 
            'rejeitado', 'processado', 'fechado'
        ]
    },
    'STATUS_COLORS': {
        'aberto': '#17a2b8',
        'em_analise': '#ffc107',
        'aguardando_cliente': '#fd7e14',
        'em_desenvolvimento': '#6f42c1',
        'teste': '#20c997',
        'resolvido': '#28a745',
        'fechado': '#6c757d',
        'qualificacao': '#007bff',
        'proposta': '#17a2b8',
        'negociacao': '#ffc107',
        'fechado_ganho': '#28a745',
        'fechado_perdido': '#dc3545',
        'aprovado': '#28a745',
        'rejeitado': '#dc3545',
        'processado': '#6f42c1'
    }
}


# Integrações externas (WhatsApp, Slack, CRM, ERP, Webhooks)
try:
    from config.integrations_settings_example import *
except ImportError:
    pass

# AI/Chatbot Configuration
AI_CONFIG = {
    'OPENAI_API_KEY': config('OPENAI_API_KEY', default=''),
    'ENABLE_CHATBOT': config('ENABLE_CHATBOT', default=False, cast=bool),
    'AUTO_ASSIGNMENT': config('ENABLE_AUTO_ASSIGNMENT', default=True, cast=bool),
    'SENTIMENT_ANALYSIS': config('ENABLE_SENTIMENT_ANALYSIS', default=False, cast=bool),
}

# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://redis:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_SERIALIZER = 'json'
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Celery Beat — agendamento de tarefas periódicas
from datetime import timedelta as _td  # noqa: E402
CELERY_BEAT_SCHEDULE = {
    'execute-scheduled-rules': {
        'task': 'dashboard.tasks.execute_scheduled_rules',
        'schedule': _td(minutes=5),
    },
    'send-scheduled-reports': {
        'task': 'dashboard.tasks.send_scheduled_reports',
        'schedule': _td(hours=1),
    },
    'monitor-sla-breaches': {
        'task': 'dashboard.tasks.monitor_sla_breaches',
        'schedule': _td(minutes=5),
    },
    'check-equipment-alerts': {
        'task': 'dashboard.tasks.check_equipment_alerts',
        'schedule': _td(hours=1),
    },
    'check-kpi-alerts': {
        'task': 'dashboard.tasks.check_kpi_alerts',
        'schedule': _td(minutes=15),
    },
    'recalculate-customer-health': {
        'task': 'dashboard.tasks.recalculate_customer_health',
        'schedule': _td(hours=6),
    },
    'update-agent-leaderboard': {
        'task': 'dashboard.tasks.update_agent_leaderboard',
        'schedule': _td(hours=1),
    },
    'check-inbound-emails': {
        'task': 'dashboard.tasks.check_inbound_emails',
        'schedule': _td(minutes=5),
    },
    'lgpd-data-retention': {
        'task': 'dashboard.tasks.lgpd_data_retention',
        'schedule': _td(hours=24),
    },
}


# ==================== REST Framework ====================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
    },
}

# JWT Configuration
from datetime import timedelta  # noqa: E402
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# CORS Configuration — origens específicas definidas em settings_dev.py / settings_prod.py
CORS_ALLOWED_ORIGINS = []  # Sobrescrito por ambiente
CORS_ALLOW_CREDENTIALS = True

# Django Axes - Brute-force protection
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=30)
AXES_LOCKOUT_TEMPLATE = None  # Usa JSON response
AXES_RESET_ON_SUCCESS = True
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]
CELERY_TIMEZONE = TIME_ZONE
