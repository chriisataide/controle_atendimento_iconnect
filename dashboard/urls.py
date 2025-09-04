from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='index'),
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
    
    # Portal do Cliente
    path('cliente/', views.ClientePortalView.as_view(), name='cliente_portal'),
    path('cliente/tickets/', views.ClienteTicketsView.as_view(), name='cliente_tickets'),
    
    # APIs
    path('api/tickets/status/', views.update_ticket_status, name='update_ticket_status'),
    path('api/agente/status/', views.update_agent_status, name='update_agent_status'),
]
