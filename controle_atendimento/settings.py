"""
Configuração principal do Django para o projeto controle_atendimento.
Carrega configurações modularizadas por ambiente com decouple.

ATENÇÃO: Este arquivo NÃO deve redefinir settings já definidos em
settings_base/dev/prod. Apenas orquestra qual módulo carregar e
define configurações específicas de integração (WhatsApp, Channels).
"""
import logging
from decouple import config

logger = logging.getLogger(__name__)

# Determina o ambiente atual
ENVIRONMENT = config('ENVIRONMENT', default='development')

# Importa as configurações baseadas no ambiente
if ENVIRONMENT == 'production':
    from .settings_prod import *  # noqa: F401,F403
elif ENVIRONMENT == 'development':
    from .settings_dev import *  # noqa: F401,F403
else:
    from .settings_dev import *  # noqa: F401,F403

logger.info(f"Django rodando em modo: {ENVIRONMENT.upper()}")

# ========== CONFIGURAÇÕES WHATSAPP BUSINESS ==========
WHATSAPP_WEBHOOK_VERIFY_TOKEN = config(
    'WHATSAPP_WEBHOOK_VERIFY_TOKEN',
    default='',
)
WHATSAPP_API_BASE_URL = 'https://graph.facebook.com/v18.0'
WHATSAPP_REQUEST_TIMEOUT = 30  # segundos
WHATSAPP_LOG_WEBHOOKS = config('WHATSAPP_LOG_WEBHOOKS', default=True, cast=bool)
