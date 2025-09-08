from django.urls import path
from . import views, integrations

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
    
    # ========== FUNCIONALIDADES AVANÇADAS ATIVADAS ==========
    
    # Webhooks para Integrações
    path('webhooks/whatsapp/', integrations.whatsapp_webhook, name='whatsapp_webhook'),
    path('webhooks/slack/', integrations.slack_webhook, name='slack_webhook'),
]
