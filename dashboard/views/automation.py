"""
Views do motor de automação: dashboard, regras e workflows.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
import json
import logging
from dashboard.utils.rbac import role_required

logger = logging.getLogger('dashboard')


@login_required
@role_required('admin', 'gerente', 'supervisor')
def automation_dashboard(request):
    """Dashboard do Sistema de Automação"""
    from ..models import WorkflowRule, WorkflowExecution

    # Handle POST: ativar template
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            if data.get('action') == 'activate_template':
                tpl = data.get('template')
                TEMPLATE_CONFIGS = {
                    'auto_assign': {
                        'name': 'Atribuição Automática',
                        'description': 'Distribui tickets automaticamente entre agentes',
                        'trigger_event': 'ticket_created',
                        'conditions': {'has_agent': False},
                        'actions': [{'type': 'assign_agent', 'value': 'auto'}],
                        'priority': 8,
                    },
                    'sla_monitor': {
                        'name': 'Monitoramento de SLA',
                        'description': 'Alerta quando SLA está próximo de ser violado',
                        'trigger_event': 'sla_warning',
                        'conditions': {},
                        'actions': [{'type': 'send_notification', 'value': 'Alerta: SLA prestes a ser violado'}],
                        'priority': 9,
                    },
                    'escalation': {
                        'name': 'Escalação por Prioridade',
                        'description': 'Escala tickets sem resposta por tempo prolongado',
                        'trigger_event': 'ticket_updated',
                        'conditions': {'status': 'aberto', 'time_since_creation': '24h'},
                        'actions': [{'type': 'escalate', 'value': 'supervisor'}, {'type': 'change_priority', 'value': 'alta'}],
                        'priority': 7,
                    },
                    'email_notify': {
                        'name': 'Notificações por E-mail',
                        'description': 'Envia e-mails ao cliente quando há mudanças',
                        'trigger_event': 'status_changed',
                        'conditions': {},
                        'actions': [{'type': 'send_notification', 'value': 'Status do seu ticket foi atualizado'}],
                        'priority': 5,
                    },
                    'auto_resolve': {
                        'name': 'Auto-Resolução',
                        'description': 'Fecha tickets resolvidos após 72h de inatividade',
                        'trigger_event': 'status_changed',
                        'conditions': {'status': 'resolvido', 'time_since_creation': '72h'},
                        'actions': [{'type': 'change_status', 'value': 'fechado'}, {'type': 'add_comment', 'value': 'Ticket fechado automaticamente após 72h sem interação.'}],
                        'priority': 3,
                    },
                }
                if tpl in TEMPLATE_CONFIGS:
                    cfg = TEMPLATE_CONFIGS[tpl]
                    rule, created = WorkflowRule.objects.get_or_create(
                        name=cfg['name'],
                        defaults={
                            'description': cfg['description'],
                            'trigger_event': cfg['trigger_event'],
                            'conditions': cfg['conditions'],
                            'actions': cfg['actions'],
                            'priority': cfg['priority'],
                            'is_active': True,
                        }
                    )
                    if not created and not rule.is_active:
                        rule.is_active = True
                        rule.save()
                    return JsonResponse({'success': True, 'created': created})
                return JsonResponse({'success': False, 'error': 'Template não encontrado'})
        except Exception:
            logger.exception('Erro em automation_dashboard POST')
            return JsonResponse({'success': False, 'error': 'Erro interno do servidor'})

    # GET: dashboard data
    active_workflows = WorkflowRule.objects.filter(is_active=True).count()
    all_workflows = WorkflowRule.objects.all()
    total_executions = WorkflowExecution.objects.count()
    failed_executions = WorkflowExecution.objects.filter(success=False).count()
    success_executions = total_executions - failed_executions
    success_rate = round((success_executions / total_executions * 100) if total_executions > 0 else 0)
    recent_executions = WorkflowExecution.objects.select_related('rule', 'ticket').order_by('-created_at')[:10]

    tpl_names = {
        'tpl_auto_assign': 'Atribuição Automática',
        'tpl_sla_monitor': 'Monitoramento de SLA',
        'tpl_escalation': 'Escalação por Prioridade',
        'tpl_email_notify': 'Notificações por E-mail',
        'tpl_auto_resolve': 'Auto-Resolução',
    }
    tpl_status = {}
    for key, name in tpl_names.items():
        tpl_status[key] = WorkflowRule.objects.filter(name=name, is_active=True).exists()

    chart_labels = []
    chart_data = []
    for i in range(6, -1, -1):
        day = timezone.now().date() - timedelta(days=i)
        chart_labels.append(day.strftime('%d/%m'))
        chart_data.append(WorkflowExecution.objects.filter(
            created_at__date=day
        ).count())

    context = {
        'title': 'Motor de Automação',
        'current_page': 'automation',
        'active_workflows': active_workflows,
        'total_executions': total_executions,
        'failed_executions': failed_executions,
        'success_executions': success_executions,
        'success_rate': success_rate,
        'workflows': all_workflows,
        'recent_executions': recent_executions,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }
    context.update(tpl_status)

    return render(request, 'dashboard/automation/dashboard.html', context)


@login_required
@role_required('admin', 'gerente', 'supervisor')
def automation_rules(request):
    """Gerenciamento de Regras de Automação"""
    from ..models import WorkflowRule, WorkflowExecution

    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            action = data.get('action')

            if action == 'create':
                conditions = data.get('conditions', '{}')
                actions_field = data.get('actions', '[]')
                try:
                    conditions = json.loads(conditions) if isinstance(conditions, str) else conditions
                except json.JSONDecodeError:
                    conditions = {}
                try:
                    actions_field = json.loads(actions_field) if isinstance(actions_field, str) else actions_field
                except json.JSONDecodeError:
                    actions_field = []

                rule = WorkflowRule.objects.create(
                    name=data.get('name', 'Nova Regra'),
                    description=data.get('description', ''),
                    trigger_event=data.get('trigger_event', 'ticket_created'),
                    conditions=conditions,
                    actions=actions_field,
                    priority=int(data.get('priority', 5)),
                    is_active=True,
                )
                return JsonResponse({'success': True, 'id': rule.id, 'message': 'Regra criada com sucesso'})

            elif action == 'toggle':
                rule = WorkflowRule.objects.get(id=data.get('rule_id'))
                rule.is_active = not rule.is_active
                rule.save()
                return JsonResponse({'success': True, 'is_active': rule.is_active})

            elif action == 'delete':
                WorkflowRule.objects.filter(id=data.get('rule_id')).delete()
                return JsonResponse({'success': True, 'message': 'Regra excluída'})
        except Exception:
            logger.exception('Erro em automation_rules POST')
            return JsonResponse({'success': False, 'error': 'Erro interno do servidor'})

    rules = WorkflowRule.objects.all().order_by('-priority', 'name')
    total_rules = rules.count()
    active_rules = rules.filter(is_active=True).count()
    inactive_rules = total_rules - active_rules
    total_executions = WorkflowExecution.objects.count()

    return render(request, 'dashboard/automation/rules.html', {
        'title': 'Regras de Automação',
        'current_page': 'automation_rules',
        'rules': rules,
        'total_rules': total_rules,
        'active_rules': active_rules,
        'inactive_rules': inactive_rules,
        'total_executions': total_executions,
    })


@login_required
@role_required('admin', 'gerente', 'supervisor')
def automation_workflows(request):
    """Gerenciamento de Workflows"""
    from ..models import WorkflowRule, WorkflowExecution

    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            action = data.get('action')

            if action == 'create':
                tpl = data.get('template')
                QUICK_TEMPLATES = {
                    'auto_assign_high_priority': {
                        'name': 'Auto-Atribuir Alta Prioridade',
                        'description': 'Atribui automaticamente tickets de alta prioridade ao melhor agente disponível',
                        'trigger_event': 'ticket_created',
                        'conditions': {'priority': 'alta'},
                        'actions': [{'type': 'assign_agent', 'value': 'auto'}, {'type': 'send_notification', 'value': 'Ticket de alta prioridade atribuído'}],
                        'priority': 9,
                    },
                    'escalate_old_tickets': {
                        'name': 'Escalar Tickets Antigos',
                        'description': 'Escala tickets abertos há mais de 48h sem atualização',
                        'trigger_event': 'ticket_updated',
                        'conditions': {'status': 'aberto', 'time_since_creation': '48h'},
                        'actions': [{'type': 'escalate', 'value': 'supervisor'}, {'type': 'change_priority', 'value': 'urgente'}],
                        'priority': 8,
                    },
                    'close_resolved_tickets': {
                        'name': 'Fechar Tickets Resolvidos',
                        'description': 'Fecha automaticamente tickets resolvidos após 48h de inatividade',
                        'trigger_event': 'status_changed',
                        'conditions': {'status': 'resolvido', 'time_since_creation': '48h'},
                        'actions': [{'type': 'change_status', 'value': 'fechado'}, {'type': 'add_comment', 'value': 'Ticket fechado automaticamente.'}],
                        'priority': 4,
                    },
                }
                if tpl and tpl in QUICK_TEMPLATES:
                    cfg = QUICK_TEMPLATES[tpl]
                    rule = WorkflowRule.objects.create(
                        name=cfg['name'],
                        description=cfg['description'],
                        trigger_event=cfg['trigger_event'],
                        conditions=cfg['conditions'],
                        actions=cfg['actions'],
                        priority=cfg['priority'],
                        is_active=True,
                    )
                    return JsonResponse({'success': True, 'id': rule.id, 'message': f'Workflow "{cfg["name"]}" criado'})
                else:
                    conditions = data.get('conditions', '{}')
                    actions_field = data.get('actions', '[]')
                    try:
                        conditions = json.loads(conditions) if isinstance(conditions, str) else conditions
                    except json.JSONDecodeError:
                        conditions = {}
                    try:
                        actions_field = json.loads(actions_field) if isinstance(actions_field, str) else actions_field
                    except json.JSONDecodeError:
                        actions_field = []
                    rule = WorkflowRule.objects.create(
                        name=data.get('name', 'Novo Workflow'),
                        description=data.get('description', ''),
                        trigger_event=data.get('trigger_event', 'ticket_created'),
                        conditions=conditions,
                        actions=actions_field,
                        priority=int(data.get('priority', 5)),
                        is_active=True,
                    )
                    return JsonResponse({'success': True, 'id': rule.id, 'message': 'Workflow criado com sucesso'})

            elif action == 'toggle':
                rule = WorkflowRule.objects.get(id=data.get('workflow_id'))
                rule.is_active = not rule.is_active
                rule.save()
                return JsonResponse({'success': True, 'is_active': rule.is_active})

            elif action == 'delete':
                WorkflowRule.objects.filter(id=data.get('workflow_id')).delete()
                return JsonResponse({'success': True, 'message': 'Workflow excluído'})
        except Exception:
            logger.exception('Erro em automation_workflows POST')
            return JsonResponse({'success': False, 'error': 'Erro interno do servidor'})

    workflows = WorkflowRule.objects.all().order_by('-priority', 'name')
    total_workflows = workflows.count()
    active_workflows = workflows.filter(is_active=True).count()
    total_executions = WorkflowExecution.objects.count()
    success_execs = WorkflowExecution.objects.filter(success=True).count()
    success_rate = round((success_execs / total_executions * 100) if total_executions > 0 else 0)

    return render(request, 'dashboard/automation/workflows.html', {
        'title': 'Workflows Automáticos',
        'current_page': 'automation_workflows',
        'workflows': workflows,
        'total_workflows': total_workflows,
        'active_workflows': active_workflows,
        'total_executions': total_executions,
        'success_rate': success_rate,
    })
