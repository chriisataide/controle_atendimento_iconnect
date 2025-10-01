from django.urls import path
from . import whatsapp_views

app_name = 'whatsapp'

urlpatterns = [
    # Dashboard principal
    path('', whatsapp_views.whatsapp_dashboard, name='dashboard'),
    
    # Conversas
    path('conversations/', whatsapp_views.whatsapp_conversations, name='conversations'),
    path('conversations/<uuid:uuid>/', whatsapp_views.whatsapp_conversation_detail, name='conversation_detail'),
    
    # Contatos
    path('contacts/', whatsapp_views.whatsapp_contacts, name='contacts'),
    
    # Templates
    path('templates/', whatsapp_views.whatsapp_templates, name='templates'),
    
    # Respostas automáticas
    path('auto-responses/', whatsapp_views.whatsapp_auto_responses, name='auto_responses'),
    
    # Analytics
    path('analytics/', whatsapp_views.whatsapp_analytics, name='analytics'),
    
    # Webhook
    path('webhook/', whatsapp_views.whatsapp_webhook, name='webhook'),
    
    # API endpoints
    path('api/send-message/', whatsapp_views.whatsapp_api_send_message, name='api_send_message'),
    path('api/conversation/<uuid:uuid>/messages/', whatsapp_views.whatsapp_api_conversation_messages, name='api_conversation_messages'),
    path('api/stats/', whatsapp_views.whatsapp_api_stats, name='api_stats'),
]