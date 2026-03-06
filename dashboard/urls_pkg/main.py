from django.urls import include, path

from .. import integrations
from .. import tenants as tenant_views
from .. import views
from ..monitoring import HealthCheckView, MetricsView
from ..views import analytics, chat, chatbot_ai, executive, push, sla
from ..views import ticket_operations as ticket_operations_views
from ..views import workflow_builder as workflow_builder_views

app_name = "dashboard"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="index"),
    path("home/", views.DashboardView.as_view(), name="dashboard"),  # Alias para dashboard
    path("general/", views.DashboardView.as_view(), name="general_dashboard"),  # Dashboard geral
    path("profile/", views.ProfileView.as_view(), name="profile"),
    # Sistema de Tickets
    path("tickets/", views.TicketListView.as_view(), name="ticket_list"),
    path("tickets/kanban/", views.KanbanBoardView.as_view(), name="ticket_kanban"),
    path("tickets/novo/", views.TicketCreateView.as_view(), name="ticket_create"),
    path("tickets/<int:pk>/", views.TicketDetailView.as_view(), name="ticket_detail"),
    path("tickets/<int:pk>/editar/", views.TicketUpdateView.as_view(), name="ticket_update"),
    path("tickets/<int:ticket_id>/interacao/", views.add_interaction, name="add_interaction"),
    # Monitoramento
    path("health/", HealthCheckView.as_view(), name="health_check"),
    path("metrics/", MetricsView.as_view(), name="metrics"),
    # API para filtros
    path("api/tickets-chart/", views.tickets_chart_api, name="tickets_chart_api"),
    # Dashboard do Agente
    path("agente/", views.AgenteDashboardView.as_view(), name="agente_dashboard"),
    path("agente/tickets/", views.AgenteTicketsView.as_view(), name="agente_tickets"),
    # Dashboard Administrativo
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    # Portal do Cliente
    path("cliente/", views.ClientePortalView.as_view(), name="cliente_portal"),
    path("cliente/tickets/", views.ClienteTicketsView.as_view(), name="cliente_tickets"),
    # Gestão de Clientes (Admin)
    path("clientes/", views.ClienteListView.as_view(), name="cliente_list"),
    path("clientes/novo/", views.ClienteCreateView.as_view(), name="cliente_create"),
    path("clientes/<int:pk>/", views.cliente_detail_view, name="cliente_detail"),
    path("clientes/<int:pk>/editar/", views.ClienteUpdateView.as_view(), name="cliente_update"),
    path("clientes/<int:pk>/excluir/", views.cliente_delete_view, name="cliente_delete"),
    # Pontos de Venda
    path("pontosdevenda/", views.PontoDeVendaListView.as_view(), name="pontodevenda_list"),
    path("pontosdevenda/novo/", views.PontoDeVendaCreateView.as_view(), name="pontodevenda_create"),
    path("pontosdevenda/<int:pk>/", views.PontoDeVendaDetailView.as_view(), name="pontodevenda_detail"),
    path("pontosdevenda/<int:pk>/editar/", views.PontoDeVendaUpdateView.as_view(), name="pontodevenda_update"),
    # APIs AJAX
    path("api/tickets/status/", views.update_ticket_status, name="update_ticket_status"),
    path("api/agente/status/", views.update_agent_status, name="update_agent_status"),
    path("api/metrics/", views.ajax_metrics, name="ajax_metrics"),
    path("api/cliente/stats/", views.cliente_stats_ajax, name="cliente_stats_ajax"),
    path("api/pontos-de-venda/", views.api_pontos_de_venda_por_cliente, name="api_pdv_por_cliente"),
    # APIs para Itens de Atendimento
    path("api/produtos-ativos/", views.api_produtos_ativos, name="api_produtos_ativos"),
    path("api/ticket-itens/add/", views.api_add_item_atendimento, name="api_add_item_atendimento"),
    path("api/ticket-itens/<int:ticket_id>/", views.api_listar_itens_atendimento, name="api_listar_itens_atendimento"),
    path(
        "api/ticket-itens/<int:item_id>/remove/",
        views.api_remover_item_atendimento,
        name="api_remover_item_atendimento",
    ),
    path(
        "api/ticket-financeiro/<int:ticket_id>/",
        views.api_estatisticas_financeiras_ticket,
        name="api_estatisticas_financeiras_ticket",
    ),
    # Relatórios
    path("relatorios/itens-atendimento/", views.relatorio_itens_atendimento, name="relatorio_itens_atendimento"),
    path("export/tickets/", views.export_tickets, name="export_tickets"),
    # ========== FUNCIONALIDADES AVANÇADAS ==========
    # SLA Management System
    path("sla/", sla.sla_dashboard, name="sla_dashboard"),
    path("sla/policies/", sla.sla_policies, name="sla_policies"),
    path("sla/reports/", sla.sla_reports, name="sla_reports"),
    # SLA APIs
    path("api/sla/dashboard/", sla.api_sla_dashboard_data, name="api_sla_dashboard_data"),
    path("api/sla/policies/", sla.api_create_sla_policy, name="api_create_sla_policy"),
    path("api/sla/alerts/<int:alert_id>/resolve/", sla.api_resolve_sla_alert, name="api_resolve_sla_alert"),
    path("api/sla/monitor/run/", sla.api_run_sla_monitor, name="api_run_sla_monitor"),
    path("api/sla/tickets/<int:ticket_id>/", sla.api_ticket_sla_details, name="api_ticket_sla_details"),
    # Real-time Notifications
    path("notifications/", views.notifications_list, name="notifications"),
    path("api/notifications/recent/", views.api_notifications_recent, name="api_notifications_recent"),
    path(
        "api/notifications/<int:notification_id>/mark-read/",
        views.api_notification_mark_read,
        name="api_notification_mark_read",
    ),
    path(
        "api/notifications/<int:notification_id>/delete/", views.api_notification_delete, name="api_notification_delete"
    ),
    path(
        "api/notifications/mark-all-read/",
        views.api_notifications_mark_all_read,
        name="api_notifications_mark_all_read",
    ),
    # ========== SISTEMA DE CHAT AVANÇADO ==========
    # Chat Dashboard e Interface
    path("chat/", chat.chat_dashboard, name="chat_dashboard"),
    path("chat/<uuid:room_id>/", chat.chat_room, name="chat_room"),
    path("chat/create/", chat.create_chat_room, name="create_chat_room"),
    path("chat/<uuid:room_id>/history/", chat.chat_history, name="chat_history"),
    path("chat/settings/", chat.chat_settings_view, name="chat_settings"),
    # Chat APIs
    path("api/chat/send/", chat.api_send_message, name="api_send_message"),
    path("api/chat/<uuid:room_id>/participants/", chat.api_room_participants, name="api_room_participants"),
    path("api/chat/recent-rooms/", chat.api_recent_rooms, name="api_recent_rooms"),
    path(
        "api/chat/<uuid:room_id>/create-ticket/", chat.api_create_ticket_from_chat, name="api_create_ticket_from_chat"
    ),
    # ChatBot Configuration
    path("chatbot/settings/", chat.chatbot_settings, name="chatbot_settings"),
    # AI Chatbot Interface
    path("chatbot/", views.chatbot_interface, name="chatbot"),
    path("chatbot/api/", views.chatbot_api, name="chatbot_api"),
    # Automation Engine
    path("automation/", views.automation_dashboard, name="automation"),
    path("automation/rules/", views.automation_rules, name="automation_rules"),
    path("automation/workflows/", views.automation_workflows, name="automation_workflows"),
    # Visual Workflow Builder
    path("workflows/builder/", workflow_builder_views.workflow_builder_view, name="workflow_builder"),
    path("api/workflows/catalog/", workflow_builder_views.api_workflow_catalog, name="api_workflow_catalog"),
    path("api/workflows/", workflow_builder_views.api_workflow_list, name="api_workflow_list"),
    path("api/workflows/create/", workflow_builder_views.api_workflow_create, name="api_workflow_create"),
    path("api/workflows/<int:pk>/update/", workflow_builder_views.api_workflow_update, name="api_workflow_update"),
    path("api/workflows/<int:pk>/delete/", workflow_builder_views.api_workflow_delete, name="api_workflow_delete"),
    path("api/workflows/<int:pk>/toggle/", workflow_builder_views.api_workflow_toggle, name="api_workflow_toggle"),
    path(
        "api/workflows/<int:pk>/duplicate/",
        workflow_builder_views.api_workflow_duplicate,
        name="api_workflow_duplicate",
    ),
    path(
        "api/workflows/from-template/",
        workflow_builder_views.api_workflow_from_template,
        name="api_workflow_from_template",
    ),
    path("api/workflows/validate/", workflow_builder_views.api_workflow_validate, name="api_workflow_validate"),
    path("api/workflows/metrics/", workflow_builder_views.api_workflow_metrics, name="api_workflow_metrics"),
    # Ticket Operations — Merge / Split / Parent-Child
    path("api/tickets/merge/", ticket_operations_views.api_merge_tickets, name="api_merge_tickets"),
    path("api/tickets/split/", ticket_operations_views.api_split_ticket, name="api_split_ticket"),
    path("api/tickets/<int:pk>/sub-tickets/", ticket_operations_views.api_add_sub_ticket, name="api_add_sub_ticket"),
    path(
        "api/tickets/<int:pk>/sub-tickets/remove/",
        ticket_operations_views.api_remove_sub_ticket,
        name="api_remove_sub_ticket",
    ),
    path("api/tickets/<int:pk>/hierarchy/", ticket_operations_views.api_ticket_hierarchy, name="api_ticket_hierarchy"),
    path("api/tickets/<int:pk>/link/", ticket_operations_views.api_link_tickets, name="api_link_tickets"),
    # Multi-tenancy
    path("api/tenant/", tenant_views.api_tenant_info, name="api_tenant_info"),
    path("api/tenant/members/", tenant_views.api_tenant_members, name="api_tenant_members"),
    path("api/tenant/invite/", tenant_views.api_tenant_invite, name="api_tenant_invite"),
    path("api/tenant/switch/", tenant_views.api_switch_tenant, name="api_switch_tenant"),
    path("api/tenants/", tenant_views.api_user_tenants, name="api_user_tenants"),
    # User management (admin/staff)
    path("users/", views.UserListView.as_view(), name="user_list"),
    path("users/novo/", views.UserCreateView.as_view(), name="user_create"),
    # Advanced Reports
    path("reports/", views.reports_dashboard, name="reports"),
    path("reports/generate/", views.generate_report, name="generate_report"),
    path("reports/download/<str:report_id>/", views.download_report, name="download_report"),
    path("reports/custom/", views.custom_reports, name="custom_reports"),
    # Search Advanced
    path("search/", views.advanced_search, name="search"),
    path("search/suggest/", views.search_suggestions, name="search_suggestions"),
    # PWA Views
    path("pwa/", views.pwa_info, name="pwa_info"),
    path("pwa/install/", views.pwa_install_guide, name="pwa_install_guide"),
    # Push Notifications API
    path("api/push/public-key/", push.get_public_key, name="push_public_key"),
    path("api/push/subscribe/", push.subscribe_push, name="push_subscribe"),
    path("api/push/unsubscribe/", push.unsubscribe_push, name="push_unsubscribe"),
    path("api/push/preferences/", push.update_preferences, name="push_preferences"),
    path("api/push/test/", push.test_notification, name="push_test"),
    # Analytics Avançado
    path("analytics/", analytics.analytics_dashboard, name="analytics_dashboard"),
    # Dashboard Executivo
    path("executive/", executive.executive_dashboard, name="executive_dashboard"),
    # APIs do Dashboard Executivo
    path("api/executive-kpis/", executive.executive_kpis_api, name="executive_kpis_api"),
    path("api/executive-charts/", executive.executive_charts_api, name="executive_charts_api"),
    path("api/executive-alerts/", executive.executive_alerts_api, name="executive_alerts_api"),
    # Chatbot IA
    path("chatbot-ai/", chatbot_ai.chatbot_interface, name="chatbot_ai_interface"),
    path("chatbot-ai/dashboard/", chatbot_ai.chatbot_dashboard, name="chatbot_ai_dashboard"),
    path("chatbot-ai/knowledge/", chatbot_ai.chatbot_knowledge_base, name="chatbot_ai_knowledge"),
    path("chatbot-ai/conversations/", chatbot_ai.chatbot_conversations, name="chatbot_ai_conversations"),
    path(
        "chatbot-ai/conversation/<uuid:conversation_id>/",
        chatbot_ai.chatbot_conversation_detail,
        name="chatbot_ai_conversation_detail",
    ),
    path("chatbot-ai/settings/", chatbot_ai.chatbot_settings, name="chatbot_ai_settings"),
    # APIs do Chatbot IA
    path("api/chatbot/", chatbot_ai.chatbot_api, name="chatbot_ai_api"),
    path("api/chatbot/feedback/", chatbot_ai.chatbot_feedback, name="chatbot_ai_feedback"),
    path("api/chatbot/add-knowledge/", chatbot_ai.chatbot_add_knowledge, name="chatbot_ai_add_knowledge"),
    path(
        "api/chatbot/create-ticket/",
        chatbot_ai.chatbot_create_ticket_from_conversation,
        name="chatbot_ai_create_ticket",
    ),
    path("api/chatbot/analytics/", chatbot_ai.chatbot_analytics_api, name="chatbot_ai_analytics"),
    # WhatsApp Business
    path("whatsapp/", include("dashboard.urls.whatsapp")),
    # Central de Comunicação Unificada
    path("communication/", views.communication_center, name="communication_center"),
    # Webhooks para Integrações
    path("webhooks/whatsapp/", integrations.whatsapp_webhook, name="whatsapp_webhook"),
    path("webhooks/slack/", integrations.slack_webhook, name="slack_webhook"),
]

# URLs Mobile - Namespace separado
from ..views import mobile as mobile_views

mobile_urlpatterns = [
    path("", mobile_views.mobile_dashboard, name="dashboard"),
    path("tickets/", mobile_views.mobile_ticket_list, name="ticket_list"),
    path("tickets/novo/", mobile_views.mobile_create_ticket, name="create_ticket"),
    path("ticket/<int:ticket_id>/", mobile_views.mobile_ticket_detail, name="ticket_detail"),
    path("ticket/<int:ticket_id>/status/", mobile_views.mobile_ticket_status_update, name="ticket_status_update"),
    path("ticket/<int:ticket_id>/comment/", mobile_views.mobile_ticket_comment, name="ticket_comment"),
    path("ticket/<int:ticket_id>/upload-photo/", mobile_views.mobile_ticket_upload_photo, name="ticket_upload_photo"),
    path("tickets/check-updates/", mobile_views.mobile_tickets_check_updates, name="tickets_check_updates"),
    path("chat/", mobile_views.mobile_chat, name="chat"),
]
