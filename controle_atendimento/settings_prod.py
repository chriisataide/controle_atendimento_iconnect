"""
Configurações de Produção para o Controle de Atendimento iConnect.
Configurações otimizadas e seguras para ambiente de produção.
"""

from decouple import config

from .settings_base import *  # noqa: F401,F403

# ==========================================================================
# SEGURANÇA
# ==========================================================================

DEBUG = False

# SECRET_KEY DEVE vir de variável de ambiente em produção
SECRET_KEY = config("SECRET_KEY")

# Validar que não está usando a chave insegura padrão
if "insecure" in SECRET_KEY.lower() or "MUDE-ESTA-CHAVE" in SECRET_KEY:
    raise ValueError(
        "CRITICAL: SECRET_KEY de producao nao pode ser a chave padrao insegura. "
        "Gere uma nova com: python -c "
        "'from django.core.management.utils import get_random_secret_key; "
        "print(get_random_secret_key())'"
    )

# Hosts permitidos (obrigatório em produção)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="").split(",")

# Cookies seguros em produção (HTTPS)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 ano
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ==========================================================================
# BANCO DE DADOS
# ==========================================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB", default="iconnect_db"),
        "USER": config("POSTGRES_USER", default="iconnect_user"),
        "PASSWORD": config("POSTGRES_PASSWORD", default=""),
        "HOST": config("DATABASE_HOST", default="db"),
        "PORT": config("DATABASE_PORT", default="5432"),
        "OPTIONS": {
            "sslmode": config("DATABASE_SSL_MODE", default="prefer"),
        },
        "CONN_MAX_AGE": 600,
        "CONN_HEALTH_CHECKS": True,
    }
}

# ==========================================================================
# CACHE (Redis em produção)
# ==========================================================================

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://redis:6379/1"),
        "KEY_PREFIX": "iconnect",
        "TIMEOUT": 300,
    }
}

# ==========================================================================
# ARQUIVOS ESTÁTICOS
# ==========================================================================

# Django 5.x: STATICFILES_STORAGE migrado para STORAGES
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ==========================================================================
# CORS
# ==========================================================================

CORS_ALLOWED_ORIGINS = [o.strip() for o in config("CORS_ALLOWED_ORIGINS", default="").split(",") if o.strip()]

# ==========================================================================
# CELERY
# ==========================================================================

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="redis://redis:6379/0")
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# ==========================================================================
# LOGGING — mais restritivo em produção
# ==========================================================================

LOGGING["handlers"]["file"]["level"] = "WARNING"
LOGGING["handlers"]["file"]["filename"] = BASE_DIR / "logs" / "iconnect_prod.log"
LOGGING["handlers"]["file"]["class"] = "logging.handlers.RotatingFileHandler"
LOGGING["handlers"]["file"]["maxBytes"] = 10 * 1024 * 1024  # 10 MB
LOGGING["handlers"]["file"]["backupCount"] = 5
LOGGING["loggers"]["django"]["level"] = "WARNING"
LOGGING["loggers"]["dashboard"]["level"] = "WARNING"

# Handler de erros críticos
LOGGING["handlers"]["error_file"] = {
    "level": "ERROR",
    "class": "logging.handlers.RotatingFileHandler",
    "filename": BASE_DIR / "logs" / "iconnect_errors.log",
    "formatter": "verbose",
    "maxBytes": 10 * 1024 * 1024,  # 10 MB
    "backupCount": 5,
}
LOGGING["loggers"]["django"]["handlers"].append("error_file")
LOGGING["loggers"]["dashboard"]["handlers"].append("error_file")

# ==========================================================================
# CHANNEL LAYERS (WebSocket em produção via Redis)
# ==========================================================================

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [config("REDIS_URL", default="redis://redis:6379/0")],
        },
    },
}
