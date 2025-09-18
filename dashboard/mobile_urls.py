"""
URLs para interface mobile do iConnect - Técnicos de Campo
"""

from django.urls import path
from . import mobile_views

app_name = 'mobile'

urlpatterns = [
    # Dashboard Mobile para Técnicos
    path('', mobile_views.mobile_dashboard, name='mobile_dashboard'),
    
    # Gestão de Tickets Mobile
    path('tickets/', mobile_views.mobile_ticket_list, name='mobile_ticket_list'),
    path('tickets/novo/', mobile_views.mobile_create_ticket, name='mobile_create_ticket'),
    path('ticket/<int:ticket_id>/', mobile_views.mobile_ticket_detail, name='mobile_ticket_detail'),
    
    # APIs AJAX para Mobile
    path('ticket/<int:ticket_id>/status/', mobile_views.mobile_ticket_status_update, name='mobile_ticket_status_update'),
    path('ticket/<int:ticket_id>/comment/', mobile_views.mobile_ticket_comment, name='mobile_ticket_comment'),
    path('ticket/<int:ticket_id>/upload-photo/', mobile_views.mobile_ticket_upload_photo, name='mobile_ticket_upload_photo'),
    path('tickets/check-updates/', mobile_views.mobile_tickets_check_updates, name='mobile_tickets_check_updates'),
    
    # Chat
    path('chat/', mobile_views.mobile_chat, name='mobile_chat'),
    path('chat/ticket/<int:ticket_id>/', mobile_views.mobile_chat_ticket, name='mobile_chat_ticket'),
    
    # PWA
    path('offline/', mobile_views.mobile_offline, name='mobile_offline'),
    
    # Notificações
    path('notifications/', mobile_views.mobile_notifications, name='mobile_notifications'),
]
