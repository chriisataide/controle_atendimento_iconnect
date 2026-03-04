"""
Configuração do Celery para processamento de tarefas em background
"""

import os

from celery import Celery

# Define Django settings module para o celery
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "controle_atendimento.settings")

# Criar instância do Celery
app = Celery("controle_atendimento")

# Configurar usando Django settings com prefixo CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")

# Garantir que broker_connection_retry_on_startup está definido
# (silencia CPendingDeprecationWarning em Celery 5.x)
app.conf.broker_connection_retry_on_startup = True

# Descobrir automaticamente tarefas em todos os apps registrados
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    import logging

    logging.getLogger(__name__).debug(f"Request: {self.request!r}")
