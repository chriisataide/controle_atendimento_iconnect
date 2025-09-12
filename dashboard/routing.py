"""
WebSocket Routing para Sistema de Notificações e Chat em Tempo Real
iConnect - Sistema de Atendimento
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Notificações gerais do usuário
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
    
    # Chat específico de ticket
    re_path(r'ws/tickets/(?P<ticket_id>\w+)/$', consumers.TicketChatConsumer.as_asgi()),
    
    # Sistema de Chat Avançado
    re_path(r'ws/chat/(?P<room_id>[0-9a-f-]+)/$', consumers.ChatConsumer.as_asgi()),
    
    # Dashboard em tempo real
    re_path(r'ws/dashboard/$', consumers.DashboardConsumer.as_asgi()),
    
    # Status de agentes
    re_path(r'ws/agent-status/$', consumers.AgentStatusConsumer.as_asgi()),
]
