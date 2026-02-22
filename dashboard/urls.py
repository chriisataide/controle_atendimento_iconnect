from django.urls import path, include
from . import views, integrations, sla_views, chat_views, push_views, executive_views, chatbot_ai_views, analytics_views
from .monitoring import HealthCheckView, MetricsView

app_name = 'dashboard'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='index'),
    path('home/', views.DashboardView.as_view(), name='dashboard'),  # Alias para dashboard
    path('general/', views.DashboardView.as_view(), name='general_dashboard'),  # Dashboard geral
    path('profile/', views.ProfileView.as_view(), name='profile'),
    
    # Sistema de Tickets
    path('tickets/', views.TicketListView.as_view(), name='ticket_list'),
    path('tickets/kanban/', views.KanbanBoardView.as_view(), name='ticket_kanban'),
    path('tickets/novo/', views.TicketCreateView.as_view(), name='ticket_create'),
    path('tickets/<int:pk>/', views.TicketDetailView.as_view(), name='ticket_detail'),
    path('tickets/<int:pk>/editar/', views.TicketUpdateView.as_view(), name='ticket_update'),
    path('tickets/<int:ticket_id>/interacao/', views.add_interaction, name='add_interaction'),
    
    # Monitoramento
    path('health/', HealthCheckView.as_view(), name='health_check'),
    path('metrics/', MetricsView.as_view(), name='metrics'),
    
    # API para filtros
    path('api/tickets-chart/', views.tickets_chart_api, name='tickets_chart_api'),
    
    # Dashboard do Agente
    path('agente/', views.AgenteDashboardView.as_view(), name='agente_dashboard'),
    path('agente/tickets/', views.AgenteTicketsView.as_view(), name='agente_tickets'),
    
    # Dashboard Administrativo
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    
    # Portal do Cliente
    path('cliente/', views.ClientePortalView.as_view(), name='cliente_portal'),
    path('cliente/tickets/', views.ClienteTicketsView.as_view(), name='cliente_tickets'),
    
    # Gestão de Clientes (Admin)
    path('clientes/', views.ClienteListView.as_view(), name='cliente_list'),
    path('clientes/novo/', views.ClienteCreateView.as_view(), name='cliente_create'),
    path('clientes/<int:pk>/', views.cliente_detail_view, name='cliente_detail'),
    path('clientes/<int:pk>/editar/', views.ClienteUpdateView.as_view(), name='cliente_update'),
    path('clientes/<int:pk>/excluir/', views.cliente_delete_view, name='cliente_delete'),

    # Pontos de Venda
    path('pontosdevenda/', views.PontoDeVendaListView.as_view(), name='pontodevenda_list'),
    path('pontosdevenda/novo/', views.PontoDeVendaCreateView.as_view(), name='pontodevenda_create'),
    path('pontosdevenda/<int:pk>/', views.PontoDeVendaDetailView.as_view(), name='pontodevenda_detail'),
    path('pontosdevenda/<int:pk>/editar/', views.PontoDeVendaUpdateView.as_view(), name='pontodevenda_update'),
    
    # APIs AJAX
    path('api/tickets/status/', views.update_ticket_status, name='update_ticket_status'),
    path('api/agente/status/', views.update_agent_status, name='update_agent_status'),
    path('api/metrics/', views.ajax_metrics, name='ajax_metrics'),
    path('api/cliente/stats/', views.cliente_stats_ajax, name='cliente_stats_ajax'),
    
    # APIs para Itens de Atendimento
    path('api/produtos-ativos/', views.api_produtos_ativos, name='api_produtos_ativos'),
    path('api/ticket-itens/add/', views.api_add_item_atendimento, name='api_add_item_atendimento'),
    path('api/ticket-itens/<int:ticket_id>/', views.api_listar_itens_atendimento, name='api_listar_itens_atendimento'),
    path('api/ticket-itens/<int:item_id>/remove/', views.api_remover_item_atendimento, name='api_remover_item_atendimento'),
    path('api/ticket-financeiro/<int:ticket_id>/', views.api_estatisticas_financeiras_ticket, name='api_estatisticas_financeiras_ticket'),
    
    # Relatórios
    path('relatorios/itens-atendimento/', views.relatorio_itens_atendimento, name='relatorio_itens_atendimento'),
    
    path('export/tickets/', views.export_tickets, name='export_tickets'),
    
    # ========== FUNCIONALIDADES AVANÇADAS ==========
    
    # SLA Management System
    path('sla/test/', sla_views.sla_test, name='sla_test'),  # URL de teste temporária
    path('sla/demo/', sla_views.sla_dashboard_public, name='sla_dashboard_public'),  # Dashboard público temporário
    path('sla/', sla_views.sla_dashboard, name='sla_dashboard'),
    path('sla/policies/', sla_views.sla_policies, name='sla_policies'),
    path('sla/alerts/', sla_views.sla_alerts, name='sla_alerts'),
    path('sla/reports/', sla_views.sla_reports, name='sla_reports'),
    
    # SLA APIs
    path('api/sla/dashboard/', sla_views.api_sla_dashboard_data, name='api_sla_dashboard_data'),
    path('api/sla/policies/', sla_views.api_create_sla_policy, name='api_create_sla_policy'),
    path('api/sla/alerts/<int:alert_id>/resolve/', sla_views.api_resolve_sla_alert, name='api_resolve_sla_alert'),
    path('api/sla/monitor/run/', sla_views.api_run_sla_monitor, name='api_run_sla_monitor'),
    path('api/sla/tickets/<int:ticket_id>/', sla_views.api_ticket_sla_details, name='api_ticket_sla_details'),
    
    # Real-time Notifications
    path('notifications/', views.notifications_list, name='notifications'),
    path('api/notifications/recent/', views.api_notifications_recent, name='api_notifications_recent'),
    path('api/notifications/<int:notification_id>/mark-read/', views.api_notification_mark_read, name='api_notification_mark_read'),
    path('api/notifications/<int:notification_id>/delete/', views.api_notification_delete, name='api_notification_delete'),
    path('api/notifications/mark-all-read/', views.api_notifications_mark_all_read, name='api_notifications_mark_all_read'),
    
    # ========== SISTEMA DE CHAT AVANÇADO ==========
    
    # Chat Dashboard e Interface
    path('chat/', chat_views.chat_dashboard, name='chat_dashboard'),
    path('chat/<uuid:room_id>/', chat_views.chat_room, name='chat_room'),
    path('chat/create/', chat_views.create_chat_room, name='create_chat_room'),
    path('chat/<uuid:room_id>/history/', chat_views.chat_history, name='chat_history'),
    path('chat/settings/', chat_views.chat_settings_view, name='chat_settings'),
    
    # Chat APIs
    path('api/chat/send/', chat_views.api_send_message, name='api_send_message'),
    path('api/chat/<uuid:room_id>/participants/', chat_views.api_room_participants, name='api_room_participants'),
    path('api/chat/recent-rooms/', chat_views.api_recent_rooms, name='api_recent_rooms'),
    path('api/chat/<uuid:room_id>/create-ticket/', chat_views.api_create_ticket_from_chat, name='api_create_ticket_from_chat'),
    
    # ChatBot Configuration
    path('chatbot/settings/', chat_views.chatbot_settings, name='chatbot_settings'),
    
    # AI Chatbot Interface
    path('chatbot/', views.chatbot_interface, name='chatbot'),
    path('chatbot/api/', views.chatbot_api, name='chatbot_api'),
    
    # Automation Engine
    path('automation/', views.automation_dashboard, name='automation'),
    path('automation/rules/', views.automation_rules, name='automation_rules'),
    path('automation/workflows/', views.automation_workflows, name='automation_workflows'),

    # User management (admin/staff)
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/novo/', views.UserCreateView.as_view(), name='user_create'),
    
    # Advanced Reports
    path('reports/', views.reports_dashboard, name='reports'),
    path('reports/generate/', views.generate_report, name='generate_report'),
    path('reports/download/<str:report_id>/', views.download_report, name='download_report'),
    path('reports/custom/', views.custom_reports, name='custom_reports'),
    
    # Search Advanced
    path('search/', views.advanced_search, name='search'),
    path('search/suggest/', views.search_suggestions, name='search_suggestions'),
    
    # PWA Views
    path('pwa/', views.pwa_info, name='pwa_info'),
    path('pwa/install/', views.pwa_install_guide, name='pwa_install_guide'),
    
    # Push Notifications API
    path('api/push/public-key/', push_views.get_public_key, name='push_public_key'),
    path('api/push/subscribe/', push_views.subscribe_push, name='push_subscribe'),
    path('api/push/unsubscribe/', push_views.unsubscribe_push, name='push_unsubscribe'),
    path('api/push/preferences/', push_views.update_preferences, name='push_preferences'),
    path('api/push/test/', push_views.test_notification, name='push_test'),
    
    # Analytics Avançado
    path('analytics/', analytics_views.analytics_dashboard, name='analytics_dashboard'),
    
    # Dashboard Executivo
    path('executive/', executive_views.executive_dashboard, name='executive_dashboard'),
    
    # APIs do Dashboard Executivo
    path('api/executive-kpis/', executive_views.executive_kpis_api, name='executive_kpis_api'),
    path('api/executive-charts/', executive_views.executive_charts_api, name='executive_charts_api'),
    path('api/executive-alerts/', executive_views.executive_alerts_api, name='executive_alerts_api'),
    
    # Chatbot IA
    path('chatbot-ai/', chatbot_ai_views.chatbot_interface, name='chatbot_ai_interface'),
    path('chatbot-ai/dashboard/', chatbot_ai_views.chatbot_dashboard, name='chatbot_ai_dashboard'),
    path('chatbot-ai/knowledge/', chatbot_ai_views.chatbot_knowledge_base, name='chatbot_ai_knowledge'),
    path('chatbot-ai/conversations/', chatbot_ai_views.chatbot_conversations, name='chatbot_ai_conversations'),
    path('chatbot-ai/conversation/<uuid:conversation_id>/', chatbot_ai_views.chatbot_conversation_detail, name='chatbot_ai_conversation_detail'),
    path('chatbot-ai/settings/', chatbot_ai_views.chatbot_settings, name='chatbot_ai_settings'),
    
    # APIs do Chatbot IA
    path('api/chatbot/', chatbot_ai_views.chatbot_api, name='chatbot_ai_api'),
    path('api/chatbot/feedback/', chatbot_ai_views.chatbot_feedback, name='chatbot_ai_feedback'),
    path('api/chatbot/add-knowledge/', chatbot_ai_views.chatbot_add_knowledge, name='chatbot_ai_add_knowledge'),
    path('api/chatbot/create-ticket/', chatbot_ai_views.chatbot_create_ticket_from_conversation, name='chatbot_ai_create_ticket'),
    path('api/chatbot/analytics/', chatbot_ai_views.chatbot_analytics_api, name='chatbot_ai_analytics'),
    
    # WhatsApp Business
    path('whatsapp/', include('dashboard.whatsapp_urls')),
    
    # Central de Comunicação Unificada
    path('communication/', views.communication_center, name='communication_center'),
    
    # Webhooks para Integrações
    path('webhooks/whatsapp/', integrations.whatsapp_webhook, name='whatsapp_webhook'),
    path('webhooks/slack/', integrations.slack_webhook, name='slack_webhook'),
]

# URLs Mobile - Namespace separado
from . import mobile_views

mobile_urlpatterns = [
    path('', mobile_views.mobile_dashboard, name='dashboard'),
    path('tickets/', mobile_views.mobile_ticket_list, name='ticket_list'),
    path('tickets/novo/', mobile_views.mobile_create_ticket, name='create_ticket'),
    path('ticket/<int:ticket_id>/', mobile_views.mobile_ticket_detail, name='ticket_detail'),
    path('ticket/<int:ticket_id>/status/', mobile_views.mobile_ticket_status_update, name='ticket_status_update'),
    path('ticket/<int:ticket_id>/comment/', mobile_views.mobile_ticket_comment, name='ticket_comment'),
    path('ticket/<int:ticket_id>/upload-photo/', mobile_views.mobile_ticket_upload_photo, name='ticket_upload_photo'),
    path('tickets/check-updates/', mobile_views.mobile_tickets_check_updates, name='tickets_check_updates'),
    path('chat/', mobile_views.mobile_chat, name='chat'),
]
