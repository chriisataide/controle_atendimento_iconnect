"""
ASGI config for controle_atendimento project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Configurar Django primeiro
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controle_atendimento.settings')
django_asgi_app = get_asgi_application()

# Importar routing do WebSocket após Django estar configurado
from dashboard.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
