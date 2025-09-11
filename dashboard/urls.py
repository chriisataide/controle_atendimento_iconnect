from django.urls import path
from . import views, integrations
from .monitoring import HealthCheckView, MetricsView

app_name = 'dashboard'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='index'),
    path('home/', views.DashboardView.as_view(), name='dashboard'),  # Alias para dashboard
    path('general/', views.DashboardView.as_view(), name='general_dashboard'),  # Dashboard geral
    path('profile/', views.ProfileView.as_view(), name='profile'),
    
    # Sistema de Tickets
    path('tickets/', views.TicketListView.as_view(), name='ticket_list'),
    path('tickets/novo/', views.TicketCreateView.as_view(), name='ticket_create'),
    path('tickets/<int:pk>/', views.TicketDetailView.as_view(), name='ticket_detail'),
    path('tickets/<int:pk>/editar/', views.TicketUpdateView.as_view(), name='ticket_update'),
    path('tickets/<int:ticket_id>/interacao/', views.add_interaction, name='add_interaction'),
    
    # Monitoramento
    path('health/', HealthCheckView.as_view(), name='health_check'),
    path('metrics/', MetricsView.as_view(), name='metrics'),
    
    # Dashboard do Agente
    path('agente/', views.AgenteDashboardView.as_view(), name='agente_dashboard'),
    path('agente/tickets/', views.AgenteTicketsView.as_view(), name='agente_tickets'),
    
    # Dashboard Administrativo
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    
    # Portal do Cliente
    path('cliente/', views.ClientePortalView.as_view(), name='cliente_portal'),
    path('cliente/tickets/', views.ClienteTicketsView.as_view(), name='cliente_tickets'),
    
    # APIs AJAX
    path('api/tickets/status/', views.update_ticket_status, name='update_ticket_status'),
    path('api/agente/status/', views.update_agent_status, name='update_agent_status'),
    path('api/metrics/', views.ajax_metrics, name='ajax_metrics'),
    path('api/cliente/stats/', views.cliente_stats_ajax, name='cliente_stats_ajax'),
    path('export/tickets/', views.export_tickets, name='export_tickets'),
    
    # ========== FUNCIONALIDADES AVANÇADAS ==========
    
    # Analytics Dashboard
    path('analytics/', views.analytics_dashboard, name='analytics'),
    path('analytics/data/', views.analytics_data_view, name='analytics_data'),
    
    # Real-time Notifications
    path('notifications/', views.notifications_center, name='notifications'),
    path('notifications/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    
    # AI Chatbot Interface
    path('chatbot/', views.chatbot_interface, name='chatbot'),
    path('chatbot/api/', views.chatbot_api, name='chatbot_api'),
    path('chat/', views.chat_interface, name='chat'),
    
    # Automation Engine
    path('automation/', views.automation_dashboard, name='automation'),
    path('automation/rules/', views.automation_rules, name='automation_rules'),
    path('automation/workflows/', views.automation_workflows, name='automation_workflows'),
    
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
    
    # Webhooks para Integrações
    path('webhooks/whatsapp/', integrations.whatsapp_webhook, name='whatsapp_webhook'),
    path('webhooks/slack/', integrations.slack_webhook, name='slack_webhook'),
]
