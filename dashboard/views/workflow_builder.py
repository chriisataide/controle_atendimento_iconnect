"""
Visual Workflow Builder — API para o editor drag-and-drop de workflows.

Fornece endpoints CRUD para regras, catálogo de condições/ações disponíveis,
validação de fluxo e execução de teste.
"""

import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from ..models import WorkflowRule
from ..services.workflows import workflow_builder, workflow_engine
from ..utils.rbac import role_required

logger = logging.getLogger("dashboard")

# ======================== CATÁLOGO ========================

CONDITION_CATALOG = [
    {
        "id": "status",
        "label": "Status do ticket",
        "type": "multi_select",
        "options": ["aberto", "em_andamento", "aguardando_cliente", "resolvido", "fechado"],
        "icon": "flag",
        "color": "#3b82f6",
    },
    {
        "id": "prioridade",
        "label": "Prioridade",
        "type": "multi_select",
        "options": ["baixa", "media", "alta", "critica"],
        "icon": "priority_high",
        "color": "#ef4444",
    },
    {
        "id": "categoria",
        "label": "Categoria",
        "type": "multi_select_dynamic",
        "source": "categorias",
        "icon": "folder",
        "color": "#8b5cf6",
    },
    {
        "id": "has_agent",
        "label": "Agente atribuído?",
        "type": "boolean",
        "icon": "person_check",
        "color": "#10b981",
    },
    {
        "id": "time_since_creation",
        "label": "Tempo desde criação",
        "type": "time_range",
        "fields": ["min_hours", "max_hours"],
        "icon": "schedule",
        "color": "#f59e0b",
    },
    {
        "id": "interaction_count",
        "label": "Número de interações",
        "type": "number_range",
        "fields": ["min", "max"],
        "icon": "chat",
        "color": "#06b6d4",
    },
]

ACTION_CATALOG = [
    {
        "id": "change_status",
        "label": "Alterar status",
        "type": "select",
        "field": "new_status",
        "options": ["aberto", "em_andamento", "aguardando_cliente", "resolvido", "fechado"],
        "icon": "swap_horiz",
        "color": "#3b82f6",
    },
    {
        "id": "change_priority",
        "label": "Alterar prioridade",
        "type": "select",
        "field": "new_priority",
        "options": ["baixa", "media", "alta", "critica"],
        "icon": "arrow_upward",
        "color": "#ef4444",
    },
    {
        "id": "assign_agent",
        "label": "Atribuir agente",
        "type": "agent_select",
        "fields": ["auto_assign", "specific_agent_id"],
        "icon": "person_add",
        "color": "#10b981",
    },
    {
        "id": "send_notification",
        "label": "Enviar notificação",
        "type": "notification",
        "fields": ["recipients", "message"],
        "icon": "notifications",
        "color": "#f59e0b",
    },
    {
        "id": "add_comment",
        "label": "Adicionar comentário",
        "type": "comment",
        "fields": ["comment", "public"],
        "icon": "comment",
        "color": "#8b5cf6",
    },
    {
        "id": "escalate",
        "label": "Escalar ticket",
        "type": "escalate",
        "fields": ["level"],
        "icon": "trending_up",
        "color": "#dc2626",
    },
]

TRIGGER_CATALOG = [
    {"id": "ticket_created", "label": "Ticket Criado", "icon": "add_circle", "color": "#10b981"},
    {"id": "ticket_updated", "label": "Ticket Atualizado", "icon": "edit", "color": "#3b82f6"},
    {"id": "status_changed", "label": "Status Alterado", "icon": "swap_horiz", "color": "#f59e0b"},
    {"id": "agent_assigned", "label": "Agente Atribuído", "icon": "person_check", "color": "#8b5cf6"},
    {"id": "interaction_added", "label": "Interação Adicionada", "icon": "chat", "color": "#06b6d4"},
    {"id": "sla_warning", "label": "Aviso de SLA", "icon": "warning", "color": "#ef4444"},
    {"id": "sla_breach", "label": "Violação de SLA", "icon": "cancel", "color": "#dc2626"},
]

TEMPLATE_CATALOG = [
    {
        "id": "auto_assign_high_priority",
        "label": "Auto-atribuição Alta Prioridade",
        "description": "Atribui tickets alta/crítica automaticamente a um agente",
        "icon": "bolt",
    },
    {
        "id": "escalate_old_tickets",
        "label": "Escalação por Tempo",
        "description": "Escala tickets sem resposta após 24h",
        "icon": "schedule",
    },
    {
        "id": "close_resolved_tickets",
        "label": "Auto-fechar Resolvidos",
        "description": "Fecha tickets resolvidos após 48h sem atividade",
        "icon": "done_all",
    },
]


# ======================== VIEWS ========================


@login_required
@role_required('admin', 'gerente', 'supervisor')
def workflow_builder_view(request):
    """Página principal do Visual Workflow Builder."""
    rules = WorkflowRule.objects.all()
    return render(
        request,
        "dashboard/workflow_builder.html",
        {
            "rules": rules,
            "triggers": TRIGGER_CATALOG,
            "conditions": CONDITION_CATALOG,
            "actions": ACTION_CATALOG,
            "templates": TEMPLATE_CATALOG,
        },
    )


# ======================== API CRUD ========================


@login_required
@role_required('admin', 'gerente', 'supervisor')
@require_GET
def api_workflow_catalog(request):
    """GET — catálogo completo (triggers, conditions, actions, templates)."""
    return JsonResponse(
        {
            "triggers": TRIGGER_CATALOG,
            "conditions": CONDITION_CATALOG,
            "actions": ACTION_CATALOG,
            "templates": TEMPLATE_CATALOG,
        }
    )


@login_required
@role_required('admin', 'gerente', 'supervisor')
@require_GET
def api_workflow_list(request):
    """GET — lista todas as regras."""
    rules = WorkflowRule.objects.all()
    data = [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "trigger_event": r.trigger_event,
            "conditions": r.conditions,
            "actions": r.actions,
            "priority": r.priority,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat(),
        }
        for r in rules
    ]
    return JsonResponse({"rules": data})


@login_required
@role_required('admin', 'gerente', 'supervisor')
@require_POST
def api_workflow_create(request):
    """
    POST — cria regra via builder visual.
    Body: { name, description, trigger_event, conditions: {...}, actions: {...}, priority }
    """
    try:
        data = json.loads(request.body)

        name = data.get("name")
        if not name:
            return JsonResponse({"error": "Nome é obrigatório"}, status=400)

        rule = WorkflowRule.objects.create(
            name=name,
            description=data.get("description", ""),
            trigger_event=data.get("trigger_event", "ticket_created"),
            conditions=data.get("conditions", {}),
            actions=data.get("actions", {}),
            priority=data.get("priority", 1),
            is_active=data.get("is_active", True),
        )

        logger.info(f"Workflow criado via builder: {rule.name} (#{rule.id})")

        return JsonResponse(
            {
                "success": True,
                "rule": {
                    "id": rule.id,
                    "name": rule.name,
                    "trigger_event": rule.trigger_event,
                },
            },
            status=201,
        )

    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)
    except Exception as e:
        logger.error(f"Erro ao criar workflow: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@role_required('admin', 'gerente', 'supervisor')
@require_http_methods(["PUT", "PATCH"])
def api_workflow_update(request, pk):
    """PUT/PATCH — atualiza regra."""
    try:
        rule = WorkflowRule.objects.get(id=pk)
        data = json.loads(request.body)

        if "name" in data:
            rule.name = data["name"]
        if "description" in data:
            rule.description = data["description"]
        if "trigger_event" in data:
            rule.trigger_event = data["trigger_event"]
        if "conditions" in data:
            rule.conditions = data["conditions"]
        if "actions" in data:
            rule.actions = data["actions"]
        if "priority" in data:
            rule.priority = data["priority"]
        if "is_active" in data:
            rule.is_active = data["is_active"]

        rule.save()
        logger.info(f"Workflow atualizado: {rule.name} (#{rule.id})")

        return JsonResponse({"success": True, "rule_id": rule.id})

    except WorkflowRule.DoesNotExist:
        return JsonResponse({"error": "Regra não encontrada"}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)


@login_required
@role_required('admin', 'gerente', 'supervisor')
@require_http_methods(["DELETE"])
def api_workflow_delete(request, pk):
    """DELETE — exclui regra."""
    try:
        rule = WorkflowRule.objects.get(id=pk)
        name = rule.name
        rule.delete()
        logger.info(f"Workflow excluído: {name} (#{pk})")
        return JsonResponse({"success": True})
    except WorkflowRule.DoesNotExist:
        return JsonResponse({"error": "Regra não encontrada"}, status=404)


@login_required
@role_required('admin', 'gerente', 'supervisor')
@require_POST
def api_workflow_toggle(request, pk):
    """POST — ativa/desativa regra."""
    try:
        rule = WorkflowRule.objects.get(id=pk)
        rule.is_active = not rule.is_active
        rule.save()
        return JsonResponse({"success": True, "is_active": rule.is_active})
    except WorkflowRule.DoesNotExist:
        return JsonResponse({"error": "Regra não encontrada"}, status=404)


@login_required
@role_required('admin', 'gerente', 'supervisor')
@require_POST
def api_workflow_duplicate(request, pk):
    """POST — duplica regra."""
    try:
        rule = WorkflowRule.objects.get(id=pk)
        new_rule = WorkflowRule.objects.create(
            name=f"{rule.name} (cópia)",
            description=rule.description,
            trigger_event=rule.trigger_event,
            conditions=rule.conditions,
            actions=rule.actions,
            priority=rule.priority,
            is_active=False,
        )
        return JsonResponse(
            {
                "success": True,
                "rule": {"id": new_rule.id, "name": new_rule.name},
            },
            status=201,
        )
    except WorkflowRule.DoesNotExist:
        return JsonResponse({"error": "Regra não encontrada"}, status=404)


@login_required
@role_required('admin', 'gerente', 'supervisor')
@require_POST
def api_workflow_from_template(request):
    """
    POST — cria regra a partir de template pré-definido.
    Body: { "template_name": "auto_assign_high_priority" }
    """
    try:
        data = json.loads(request.body)
        template_name = data.get("template_name")

        template = workflow_builder.get_rule_template(template_name)
        if not template:
            return JsonResponse({"error": f'Template "{template_name}" não encontrado'}, status=404)

        rule = workflow_builder.create_rule(**template)
        if not rule:
            return JsonResponse({"error": "Erro ao criar regra a partir do template"}, status=500)

        return JsonResponse(
            {
                "success": True,
                "rule": {
                    "id": rule.id,
                    "name": rule.name,
                    "trigger_event": rule.trigger_event,
                },
            },
            status=201,
        )

    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)


@login_required
@role_required('admin', 'gerente', 'supervisor')
@require_POST
def api_workflow_validate(request):
    """
    POST — valida configuração de workflow sem salvar.
    Body: { trigger_event, conditions, actions }
    """
    try:
        data = json.loads(request.body)
        errors = []

        trigger = data.get("trigger_event")
        conditions = data.get("conditions", {})
        actions = data.get("actions", {})

        # Validar trigger
        valid_triggers = [t["id"] for t in TRIGGER_CATALOG]
        if trigger not in valid_triggers:
            errors.append(f"Trigger inválido: {trigger}")

        # Validar conditions
        valid_conditions = [c["id"] for c in CONDITION_CATALOG]
        for key in conditions.keys():
            if key not in valid_conditions:
                errors.append(f"Condição desconhecida: {key}")

        # Validar actions
        valid_actions = [a["id"] for a in ACTION_CATALOG]
        for key in actions.keys():
            if key not in valid_actions:
                errors.append(f"Ação desconhecida: {key}")

        if not actions:
            errors.append("Pelo menos uma ação é necessária")

        if errors:
            return JsonResponse({"valid": False, "errors": errors}, status=400)

        return JsonResponse({"valid": True, "message": "Configuração válida"})

    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)


@login_required
@role_required('admin', 'gerente', 'supervisor')
@require_GET
def api_workflow_metrics(request):
    """GET — métricas de execução de workflows."""
    days = int(request.GET.get("days", 30))
    metrics = workflow_engine.get_workflow_metrics(days=days)
    return JsonResponse(metrics)
