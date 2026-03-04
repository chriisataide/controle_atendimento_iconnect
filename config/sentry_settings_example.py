"""
Exemplo de configuração do Sentry para Django
"""

import os

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

SENTRY_DSN = os.getenv("SENTRY_DSN", "")

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.5,  # Ajuste conforme necessidade
        send_default_pii=True,
        environment=os.getenv("ENVIRONMENT", "development"),
    )
