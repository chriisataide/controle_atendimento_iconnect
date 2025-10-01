"""
Configuração do Django para o projeto controle_atendimento.
Agora usando configurações modularizadas por ambiente com decouple.
"""
import os
from decouple import config

# Determina o ambiente atual
ENVIRONMENT = config('ENVIRONMENT', default='development')

# Importa as configurações baseadas no ambiente
if ENVIRONMENT == 'production':
    from .settings_prod import *
elif ENVIRONMENT == 'development':
    from .settings_dev import *
else:
    # Fallback para configurações básicas de desenvolvimento
    from .settings_dev import *
    
print(f"🚀 Django rodando em modo: {ENVIRONMENT.upper()}")

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-@6_2*65&%cv6l!gn(b(zt04p*_7dddph#v43#flay&fnif(v)d'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*', 'testserver', 'localhost', '127.0.0.1']


# Application definition

INSTALLED_APPS = [
    'daphne',  # Django Channels ASGI
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',  # WebSocket support
    'rest_framework',
    'rest_framework.authtoken',
    'dashboard',
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


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'assets',
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (user uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Login URLs
LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    }
}

# Cache Configuration
import socket

def test_redis_connection():
    """Testa se o Redis está disponível"""
    # Configurações para tentar
    redis_configs = [
        {'host': 'redis', 'port': 6379, 'password': 'redis_password'},  # Docker com senha
        {'host': 'redis', 'port': 6379, 'password': None},              # Docker sem senha
        {'host': '127.0.0.1', 'port': 6379, 'password': None},          # Local sem senha
        {'host': 'localhost', 'port': 6379, 'password': None},          # Local sem senha
    ]
    
    for config in redis_configs:
        try:
            import redis
            r = redis.Redis(
                host=config['host'], 
                port=config['port'], 
                password=config['password'],
                socket_timeout=2, 
                socket_connect_timeout=2
            )
            r.ping()
            print(f"✅ Redis conectado em {config['host']}:{config['port']} (senha: {'sim' if config['password'] else 'não'})")
            return True, config
        except Exception as e:
            print(f"❌ Falha ao conectar Redis em {config['host']}:{config['port']} - {e}")
            continue
    
    print("❌ Redis não disponível em nenhuma configuração")
    return False, None

redis_available, redis_config = test_redis_connection()

if redis_available:
    # Construir URL do Redis
    if redis_config['password']:
        redis_url = f"redis://:{redis_config['password']}@{redis_config['host']}:{redis_config['port']}/1"
    else:
        redis_url = f"redis://{redis_config['host']}:{redis_config['port']}/1"
    
    # Tentar usar django-redis primeiro, fallback para backend nativo
    try:
        import django_redis
        CACHES = {
            'default': {
                'BACKEND': 'django_redis.cache.RedisCache',
                'LOCATION': redis_url,
                'OPTIONS': {
                    'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                    'CONNECTION_POOL_KWARGS': {
                        'socket_timeout': 5,
                        'socket_connect_timeout': 5,
                        'retry_on_timeout': True,
                    },
                }
            }
        }
        print("✅ Usando django-redis backend")
    except ImportError:
        # Fallback para backend nativo do Django (mais simples)
        CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                'LOCATION': redis_url,
                'TIMEOUT': 300,
            }
        }
        print("✅ Usando backend Redis nativo do Django")
    print(f"✅ Cache configurado para Redis em {redis_config['host']}:{redis_config['port']}")
else:
    # Fallback para cache local
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
            'OPTIONS': {
                'MAX_ENTRIES': 10000,
                'CULL_FREQUENCY': 4,
            }
        }
    }
    print("⚠️  Redis não disponível, usando cache local")

# Django Channels Configuration
ASGI_APPLICATION = 'controle_atendimento.asgi.application'

if redis_available:
    # Configuração do Channels
    channel_config = {
        "hosts": [(redis_config['host'], redis_config['port'])],
    }
    if redis_config['password']:
        channel_config["hosts"] = [f"redis://:{redis_config['password']}@{redis_config['host']}:{redis_config['port']}/0"]
    
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": channel_config,
        },
    }
    print(f"✅ Channels configurado para Redis em {redis_config['host']}:{redis_config['port']}")
else:
    # Fallback para in-memory channel layer
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        },
    }
    print("⚠️  Channels usando camada em memória (apenas para desenvolvimento)")

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ========== CONFIGURAÇÕES WHATSAPP BUSINESS ==========
# Token de verificação do webhook (configure no .env)
WHATSAPP_WEBHOOK_VERIFY_TOKEN = config('WHATSAPP_WEBHOOK_VERIFY_TOKEN', default='controle_atendimento_webhook_2024')

# URL base da API do WhatsApp Business (normalmente não muda)
WHATSAPP_API_BASE_URL = 'https://graph.facebook.com/v18.0'

# Configurações de timeout para requisições WhatsApp
WHATSAPP_REQUEST_TIMEOUT = 30  # segundos

# Log de webhooks (recomendado True em produção)
WHATSAPP_LOG_WEBHOOKS = True
