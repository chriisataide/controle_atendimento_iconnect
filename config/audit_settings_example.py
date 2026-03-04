# Configuração do Sistema de Auditoria iConnect
# Adicione estas configurações ao seu settings.py

# ========== AUDITORIA E LOGGING ==========


# Diretório para logs
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Configuração de logging avançada
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {message}",
            "style": "{",
        },
        "audit": {
            "format": "{asctime} | {levelname} | {module} | {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"level": "INFO", "class": "logging.StreamHandler", "formatter": "simple"},
        "audit_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "audit.log",
            "maxBytes": 1024 * 1024 * 50,  # 50MB
            "backupCount": 10,
            "formatter": "audit",
        },
        "security_file": {
            "level": "WARNING",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "security.log",
            "maxBytes": 1024 * 1024 * 25,  # 25MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "performance_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "performance.log",
            "maxBytes": 1024 * 1024 * 25,  # 25MB
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "dashboard.audit_system": {
            "handlers": ["audit_file", "console"],
            "level": "INFO",
            "propagate": False,
        },
        "dashboard.security": {
            "handlers": ["security_file", "console"],
            "level": "WARNING",
            "propagate": False,
        },
        "dashboard.performance": {
            "handlers": ["performance_file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["security_file"],
            "level": "ERROR",
            "propagate": True,
        },
    },
}

# ========== MIDDLEWARE DE AUDITORIA ==========
# Adicione ao MIDDLEWARE (preferencialmente no início)
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "dashboard.security.SecurityHeadersMiddleware",  # Middleware de segurança
    "dashboard.audit_system.AuditMiddleware",  # Middleware de auditoria
    "dashboard.api_versioning.APIVersionMiddleware",  # Middleware de versionamento
    # ... outros middlewares existentes
]

# ========== CONFIGURAÇÕES DE AUDITORIA ==========

# Ativar auditoria
AUDIT_ENABLED = True

# Ativar auditoria para requests HTTP (pode gerar muitos logs)
AUDIT_HTTP_REQUESTS = False

# Auditoria de dados sensíveis
AUDIT_SENSITIVE_DATA = True

# Tabelas consideradas sensíveis
SENSITIVE_TABLES = [
    "auth_user",
    "dashboard_cliente",
    "dashboard_ticket",
    "dashboard_perfilusuario",
]

# Campos considerados sensíveis
SENSITIVE_FIELDS = [
    "password",
    "email",
    "telefone",
    "cpf",
    "cnpj",
    "endereco",
]

# Retenção de logs de auditoria (em dias)
AUDIT_RETENTION_DAYS = 365

# Retenção de eventos de segurança (em dias)
SECURITY_RETENTION_DAYS = 90

# Retenção de logs de acesso a dados (em dias)
DATA_ACCESS_RETENTION_DAYS = 180

# ========== CONFIGURAÇÕES DE SEGURANÇA ==========

# Cache para rate limiting (usando Redis se disponível)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}

# Se tiver Redis disponível:
# CACHES = {
#     'default': {
#         'BACKEND': 'django.core.cache.backends.redis.RedisCache',
#         'LOCATION': 'redis://127.0.0.1:6379/1',
#     }
# }

# Rate limiting padrão
DEFAULT_RATE_LIMIT = {
    "max_requests": 1000,
    "window_seconds": 3600,
}

# Rate limits específicos por endpoint
RATE_LIMITS = {
    "login": {"max_requests": 5, "window_seconds": 300},
    "password_reset": {"max_requests": 3, "window_seconds": 3600},
    "api_calls": {"max_requests": 100, "window_seconds": 3600},
    "file_upload": {"max_requests": 10, "window_seconds": 600},
}

# IPs confiáveis (não aplicar rate limiting)
TRUSTED_IPS = [
    "127.0.0.1",
    "::1",
    # Adicione IPs de servidores internos
]

# ========== CONFIGURAÇÕES DE NOTIFICAÇÃO ==========

# Email para alertas de segurança críticos
SECURITY_ALERT_EMAIL = "admin@exemplo.com"

# Webhook para alertas (Slack, Teams, etc.)
SECURITY_WEBHOOK_URL = None

# Ativar notificações por email para eventos críticos
EMAIL_SECURITY_ALERTS = True

# ========== COMANDOS DE MANUTENÇÃO ==========

# Configurações para limpeza automática de logs antigos
# Adicione ao crontab:
#
# # Limpeza de logs de auditoria (diário às 1:00)
# 0 1 * * * cd /caminho/para/projeto && python manage.py audit_cleanup
#
# # Relatório semanal de auditoria (segundas às 8:00)
# 0 8 * * 1 cd /caminho/para/projeto && python manage.py audit_report --days 7 --type summary
#
# # Backup semanal (domingos às 2:00)
# 0 2 * * 0 cd /caminho/para/projeto && python manage.py backup --full

# ========== EXEMPLOS DE USO ==========

# Gerar relatório de auditoria dos últimos 30 dias:
# python manage.py audit_report --days 30 --type full

# Gerar relatório de segurança:
# python manage.py audit_report --days 7 --type security

# Gerar relatório de acesso a dados por usuário:
# python manage.py audit_report --days 30 --type access --user admin

# Gerar relatório resumido em JSON:
# python manage.py audit_report --days 7 --type summary --format json

# ========== MONITORAMENTO EM PRODUÇÃO ==========

# Para monitoramento em produção, considere:
# 1. Usar Sentry para tracking de erros
# 2. Usar ELK Stack (Elasticsearch, Logstash, Kibana) para análise de logs
# 3. Usar Prometheus + Grafana para métricas
# 4. Configurar alertas automáticos para eventos críticos

# Exemplo de integração com Sentry:
# import sentry_sdk
# from sentry_sdk.integrations.django import DjangoIntegration
# from sentry_sdk.integrations.logging import LoggingIntegration
#
# sentry_logging = LoggingIntegration(
#     level=logging.INFO,
#     event_level=logging.ERROR
# )
#
# sentry_sdk.init(
#     dsn="YOUR_SENTRY_DSN",
#     integrations=[DjangoIntegration(), sentry_logging],
#     traces_sample_rate=0.1,
#     send_default_pii=True
# )
