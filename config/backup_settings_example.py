# Configurações de Backup para iConnect
# Adicione estas configurações ao seu settings.py

# ========== CONFIGURAÇÕES DE BACKUP ==========

# Número de dias para manter backups locais
BACKUP_KEEP_LOCAL_DAYS = 7

# Número de dias para manter backups remotos
BACKUP_KEEP_REMOTE_DAYS = 30

# ========== AMAZON S3 (OPCIONAL) ==========
# Configurações para upload automático para S3
# Descomente e configure se desejar usar S3

# AWS_ACCESS_KEY_ID = 'sua_access_key_aqui'
# AWS_SECRET_ACCESS_KEY = 'sua_secret_key_aqui'
# BACKUP_S3_BUCKET = 'nome-do-seu-bucket'

# ========== LOGGING PARA BACKUPS ==========
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "backup_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "backup.log"),
            "maxBytes": 1024 * 1024 * 15,  # 15MB
            "backupCount": 10,
            "formatter": "verbose",
        },
        "console": {"level": "INFO", "class": "logging.StreamHandler", "formatter": "simple"},
    },
    "loggers": {
        "dashboard.management.commands.backup": {
            "handlers": ["backup_file", "console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ========== CRON JOB EXEMPLO ==========
# Para automatizar backups, adicione ao crontab:
#
# # Backup completo diário às 2:00 AM
# 0 2 * * * cd /caminho/para/projeto && python manage.py backup --full
#
# # Backup apenas do banco de dados a cada 6 horas
# 0 */6 * * * cd /caminho/para/projeto && python manage.py backup --database-only

# ========== DEPENDÊNCIAS OPCIONAIS ==========
# Para suporte completo, instale:
# pip install boto3  # Para upload S3
# pip install psycopg2-binary  # Para PostgreSQL

# ========== EXEMPLOS DE USO ==========
# python manage.py backup --full          # Backup completo
# python manage.py backup --database-only # Apenas banco de dados
# python manage.py backup --media-only    # Apenas arquivos de mídia
# python manage.py backup --fixtures-only # Apenas dados (JSON)
