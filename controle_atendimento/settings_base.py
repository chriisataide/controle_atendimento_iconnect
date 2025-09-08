"""
Configurações base do Django para o projeto Controle de Atendimento iConnect.
Configurações compartilhadas entre desenvolvimento e produção.
"""
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-change-me-in-production')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'dashboard',
    
    # Terceiros
    'django_extensions',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'controle_atendimento.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
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
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'assets']
STATIC_ROOT = BASE_DIR / 'staticfiles'

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

# Redis/Cache Configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache' if os.environ.get('REDIS_URL') else 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': os.environ.get('REDIS_URL', 'unique-snowflake'),
    }
}

# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 86400  # 24 horas

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
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
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

# WhatsApp Business API Configuration
WHATSAPP_CONFIG = {
    'BASE_URL': os.environ.get('WHATSAPP_API_URL', ''),
    'ACCESS_TOKEN': os.environ.get('WHATSAPP_ACCESS_TOKEN', ''),
    'PHONE_NUMBER_ID': os.environ.get('WHATSAPP_PHONE_NUMBER_ID', ''),
    'WEBHOOK_VERIFY_TOKEN': os.environ.get('WHATSAPP_WEBHOOK_TOKEN', ''),
}

# Slack Integration
SLACK_CONFIG = {
    'WEBHOOK_URL': os.environ.get('SLACK_WEBHOOK_URL', ''),
    'BOT_TOKEN': os.environ.get('SLACK_BOT_TOKEN', ''),
    'CHANNEL': os.environ.get('SLACK_CHANNEL', '#atendimento'),
}

# AI/Chatbot Configuration
AI_CONFIG = {
    'OPENAI_API_KEY': os.environ.get('OPENAI_API_KEY', ''),
    'ENABLE_CHATBOT': os.environ.get('ENABLE_CHATBOT', 'False').lower() == 'true',
    'AUTO_ASSIGNMENT': os.environ.get('ENABLE_AUTO_ASSIGNMENT', 'True').lower() == 'true',
    'SENTIMENT_ANALYSIS': os.environ.get('ENABLE_SENTIMENT_ANALYSIS', 'False').lower() == 'true',
}
