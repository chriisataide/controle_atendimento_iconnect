"""
API Views para funcionalidades avançadas do iConnect
Endpoints para notificações em tempo real, analytics e PWA
"""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Q, Avg
from django.core.paginator import Paginator
from datetime import datetime, timedelta
import json
import logging

from .models import Ticket, Notification
from django.contrib.auth.models import User
from .views_helpers import get_analytics_data

logger = logging.getLogger(__name__)

# ====================================
# ANALYTICS API ENDPOINTS
# ====================================

@login_required
@require_http_methods(["GET"])
def analytics_data(request):
    """
    Endpoint para dados de analytics do dashboard
    
    Parâmetros query:
    - period: today, week, month, quarter, year (padrão: month)
    - agent_id: filtrar por agente específico
    - status: filtrar por status específico
    """
    try:
        period = request.GET.get('period', 'month')
        agent_id = request.GET.get('agent_id')
        status = request.GET.get('status')
        
        # Filtros base
        filters = {}
        if agent_id:
            filters['assigned_to_id'] = agent_id
        if status:
            filters['status'] = status
            
        # Período de análise
        now = timezone.now()
        if period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0)
        elif period == 'week':
            start_date = now - timedelta(days=7)
        elif period == 'month':
            start_date = now - timedelta(days=30)
        elif period == 'quarter':
            start_date = now - timedelta(days=90)
        elif period == 'year':
            start_date = now - timedelta(days=365)
        else:
            start_date = now - timedelta(days=30)
            
        filters['created_at__gte'] = start_date
        
        # Buscar tickets
        tickets = Ticket.objects.filter(**filters)
        
        # Métricas principais
        total_tickets = tickets.count()
        open_tickets = tickets.filter(status__in=['NOVO', 'ABERTO', 'EM_ANDAMENTO']).count()
        closed_tickets = tickets.filter(status='FECHADO').count()
        
        # Taxa de resolução
        resolution_rate = (closed_tickets / total_tickets * 100) if total_tickets > 0 else 0
        
        # Tempo médio de resolução (em horas)
        resolved_tickets = tickets.filter(
            status='FECHADO',
            resolved_at__isnull=False
        )
        avg_resolution_time = 0
        if resolved_tickets.exists():
            total_time = sum([
                (ticket.resolved_at - ticket.created_at).total_seconds() / 3600
                for ticket in resolved_tickets
            ])
            avg_resolution_time = total_time / resolved_tickets.count()
        
        # Distribuição por status
        status_distribution = tickets.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Distribuição por prioridade
        priority_distribution = tickets.values('priority').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Tickets por dia (últimos 30 dias)
        daily_data = []
        for i in range(29, -1, -1):
            date = now - timedelta(days=i)
            daily_count = tickets.filter(
                created_at__date=date.date()
            ).count()
            daily_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'count': daily_count
            })
        
        # Performance dos agentes
        agent_performance = User.objects.annotate(
            total_tickets=Count('tickets_agente', filter=Q(**filters)),
            resolved_tickets=Count('tickets_agente', 
                filter=Q(tickets_agente__status='FECHADO', **filters)),
            avg_resolution_hours=Avg('tickets_agente__resolution_time_hours',
                filter=Q(tickets_agente__status='FECHADO', **filters))
        ).order_by('-total_tickets')[:10]
        
        agent_data = []
        for agent in agent_performance:
            resolution_rate_agent = 0
            if agent.total_tickets > 0:
                resolution_rate_agent = (agent.resolved_tickets / agent.total_tickets * 100)
            
            agent_data.append({
                'name': agent.user.get_full_name() or agent.user.username,
                'total_tickets': agent.total_tickets,
                'resolved_tickets': agent.resolved_tickets,
                'resolution_rate': round(resolution_rate_agent, 1),
                'avg_resolution_hours': round(agent.avg_resolution_hours or 0, 1)
            })
        
        # Satisfação do cliente (se disponível)
        satisfaction_data = tickets.exclude(
            customer_satisfaction__isnull=True
        ).aggregate(
            avg_satisfaction=Avg('customer_satisfaction'),
            total_ratings=Count('customer_satisfaction')
        )
        
        # Resposta JSON
        response_data = {
            'period': period,
            'summary': {
                'total_tickets': total_tickets,
                'open_tickets': open_tickets,
                'closed_tickets': closed_tickets,
                'resolution_rate': round(resolution_rate, 1),
                'avg_resolution_time': round(avg_resolution_time, 1),
                'avg_satisfaction': round(satisfaction_data['avg_satisfaction'] or 0, 1),
                'total_ratings': satisfaction_data['total_ratings']
            },
            'charts': {
                'status_distribution': list(status_distribution),
                'priority_distribution': list(priority_distribution),
                'daily_tickets': daily_data,
                'agent_performance': agent_data
            },
            'updated_at': now.isoformat()
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Erro ao buscar analytics: {e}")
        return JsonResponse({
            'error': 'Erro interno do servidor',
            'message': str(e)
        }, status=500)

# ====================================
# NOTIFICAÇÕES API ENDPOINTS
# ====================================

@login_required
@require_http_methods(["GET"])
def notifications_list(request):
    """
    Lista notificações do usuário atual
    
    Parâmetros query:
    - unread_only: true/false (padrão: false)
    - limit: número máximo de notificações (padrão: 20)
    - offset: offset para paginação (padrão: 0)
    """
    try:
        user = request.user
        unread_only = request.GET.get('unread_only', 'false').lower() == 'true'
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Query base
        notifications = Notification.objects.filter(user=user)
        
        if unread_only:
            notifications = notifications.filter(read=False)
            
        notifications = notifications.order_by('-created_at')
        
        # Contadores
        total_count = notifications.count()
        unread_count = Notification.objects.filter(user=user, read=False).count()
        
        # Paginação
        paginated_notifications = notifications[offset:offset + limit]
        
        # Serialização
        notifications_data = []
        for notification in paginated_notifications:
            notifications_data.append({
                'id': notification.id,
                'type': notification.type,
                'title': notification.title,
                'message': notification.message,
                'read': notification.read,
                'created_at': notification.created_at.isoformat(),
                'metadata': notification.metadata,
                'url': notification.url
            })
        
        response_data = {
            'notifications': notifications_data,
            'total_count': total_count,
            'unread_count': unread_count,
            'has_more': total_count > (offset + limit)
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Erro ao buscar notificações: {e}")
        return JsonResponse({
            'error': 'Erro interno do servidor',
            'message': str(e)
        }, status=500)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def mark_notifications_read(request):
    """
    Marca notificações como lidas
    
    Body JSON:
    - notification_ids: array de IDs das notificações
    - mark_all: true para marcar todas como lidas
    """
    try:
        data = json.loads(request.body)
        user = request.user
        
        if data.get('mark_all', False):
            # Marcar todas como lidas
            updated = Notification.objects.filter(
                user=user, 
                read=False
            ).update(
                read=True,
                read_at=timezone.now()
            )
        else:
            # Marcar específicas como lidas
            notification_ids = data.get('notification_ids', [])
            updated = Notification.objects.filter(
                id__in=notification_ids,
                user=user,
                read=False
            ).update(
                read=True,
                read_at=timezone.now()
            )
        
        # Contar notificações não lidas restantes
        unread_count = Notification.objects.filter(user=user, read=False).count()
        
        return JsonResponse({
            'success': True,
            'updated_count': updated,
            'unread_count': unread_count
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'JSON inválido'
        }, status=400)
    except Exception as e:
        logger.error(f"Erro ao marcar notificações: {e}")
        return JsonResponse({
            'error': 'Erro interno do servidor',
            'message': str(e)
        }, status=500)

@login_required
@csrf_exempt
@require_http_methods(["DELETE"])
def delete_notification(request, notification_id):
    """
    Deleta uma notificação específica
    """
    try:
        notification = Notification.objects.get(
            id=notification_id,
            user=request.user
        )
        notification.delete()
        
        # Contar notificações restantes
        unread_count = Notification.objects.filter(
            user=request.user, 
            read=False
        ).count()
        
        return JsonResponse({
            'success': True,
            'unread_count': unread_count
        })
        
    except Notification.DoesNotExist:
        return JsonResponse({
            'error': 'Notificação não encontrada'
        }, status=404)
    except Exception as e:
        logger.error(f"Erro ao deletar notificação: {e}")
        return JsonResponse({
            'error': 'Erro interno do servidor',
            'message': str(e)
        }, status=500)

# ====================================
# PWA API ENDPOINTS
# ====================================

@csrf_exempt
@require_http_methods(["POST"])
def register_push_subscription(request):
    """
    Registra subscription para push notifications
    """
    try:
        if not request.user.is_authenticated:
            return JsonResponse({
                'error': 'Usuário não autenticado'
            }, status=401)
        
        data = json.loads(request.body)
        
        # Salvar subscription (implementar modelo PushSubscription)
        # Por enquanto, apenas logar
        logger.info(f"Push subscription registrada para usuário {request.user.id}")
        
        return JsonResponse({
            'success': True,
            'message': 'Push subscription registrada com sucesso'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'JSON inválido'
        }, status=400)
    except Exception as e:
        logger.error(f"Erro ao registrar push subscription: {e}")
        return JsonResponse({
            'error': 'Erro interno do servidor',
            'message': str(e)
        }, status=500)

@login_required
@require_http_methods(["GET"])
def dashboard_stats_realtime(request):
    """
    Endpoint para estatísticas em tempo real do dashboard
    Usado pelo WebSocket para atualizações automáticas
    """
    try:
        # Stats básicas
        now = timezone.now()
        today = now.replace(hour=0, minute=0, second=0)
        
        stats = {
            'tickets_today': Ticket.objects.filter(created_at__gte=today).count(),
            'tickets_open': Ticket.objects.filter(
                status__in=['NOVO', 'ABERTO', 'EM_ANDAMENTO']
            ).count(),
            'tickets_pending': Ticket.objects.filter(status='NOVO').count(),
            'tickets_resolved_today': Ticket.objects.filter(
                status='FECHADO',
                resolved_at__gte=today
            ).count(),
            'active_agents': User.objects.filter(
                is_active=True,
                last_login__gte=now - timedelta(minutes=15)
            ).count(),
            'avg_response_time': 2.5,  # Implementar cálculo real
            'customer_satisfaction': 4.2,  # Implementar cálculo real
            'updated_at': now.isoformat()
        }
        
        return JsonResponse(stats)
        
    except Exception as e:
        logger.error(f"Erro ao buscar stats em tempo real: {e}")
        return JsonResponse({
            'error': 'Erro interno do servidor',
            'message': str(e)
        }, status=500)

# ====================================
# TICKETS API ENDPOINTS
# ====================================

@login_required
@require_http_methods(["GET"])
def tickets_search(request):
    """
    Busca avançada de tickets
    
    Parâmetros query:
    - q: termo de busca
    - status: filtro por status
    - priority: filtro por prioridade
    - assigned_to: filtro por agente
    - created_after: filtro por data de criação (YYYY-MM-DD)
    - created_before: filtro por data de criação (YYYY-MM-DD)
    - limit: limite de resultados (padrão: 20)
    - offset: offset para paginação (padrão: 0)
    """
    try:
        query = request.GET.get('q', '').strip()
        status = request.GET.get('status')
        priority = request.GET.get('priority')
        assigned_to = request.GET.get('assigned_to')
        created_after = request.GET.get('created_after')
        created_before = request.GET.get('created_before')
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Query base
        tickets = Ticket.objects.all()
        
        # Filtros
        if query:
            tickets = tickets.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(ticket_number__icontains=query) |
                Q(customer__name__icontains=query) |
                Q(customer__email__icontains=query)
            )
            
        if status:
            tickets = tickets.filter(status=status)
            
        if priority:
            tickets = tickets.filter(priority=priority)
            
        if assigned_to:
            tickets = tickets.filter(assigned_to_id=assigned_to)
            
        if created_after:
            tickets = tickets.filter(created_at__date__gte=created_after)
            
        if created_before:
            tickets = tickets.filter(created_at__date__lte=created_before)
            
        # Ordenação
        tickets = tickets.order_by('-created_at')
        
        # Contagem total
        total_count = tickets.count()
        
        # Paginação
        paginated_tickets = tickets[offset:offset + limit]
        
        # Serialização
        tickets_data = []
        for ticket in paginated_tickets:
            tickets_data.append({
                'id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'title': ticket.title,
                'status': ticket.status,
                'priority': ticket.priority,
                'customer_name': ticket.customer.name if ticket.customer else None,
                'assigned_to': ticket.assigned_to.user.get_full_name() if ticket.assigned_to else None,
                'created_at': ticket.created_at.isoformat(),
                'updated_at': ticket.updated_at.isoformat()
            })
        
        response_data = {
            'tickets': tickets_data,
            'total_count': total_count,
            'has_more': total_count > (offset + limit),
            'query': query
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Erro na busca de tickets: {e}")
        return JsonResponse({
            'error': 'Erro interno do servidor',
            'message': str(e)
        }, status=500)

@login_required
@require_http_methods(["GET"])
def ticket_activity(request, ticket_id):
    """
    Busca atividades/histórico de um ticket específico
    """
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        
        # Verificar permissões (implementar lógica conforme necessário)
        
        activities = []
        
        # Implementar busca de atividades/comentários/mudanças
        # Por enquanto, retornar estrutura básica
        
        response_data = {
            'ticket_id': ticket_id,
            'activities': activities,
            'total_count': len(activities)
        }
        
        return JsonResponse(response_data)
        
    except Ticket.DoesNotExist:
        return JsonResponse({
            'error': 'Ticket não encontrado'
        }, status=404)
    except Exception as e:
        logger.error(f"Erro ao buscar atividades do ticket: {e}")
        return JsonResponse({
            'error': 'Erro interno do servidor',
            'message': str(e)
        }, status=500)
