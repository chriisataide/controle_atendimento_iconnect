# Dashboard Executivo - Views e APIs
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Count, Avg, Sum, Q, F
from django.db.models.functions import TruncDate, TruncHour, TruncMonth
from django.db import models
from datetime import datetime, timedelta
import json

from .models import Ticket, Cliente, PerfilAgente, CategoriaTicket
from .models_executive import ExecutiveDashboardKPI, DashboardWidget, MetricaTempoReal, AlertaKPI
from .models_satisfacao import AvaliacaoSatisfacao

@login_required
def executive_dashboard(request):
    """Dashboard Executivo Principal"""
    
    # Verificar se é usuário executivo/admin
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('dashboard:index')
    
    # KPIs Ativos
    kpis = ExecutiveDashboardKPI.objects.filter(is_active=True)
    
    # Widgets do Dashboard
    widgets = DashboardWidget.objects.filter(is_active=True).order_by('position_y', 'position_x')
    
    # Alertas Críticos
    critical_alerts = AlertaKPI.objects.filter(
        is_resolved=False,
        severity__in=['high', 'critical']
    )[:5]

    # ---- Dados reais para KPIs ----
    from .models import MovimentacaoFinanceira
    from decimal import Decimal

    # Receita total do mês
    total_revenue = MovimentacaoFinanceira.objects.filter(
        tipo='receita',
        data_movimentacao__month=timezone.now().month,
        data_movimentacao__year=timezone.now().year,
    ).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

    # Tickets resolvidos
    tickets_resolved = Ticket.objects.filter(
        status__in=['resolvido', 'fechado']
    ).count()

    # Satisfação média
    satisfaction_avg = AvaliacaoSatisfacao.objects.aggregate(
        avg=Avg('nota_atendimento')
    )['avg'] or 0

    # SLA compliance
    tickets_with_sla = Ticket.objects.exclude(sla_deadline__isnull=True)
    if tickets_with_sla.exists():
        sla_compliant = tickets_with_sla.filter(
            resolvido_em__lte=F('sla_deadline')
        ).count()
        sla_compliance = round(sla_compliant / tickets_with_sla.count() * 100, 1)
    else:
        sla_compliance = 0

    # Tickets por status (para gráfico)
    tickets_abertos = Ticket.objects.filter(status='aberto').count()
    tickets_andamento = Ticket.objects.filter(status='em_andamento').count()
    tickets_aguardando = Ticket.objects.filter(status='aguardando_cliente').count()

    context = {
        'title': 'Dashboard Executivo',
        'kpis': kpis,
        'widgets': widgets,
        'critical_alerts': critical_alerts,
        'current_page': 'executive',
        'total_revenue': total_revenue,
        'tickets_resolved': tickets_resolved,
        'satisfaction_avg': satisfaction_avg,
        'sla_compliance': sla_compliance,
        'tickets_abertos': tickets_abertos,
        'tickets_andamento': tickets_andamento,
        'tickets_aguardando': tickets_aguardando,
    }
    
    return render(request, 'dashboard/executive_dashboard.html', context)

@login_required
def executive_kpis_api(request):
    """API para dados dos KPIs em tempo real"""
    
    # Calcular KPIs automaticamente
    kpis_data = []
    
    # 1. Volume de Tickets
    total_tickets_today = Ticket.objects.filter(
        criado_em__date=timezone.now().date()
    ).count()
    
    total_tickets_month = Ticket.objects.filter(
        criado_em__month=timezone.now().month,
        criado_em__year=timezone.now().year
    ).count()
    
    # 2. SLA Compliance
    tickets_with_sla = Ticket.objects.exclude(sla_deadline__isnull=True)
    sla_compliant = tickets_with_sla.filter(
        resolvido_em__lte=F('sla_deadline')
    ).count() if tickets_with_sla.exists() else 0
    
    sla_compliance_rate = (sla_compliant / tickets_with_sla.count() * 100) if tickets_with_sla.count() > 0 else 0
    
    # 3. Satisfação do Cliente
    avg_satisfaction = AvaliacaoSatisfacao.objects.aggregate(
        avg_score=Avg('nota_atendimento')
    )['avg_score'] or 0
    
    # 4. Tempo Médio de Resolução (em horas)
    resolved_tickets = Ticket.objects.filter(
        status='fechado',
        resolvido_em__isnull=False
    )
    
    avg_resolution_time = 0
    if resolved_tickets.exists():
        total_time = sum([
            (ticket.resolvido_em - ticket.criado_em).total_seconds() / 3600
            for ticket in resolved_tickets
            if ticket.resolvido_em and ticket.criado_em
        ])
        avg_resolution_time = total_time / resolved_tickets.count()
    
    # 5. Produtividade dos Agentes
    agents_productivity = PerfilAgente.objects.filter(
        user__is_active=True
    ).annotate(
        tickets_today=Count('user__tickets_agente', filter=Q(
            user__tickets_agente__criado_em__date=timezone.now().date()
        ))
    )
    
    avg_productivity = agents_productivity.aggregate(
        avg_tickets=Avg('tickets_today')
    )['avg_tickets'] or 0
    
    # Construir resposta JSON
    kpis_data = {
        'tickets_volume': {
            'name': 'Volume de Tickets Hoje',
            'value': total_tickets_today,
            'target': 50,  # Meta configurável
            'trend': 'up' if total_tickets_today > 30 else 'down',
            'percentage': (total_tickets_today / 50 * 100) if total_tickets_today <= 50 else 100
        },
        'sla_compliance': {
            'name': 'Compliance SLA',
            'value': round(sla_compliance_rate, 1),
            'target': 95,
            'trend': 'up' if sla_compliance_rate >= 90 else 'down',
            'percentage': sla_compliance_rate
        },
        'customer_satisfaction': {
            'name': 'Satisfação do Cliente',
            'value': round(avg_satisfaction, 2),
            'target': 4.5,
            'trend': 'up' if avg_satisfaction >= 4.0 else 'down',
            'percentage': (avg_satisfaction / 5 * 100)
        },
        'resolution_time': {
            'name': 'Tempo Médio Resolução (h)',
            'value': round(avg_resolution_time, 1),
            'target': 24,
            'trend': 'down' if avg_resolution_time <= 24 else 'up',
            'percentage': max(0, 100 - (avg_resolution_time / 24 * 100))
        },
        'agent_productivity': {
            'name': 'Produtividade Agentes',
            'value': round(avg_productivity, 1),
            'target': 15,
            'trend': 'up' if avg_productivity >= 10 else 'down',
            'percentage': (avg_productivity / 15 * 100) if avg_productivity <= 15 else 100
        }
    }
    
    return JsonResponse(kpis_data)

@login_required
def executive_charts_api(request):
    """API para dados dos gráficos executivos"""
    
    # Gráfico de Tickets por Período
    last_30_days = timezone.now() - timedelta(days=30)
    tickets_by_date = Ticket.objects.filter(
        criado_em__gte=last_30_days
    ).annotate(
        date=TruncDate('criado_em')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Gráfico de SLA por Categoria
    sla_by_category = CategoriaTicket.objects.annotate(
        total_tickets=Count('ticket'),
        sla_breached=Count('ticket', filter=Q(
            ticket__resolvido_em__gt=models.F('ticket__sla_deadline')
        ))
    ).values('nome', 'total_tickets', 'sla_breached')
    
    # Gráfico de Satisfação por Período
    satisfaction_trend = AvaliacaoSatisfacao.objects.filter(
        avaliado_em__gte=last_30_days
    ).annotate(
        date=TruncDate('avaliado_em')
    ).values('date').annotate(
        avg_score=Avg('nota_atendimento')
    ).order_by('date')
    
    # Gráfico de Performance dos Agentes
    agents_performance = PerfilAgente.objects.filter(
        user__is_active=True
    ).annotate(
        tickets_resolved=Count('user__tickets_agente', filter=Q(
            user__tickets_agente__status='fechado',
            user__tickets_agente__resolvido_em__month=timezone.now().month
        )),
        avg_satisfaction=Avg('user__tickets_agente__avaliacaosatisfacao__nota_atendimento')
    ).values(
        'user__first_name',
        'user__last_name',
        'tickets_resolved',
        'avg_satisfaction'
    )
    
    charts_data = {
        'tickets_trend': {
            'labels': [item['date'].strftime('%d/%m') for item in tickets_by_date],
            'data': [item['count'] for item in tickets_by_date]
        },
        'sla_by_category': {
            'labels': [item['nome'] for item in sla_by_category],
            'compliance': [
                ((item['total_tickets'] - item['sla_breached']) / item['total_tickets'] * 100)
                if item['total_tickets'] > 0 else 0
                for item in sla_by_category
            ]
        },
        'satisfaction_trend': {
            'labels': [item['date'].strftime('%d/%m') for item in satisfaction_trend],
            'data': [float(item['avg_score']) if item['avg_score'] else 0 for item in satisfaction_trend]
        },
        'agents_performance': {
            'labels': [f"{item['user__first_name']} {item['user__last_name']}" for item in agents_performance],
            'tickets': [item['tickets_resolved'] for item in agents_performance],
            'satisfaction': [float(item['avg_satisfaction']) if item['avg_satisfaction'] else 0 for item in agents_performance]
        }
    }
    
    return JsonResponse(charts_data)

@login_required
def executive_alerts_api(request):
    """API para alertas executivos"""
    
    alerts = []
    
    # Verificar SLA em risco
    tickets_at_risk = Ticket.objects.filter(
        status__in=['aberto', 'em_andamento'],
        sla_deadline__lte=timezone.now() + timedelta(hours=2)
    ).count()
    
    if tickets_at_risk > 0:
        alerts.append({
            'type': 'warning',
            'title': 'SLA em Risco',
            'message': f'{tickets_at_risk} tickets com SLA próximo do vencimento',
            'action_url': '/dashboard/sla/alerts/',
            'severity': 'high' if tickets_at_risk > 5 else 'medium'
        })
    
    # Verificar satisfação baixa
    recent_low_satisfaction = AvaliacaoSatisfacao.objects.filter(
        avaliado_em__gte=timezone.now() - timedelta(days=7),
        nota_atendimento__lt=3
    ).count()
    
    if recent_low_satisfaction > 0:
        alerts.append({
            'type': 'danger',
            'title': 'Satisfação Baixa',
            'message': f'{recent_low_satisfaction} avaliações baixas esta semana',
            'action_url': '/dashboard/reports/',
            'severity': 'high'
        })
    
    # Verificar volume anormal de tickets
    today_tickets = Ticket.objects.filter(
        criado_em__date=timezone.now().date()
    ).count()
    
    avg_daily_tickets = Ticket.objects.filter(
        criado_em__gte=timezone.now() - timedelta(days=30)
    ).annotate(
        date=TruncDate('criado_em')
    ).values('date').annotate(
        count=Count('id')
    ).aggregate(avg=Avg('count'))['avg'] or 0
    
    if today_tickets > avg_daily_tickets * 1.5:
        alerts.append({
            'type': 'info',
            'title': 'Volume Alto',
            'message': f'Volume de tickets hoje ({today_tickets}) está 50% acima da média',
            'action_url': '/dashboard/tickets/',
            'severity': 'medium'
        })
    
    return JsonResponse({'alerts': alerts})

@login_required
@csrf_exempt
def executive_widget_config(request):
    """Configuração de widgets do dashboard"""
    
    if request.method == 'POST':
        data = json.loads(request.body)
        
        widget = DashboardWidget.objects.create(
            title=data['title'],
            widget_type=data['widget_type'],
            data_source=data['data_source'],
            config=data.get('config', {}),
            position_x=data.get('position_x', 0),
            position_y=data.get('position_y', 0),
            width=data.get('width', 4),
            height=data.get('height', 3),
            created_by=request.user
        )
        
        return JsonResponse({
            'status': 'success',
            'widget_id': widget.id
        })
    
    # GET - Listar widgets disponíveis
    widgets = DashboardWidget.objects.filter(is_active=True)
    widgets_data = [{
        'id': w.id,
        'title': w.title,
        'type': w.widget_type,
        'position': {'x': w.position_x, 'y': w.position_y},
        'size': {'width': w.width, 'height': w.height},
        'config': w.config
    } for w in widgets]
    
    return JsonResponse({'widgets': widgets_data})