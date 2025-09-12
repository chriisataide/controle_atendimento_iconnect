"""
SLA Views - APIs e páginas para gerenciamento de SLA
"""
import json
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator

from .models import (
    Ticket, SLAPolicy, SLAHistory, SLAAlert, 
    CategoriaTicket, PrioridadeTicket, StatusTicket
)
from .services.sla_monitor import sla_monitor
from .services.sla_calculator import sla_calculator


# Função de teste temporária sem autenticação
def sla_test(request):
    """Teste SLA sem autenticação"""
    return JsonResponse({
        'status': 'success',
        'message': 'SLA sistema funcionando!',
        'timestamp': timezone.now().isoformat(),
        'sla_policies_count': SLAPolicy.objects.count(),
        'sla_alerts_count': SLAAlert.objects.count()
    })

# Dashboard SLA sem autenticação (TEMPORÁRIO - apenas para demonstração)
def sla_dashboard_public(request):
    """Dashboard SLA público temporário para demonstração"""
    try:
        dashboard_data = sla_monitor.get_sla_dashboard_data()
        sla_policies = SLAPolicy.objects.filter(is_active=True).select_related('categoria')
        
        context = {
            'title': 'Dashboard SLA - Demonstração',
            'dashboard_data': dashboard_data,
            'sla_policies': sla_policies,
            'categorias': CategoriaTicket.objects.all(),
            'prioridades': PrioridadeTicket.choices,
            'is_demo': True  # Flag para indicar que é demonstração
        }
        return render(request, 'dashboard/sla/dashboard.html', context)
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'message': 'Erro ao carregar dashboard SLA',
            'sla_system_status': 'operational'
        })


@login_required
def sla_dashboard(request):
    """Dashboard principal de SLA"""
    context = {
        'title': 'Dashboard SLA',
        'dashboard_data': sla_monitor.get_sla_dashboard_data(),
        'sla_policies': SLAPolicy.objects.filter(is_active=True).select_related('categoria'),
        'categorias': CategoriaTicket.objects.all(),
        'prioridades': PrioridadeTicket.choices
    }
    return render(request, 'dashboard/sla/dashboard.html', context)


@login_required
def sla_policies(request):
    """Página de gerenciamento de políticas de SLA"""
    policies = SLAPolicy.objects.all().select_related('categoria', 'escalation_to')
    
    context = {
        'title': 'Políticas de SLA',
        'policies': policies,
        'categorias': CategoriaTicket.objects.all(),
        'prioridades': PrioridadeTicket.choices
    }
    return render(request, 'dashboard/sla/policies.html', context)


@login_required
def sla_alerts(request):
    """Página de alertas de SLA"""
    alert_type = request.GET.get('type', 'all')
    resolved = request.GET.get('resolved', 'false') == 'true'
    
    alerts = SLAAlert.objects.select_related(
        'ticket', 'ticket__cliente', 'ticket__agente', 'sla_history__sla_policy'
    )
    
    if alert_type != 'all':
        alerts = alerts.filter(alert_type=alert_type)
    
    if not resolved:
        alerts = alerts.filter(resolved_at__isnull=True)
    
    alerts = alerts.order_by('-created_at')
    
    # Paginação
    paginator = Paginator(alerts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'Alertas de SLA',
        'alerts': page_obj,
        'alert_types': SLAAlert.ALERT_TYPES,
        'current_type': alert_type,
        'show_resolved': resolved
    }
    return render(request, 'dashboard/sla/alerts.html', context)


@login_required
def sla_reports(request):
    """Página de relatórios de SLA"""
    # Período de análise
    period = request.GET.get('period', '30')  # dias
    end_date = timezone.now()
    start_date = end_date - timedelta(days=int(period))
    
    # Tickets no período
    tickets = Ticket.objects.filter(
        criado_em__gte=start_date,
        criado_em__lte=end_date
    ).select_related('categoria', 'agente', 'sla_policy')
    
    # Estatísticas gerais
    total_tickets = tickets.count()
    resolved_tickets = tickets.filter(status__in=['resolvido', 'fechado']).count()
    
    # SLA Compliance
    sla_histories = SLAHistory.objects.filter(
        ticket__in=tickets
    ).select_related('ticket', 'sla_policy')
    
    compliant_count = 0
    total_with_sla = 0
    
    for sla_history in sla_histories:
        metrics = sla_calculator.calculate_sla_metrics(sla_history)
        if metrics['overall_sla_compliance'] is not None:
            total_with_sla += 1
            if metrics['overall_sla_compliance']:
                compliant_count += 1
    
    compliance_rate = (compliant_count / total_with_sla * 100) if total_with_sla > 0 else 0
    
    # Performance por categoria
    category_performance = []
    for categoria in CategoriaTicket.objects.all():
        cat_tickets = tickets.filter(categoria=categoria)
        cat_sla_histories = sla_histories.filter(ticket__categoria=categoria)
        
        cat_compliant = 0
        cat_total = 0
        
        for sla_history in cat_sla_histories:
            metrics = sla_calculator.calculate_sla_metrics(sla_history)
            if metrics['overall_sla_compliance'] is not None:
                cat_total += 1
                if metrics['overall_sla_compliance']:
                    cat_compliant += 1
        
        if cat_total > 0:
            category_performance.append({
                'categoria': categoria,
                'total_tickets': cat_tickets.count(),
                'compliance_rate': (cat_compliant / cat_total * 100),
                'sla_violations': cat_total - cat_compliant
            })
    
    # Performance por agente
    agent_performance = []
    agents = tickets.values('agente__id', 'agente__username', 'agente__first_name', 'agente__last_name').distinct()
    
    for agent in agents:
        if not agent['agente__id']:
            continue
            
        agent_tickets = tickets.filter(agente_id=agent['agente__id'])
        agent_sla_histories = sla_histories.filter(ticket__agente_id=agent['agente__id'])
        
        agent_compliant = 0
        agent_total = 0
        
        for sla_history in agent_sla_histories:
            metrics = sla_calculator.calculate_sla_metrics(sla_history)
            if metrics['overall_sla_compliance'] is not None:
                agent_total += 1
                if metrics['overall_sla_compliance']:
                    agent_compliant += 1
        
        if agent_total > 0:
            agent_performance.append({
                'agent_id': agent['agente__id'],
                'agent_name': f"{agent['agente__first_name']} {agent['agente__last_name']}".strip() or agent['agente__username'],
                'total_tickets': agent_tickets.count(),
                'compliance_rate': (agent_compliant / agent_total * 100),
                'sla_violations': agent_total - agent_compliant
            })
    
    context = {
        'title': 'Relatórios de SLA',
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'total_tickets': total_tickets,
        'resolved_tickets': resolved_tickets,
        'compliance_rate': compliance_rate,
        'category_performance': category_performance,
        'agent_performance': agent_performance,
        'recent_violations': SLAAlert.objects.filter(
            alert_type='breach',
            created_at__gte=start_date
        ).select_related('ticket', 'ticket__cliente')[:10]
    }
    
    return render(request, 'dashboard/sla/reports.html', context)


# ====== APIs ======

@login_required
@require_http_methods(["GET"])
def api_sla_dashboard_data(request):
    """API para dados do dashboard SLA"""
    try:
        data = sla_monitor.get_sla_dashboard_data()
        
        # Serializa dados complexos
        for ticket_data in data.get('critical_tickets', []):
            ticket = ticket_data['ticket']
            ticket_data['ticket_data'] = {
                'numero': ticket.numero,
                'titulo': ticket.titulo,
                'cliente': ticket.cliente.nome,
                'agente': ticket.agente.get_full_name() if ticket.agente else 'Não atribuído',
                'prioridade': ticket.get_prioridade_display(),
                'status': ticket.get_status_display(),
                'criado_em': ticket.criado_em.isoformat(),
            }
            
            # Converte timedelta para string
            if ticket_data['time_remaining']:
                total_seconds = int(ticket_data['time_remaining'].total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                ticket_data['time_remaining_str'] = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            else:
                ticket_data['time_remaining_str'] = "Vencido"
            
            # Remove objetos não serializáveis
            del ticket_data['ticket']
            del ticket_data['sla_history']
        
        return JsonResponse({
            'success': True,
            'data': data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_create_sla_policy(request):
    """API para criar política de SLA"""
    try:
        data = json.loads(request.body)
        
        # Validações básicas
        required_fields = ['name', 'prioridade', 'first_response_time', 'resolution_time']
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({
                    'success': False,
                    'error': f'Campo {field} é obrigatório'
                }, status=400)
        
        # Cria a política
        policy_data = {
            'name': data['name'],
            'prioridade': data['prioridade'],
            'first_response_time': int(data['first_response_time']),
            'resolution_time': int(data['resolution_time']),
            'escalation_time': int(data.get('escalation_time', data['resolution_time'])),
            'business_hours_only': data.get('business_hours_only', True),
            'warning_percentage': int(data.get('warning_percentage', 80)),
            'escalation_enabled': data.get('escalation_enabled', True)
        }
        
        # Categoria opcional
        if data.get('categoria_id'):
            try:
                categoria = CategoriaTicket.objects.get(id=data['categoria_id'])
                policy_data['categoria'] = categoria
            except CategoriaTicket.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Categoria não encontrada'
                }, status=404)
        
        # Supervisor para escalação
        if data.get('escalation_to_id'):
            try:
                from django.contrib.auth.models import User
                user = User.objects.get(id=data['escalation_to_id'])
                policy_data['escalation_to'] = user
            except User.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Usuário não encontrado'
                }, status=404)
        
        # Horários de trabalho
        if data.get('start_hour'):
            policy_data['start_hour'] = data['start_hour']
        if data.get('end_hour'):
            policy_data['end_hour'] = data['end_hour']
        if data.get('work_days'):
            policy_data['work_days'] = data['work_days']
        
        policy = SLAPolicy.objects.create(**policy_data)
        
        return JsonResponse({
            'success': True,
            'policy_id': policy.id,
            'message': 'Política de SLA criada com sucesso'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_resolve_sla_alert(request, alert_id):
    """API para resolver alerta de SLA"""
    try:
        alert = get_object_or_404(SLAAlert, id=alert_id)
        
        if alert.resolved_at:
            return JsonResponse({
                'success': False,
                'error': 'Alerta já foi resolvido'
            }, status=400)
        
        alert.resolved_at = timezone.now()
        alert.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Alerta resolvido com sucesso'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_run_sla_monitor(request):
    """API para executar monitoramento de SLA manualmente"""
    try:
        stats = sla_monitor.monitor_all_tickets()
        
        return JsonResponse({
            'success': True,
            'message': 'Monitoramento de SLA executado com sucesso',
            'stats': stats
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def api_ticket_sla_details(request, ticket_id):
    """API para detalhes de SLA de um ticket específico"""
    try:
        ticket = get_object_or_404(Ticket, id=ticket_id)
        sla_history = SLAHistory.objects.filter(ticket=ticket).first()
        
        if not sla_history:
            return JsonResponse({
                'success': False,
                'error': 'Ticket não possui SLA configurado'
            }, status=404)
        
        metrics = sla_calculator.calculate_sla_metrics(sla_history)
        
        # Formata dados para JSON
        data = {
            'ticket': {
                'numero': ticket.numero,
                'titulo': ticket.titulo,
                'status': ticket.get_status_display(),
                'prioridade': ticket.get_prioridade_display(),
                'criado_em': ticket.criado_em.isoformat(),
            },
            'sla_policy': {
                'name': sla_history.sla_policy.name,
                'first_response_time': sla_history.sla_policy.first_response_time,
                'resolution_time': sla_history.sla_policy.resolution_time,
            },
            'deadlines': {
                'first_response': sla_history.first_response_deadline.isoformat(),
                'resolution': sla_history.resolution_deadline.isoformat(),
                'escalation': sla_history.escalation_deadline.isoformat(),
            },
            'status': sla_history.status,
            'escalated': sla_history.escalated,
            'metrics': {
                'sla_percentage_elapsed': metrics.get('sla_percentage_elapsed', 0),
                'first_response_sla_met': metrics.get('first_response_sla_met'),
                'resolution_sla_met': metrics.get('resolution_sla_met'),
                'overall_sla_compliance': metrics.get('overall_sla_compliance'),
            }
        }
        
        # Formata tempo restante
        if metrics.get('time_to_breach'):
            td = metrics['time_to_breach']
            total_seconds = int(td.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            data['time_remaining'] = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
        else:
            data['time_remaining'] = "Vencido"
        
        return JsonResponse({
            'success': True,
            'data': data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
