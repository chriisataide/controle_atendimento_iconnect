"""
Pacote de views do dashboard.

Módulos:
    dashboard          - DashboardView, admin_dashboard, métricas AJAX
    tickets            - CRUD de tickets, Kanban, dashboard do agente
    clientes           - Portal do cliente, CRUD de clientes
    auth_profile       - Autenticação, perfil, gestão de usuários, pontos de venda
    notifications      - Centro de notificações e APIs
    automation         - Motor de automação e workflows
    features           - Relatórios, busca, PWA, chatbot, comunicação
    itens_atendimento  - APIs de itens de atendimento e relatório financeiro
    analytics          - Views de analytics
    chat               - Views de chat em tempo real
    chatbot_ai         - Views do chatbot IA
    equipamentos       - CRUD de equipamentos
    estoque            - CRUD de estoque
    executive          - Dashboard executivo
    financeiro         - Módulo financeiro
    mobile             - Views mobile
    push               - Push notifications
    sla                - Gestão de SLA
    ticket_operations  - Merge, split, sub-tickets
    api                - API REST views
    whatsapp           - Integração WhatsApp
    workflow_builder   - Construtor visual de workflows
    helpers            - Funções auxiliares
"""

# Compliance — Auditoria e LGPD
from .compliance import (
    AuditTrailView,
    LGPDPanelView,
    audit_export_csv,
    lgpd_process_request,
)

# Macros — Respostas Rápidas
from .banking_features import (
    macros_list,
    macro_create,
    macro_delete,
)

# Autenticação, perfil, usuários, pontos de venda
from .auth_profile import (
    PontoDeVendaCreateView,
    PontoDeVendaDetailView,
    PontoDeVendaForm,
    PontoDeVendaListView,
    PontoDeVendaUpdateView,
    ProfileView,
    UserCreateView,
    UserDeleteView,
    UserListView,
    UserUpdateView,
    api_pontos_de_venda_por_cliente,
    custom_login,
    custom_logout,
    get_user_info,
    update_agent_status,
)

# Automação
from .automation import (
    automation_dashboard,
    automation_rules,
    automation_workflows,
)

# Clientes: portal, CRUD, stats
from .clientes import (
    ClienteCreateView,
    ClienteListView,
    ClientePortalView,
    ClienteTicketsView,
    ClienteUpdateView,
    cliente_delete_view,
    cliente_detail_view,
    cliente_stats_ajax,
)

# Dashboard principal e métricas
from .dashboard import (
    DashboardView,
    admin_dashboard,
    ajax_metrics,
    home_redirect,
    tickets_chart_api,
)

# Funcionalidades diversas
from .features import (
    advanced_search,
    chat_interface,
    chatbot_api,
    chatbot_interface,
    chatbot_stats_api,
    communication_center,
    custom_reports,
    download_report,
    export_tickets,
    generate_report,
    manifest,
    pwa_info,
    pwa_install_guide,
    reports_dashboard,
    search_suggestions,
    service_worker,
)

# Itens de atendimento
from .itens_atendimento import (
    api_add_item_atendimento,
    api_estatisticas_financeiras_ticket,
    api_listar_itens_atendimento,
    api_produtos_ativos,
    api_remover_item_atendimento,
    relatorio_itens_atendimento,
)

# Notificações
from .notifications import (
    api_notification_delete,
    api_notification_mark_read,
    api_notifications_mark_all_read,
    api_notifications_recent,
    mark_notification_read,
    notifications_center,
    notifications_list,
)

# CRUD de tickets, Kanban, agente
from .tickets import (
    AgenteDashboardView,
    AgenteTicketsView,
    KanbanBoardView,
    TicketCreateView,
    TicketDetailView,
    TicketListView,
    TicketUpdateView,
    add_interaction,
    kanban_update_status,
    update_ticket_status,
)

__all__ = [
    # Dashboard
    "DashboardView",
    "admin_dashboard",
    "home_redirect",
    "ajax_metrics",
    "tickets_chart_api",
    # Tickets
    "KanbanBoardView",
    "TicketListView",
    "TicketDetailView",
    "TicketCreateView",
    "TicketUpdateView",
    "add_interaction",
    "update_ticket_status",
    "AgenteDashboardView",
    "AgenteTicketsView",
    # Clientes
    "ClientePortalView",
    "ClienteTicketsView",
    "ClienteListView",
    "ClienteCreateView",
    "ClienteUpdateView",
    "cliente_detail_view",
    "cliente_delete_view",
    "cliente_stats_ajax",
    # Auth/Profile
    "PontoDeVendaForm",
    "PontoDeVendaListView",
    "PontoDeVendaCreateView",
    "PontoDeVendaDetailView",
    "PontoDeVendaUpdateView",
    "api_pontos_de_venda_por_cliente",
    "UserListView",
    "UserCreateView",
    "UserUpdateView",
    "UserDeleteView",
    "custom_login",
    "custom_logout",
    "get_user_info",
    "ProfileView",
    "update_agent_status",
    # Notifications
    "notifications_center",
    "mark_notification_read",
    "api_notifications_recent",
    "api_notification_mark_read",
    "api_notifications_mark_all_read",
    "api_notification_delete",
    "notifications_list",
    # Automation
    "automation_dashboard",
    "automation_rules",
    "automation_workflows",
    # Features
    "chatbot_interface",
    "chatbot_api",
    "chatbot_stats_api",
    "chat_interface",
    "reports_dashboard",
    "generate_report",
    "download_report",
    "custom_reports",
    "advanced_search",
    "search_suggestions",
    "pwa_info",
    "pwa_install_guide",
    "manifest",
    "service_worker",
    "communication_center",
    "export_tickets",
    # Itens de Atendimento
    "api_produtos_ativos",
    "api_add_item_atendimento",
    "api_listar_itens_atendimento",
    "api_remover_item_atendimento",
    "relatorio_itens_atendimento",
    "api_estatisticas_financeiras_ticket",
    # Compliance
    "AuditTrailView",
    "LGPDPanelView",
    "audit_export_csv",
    "lgpd_process_request",
    # Macros
    "macros_list",
    "macro_create",
    "macro_delete",
]
