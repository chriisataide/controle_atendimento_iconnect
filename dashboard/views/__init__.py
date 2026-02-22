"""
Pacote de views do dashboard.

Módulos:
    dashboard      - DashboardView, admin_dashboard, métricas AJAX
    tickets        - CRUD de tickets, Kanban, dashboard do agente
    clientes       - Portal do cliente, CRUD de clientes
    auth_profile   - Autenticação, perfil, gestão de usuários, pontos de venda
    notifications  - Centro de notificações e APIs
    automation     - Motor de automação e workflows
    features       - Relatórios, busca, PWA, chatbot, comunicação
    itens_atendimento - APIs de itens de atendimento e relatório financeiro
"""

# Dashboard principal e métricas
from .dashboard import (
    DashboardView,
    admin_dashboard,
    home_redirect,
    ajax_metrics,
    tickets_chart_api,
)

# CRUD de tickets, Kanban, agente
from .tickets import (
    KanbanBoardView,
    TicketListView,
    TicketDetailView,
    TicketCreateView,
    TicketUpdateView,
    add_interaction,
    update_ticket_status,
    AgenteDashboardView,
    AgenteTicketsView,
)

# Clientes: portal, CRUD, stats
from .clientes import (
    ClientePortalView,
    ClienteTicketsView,
    ClienteListView,
    ClienteCreateView,
    ClienteUpdateView,
    cliente_detail_view,
    cliente_delete_view,
    cliente_stats_ajax,
)

# Autenticação, perfil, usuários, pontos de venda
from .auth_profile import (
    PontoDeVendaForm,
    PontoDeVendaListView,
    PontoDeVendaCreateView,
    PontoDeVendaDetailView,
    PontoDeVendaUpdateView,
    UserListView,
    UserCreateView,
    custom_login,
    custom_logout,
    get_user_info,
    ProfileView,
    update_agent_status,
)

# Notificações
from .notifications import (
    notifications_center,
    mark_notification_read,
    api_notifications_recent,
    api_notification_mark_read,
    api_notifications_mark_all_read,
    api_notification_delete,
    notifications_list,
)

# Automação
from .automation import (
    automation_dashboard,
    automation_rules,
    automation_workflows,
)

# Funcionalidades diversas
from .features import (
    chatbot_interface,
    chatbot_api,
    chat_interface,
    reports_dashboard,
    generate_report,
    download_report,
    custom_reports,
    advanced_search,
    search_suggestions,
    pwa_info,
    pwa_install_guide,
    manifest,
    service_worker,
    communication_center,
    export_tickets,
)

# Itens de atendimento
from .itens_atendimento import (
    api_produtos_ativos,
    api_add_item_atendimento,
    api_listar_itens_atendimento,
    api_remover_item_atendimento,
    relatorio_itens_atendimento,
    api_estatisticas_financeiras_ticket,
)

__all__ = [
    # Dashboard
    'DashboardView', 'admin_dashboard', 'home_redirect',
    'ajax_metrics', 'tickets_chart_api',
    # Tickets
    'KanbanBoardView', 'TicketListView', 'TicketDetailView', 'TicketCreateView',
    'TicketUpdateView', 'add_interaction', 'update_ticket_status',
    'AgenteDashboardView', 'AgenteTicketsView',
    # Clientes
    'ClientePortalView', 'ClienteTicketsView', 'ClienteListView',
    'ClienteCreateView', 'ClienteUpdateView',
    'cliente_detail_view', 'cliente_delete_view', 'cliente_stats_ajax',
    # Auth/Profile
    'PontoDeVendaForm', 'PontoDeVendaListView', 'PontoDeVendaCreateView',
    'PontoDeVendaDetailView', 'PontoDeVendaUpdateView',
    'UserListView', 'UserCreateView',
    'custom_login', 'custom_logout', 'get_user_info',
    'ProfileView', 'update_agent_status',
    # Notifications
    'notifications_center', 'mark_notification_read',
    'api_notifications_recent', 'api_notification_mark_read',
    'api_notifications_mark_all_read', 'api_notification_delete',
    'notifications_list',
    # Automation
    'automation_dashboard', 'automation_rules', 'automation_workflows',
    # Features
    'chatbot_interface', 'chatbot_api', 'chat_interface',
    'reports_dashboard', 'generate_report', 'download_report', 'custom_reports',
    'advanced_search', 'search_suggestions',
    'pwa_info', 'pwa_install_guide', 'manifest', 'service_worker',
    'communication_center', 'export_tickets',
    # Itens de Atendimento
    'api_produtos_ativos', 'api_add_item_atendimento',
    'api_listar_itens_atendimento', 'api_remover_item_atendimento',
    'relatorio_itens_atendimento', 'api_estatisticas_financeiras_ticket',
]
