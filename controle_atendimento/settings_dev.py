"""
Configurações para ambiente de desenvolvimento.
Funciona tanto local (SQLite + LocMemCache) quanto Docker (PostgreSQL + Redis).
"""

import os

from .settings_base import *  # noqa: F401,F403

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# CORS — Origens de desenvolvimento
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8001",
]

# Database: PostgreSQL se DATABASE_URL disponível, senão SQLite
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL:
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(DATABASE_URL)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Configurações de desenvolvimento para debugging
# Só adiciona debug_toolbar se estiver instalado
try:
    import debug_toolbar  # noqa: F401

    INSTALLED_APPS += ["debug_toolbar"]
    MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]
except ImportError:
    pass

# Debug Toolbar Configuration
INTERNAL_IPS = [
    "127.0.0.1",
    "localhost",
]

# Configurações de email para desenvolvimento (console)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Cache: Redis se REDIS_URL disponível, senão LocMemCache
REDIS_URL = os.environ.get("REDIS_URL", "")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "iconnect",
            "TIMEOUT": 300,
        }
    }
    # Channel Layer com Redis
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
            },
        },
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
    # Channel Layer em memória (apenas dev local)
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }

# Logging menos verboso para evitar spam de debug
LOGGING["handlers"]["console"]["level"] = "INFO"
LOGGING["loggers"]["django"]["level"] = "INFO"
LOGGING["loggers"]["dashboard"]["level"] = "INFO"

# Celery: se tem broker Redis, usar normalmente; senão, modo eager
if REDIS_URL:
    CELERY_TASK_ALWAYS_EAGER = False
else:
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
