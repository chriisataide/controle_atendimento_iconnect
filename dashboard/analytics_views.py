# Views para Analytics Avançado
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Ticket, Cliente

@login_required
def analytics_dashboard(request):
    """Dashboard executivo com métricas avançadas"""
    
    # Período de análise
    hoje = timezone.now().date()
    inicio_mes = hoje.replace(day=1)
    mes_anterior = (inicio_mes - timedelta(days=1)).replace(day=1)
    inicio_ano = hoje.replace(month=1, day=1)
    
    # KPIs Principais
    tickets_hoje = Ticket.objects.filter(criado_em__date=hoje).count()
    tickets_mes = Ticket.objects.filter(criado_em__date__gte=inicio_mes).count()
    tickets_ano = Ticket.objects.filter(criado_em__date__gte=inicio_ano).count()
    
    # Taxa de Resolução
    resolvidos_mes = Ticket.objects.filter(
        criado_em__date__gte=inicio_mes,
        status='resolvido'
    ).count()
    taxa_resolucao = (resolvidos_mes / tickets_mes * 100) if tickets_mes > 0 else 0
    
    # Tempo Médio de Resolução
    tempo_medio = Ticket.objects.filter(
        status='resolvido',
        criado_em__date__gte=inicio_mes
    ).aggregate(
        tempo=Avg(F('resolvido_em') - F('criado_em'))
    )['tempo']
    
    # SLA Performance (tickets resolvidos dentro do prazo SLA)
    sla_ok = Ticket.objects.filter(
        criado_em__date__gte=inicio_mes,
        status='resolvido',
        sla_deadline__isnull=False,
        resolvido_em__lte=F('sla_deadline')
    ).count()
    sla_total = Ticket.objects.filter(
        criado_em__date__gte=inicio_mes,
        sla_deadline__isnull=False
    ).count()
    sla_performance = (sla_ok / sla_total * 100) if sla_total > 0 else 0
    
    # Distribuição por Categoria
    categorias = Ticket.objects.filter(
        criado_em__date__gte=inicio_mes
    ).values('categoria').annotate(
        total=Count('id'),
        resolvidos=Count('id', filter=Q(status='resolvido')),
        tempo_medio=Avg(F('resolvido_em') - F('criado_em'))
    ).order_by('-total')
    
    # Performance dos Agentes
    agentes = Ticket.objects.filter(
        criado_em__date__gte=inicio_mes,
        agente__isnull=False
    ).values(
        'agente__first_name', 'agente__last_name'
    ).annotate(
        total_tickets=Count('id'),
        resolvidos=Count('id', filter=Q(status='resolvido')),
        tempo_medio=Avg(F('resolvido_em') - F('criado_em')),
        satisfacao_media=Avg('avaliacaosatisfacao__nota_atendimento')
    ).order_by('-total_tickets')
    
    # Tendência (últimos 30 dias) — single aggregated query instead of 30 individual queries
    from django.db.models.functions import TruncDate
    data_inicio_tendencia = hoje - timedelta(days=29)
    tendencia_qs = (
        Ticket.objects.filter(criado_em__date__gte=data_inicio_tendencia)
        .annotate(dia=TruncDate('criado_em'))
        .values('dia')
        .annotate(total=Count('id'))
        .order_by('dia')
    )
    tendencia_map = {item['dia']: item['total'] for item in tendencia_qs}
    tendencia_dados = [
        {'data': (data_inicio_tendencia + timedelta(days=i)).strftime('%d/%m'),
         'tickets': tendencia_map.get(data_inicio_tendencia + timedelta(days=i), 0)}
        for i in range(30)
    ]
    
    # Top 5 Clientes com Mais Tickets
    top_clientes = Cliente.objects.annotate(
        total_tickets=Count('tickets'),
        tickets_mes=Count('tickets', filter=Q(tickets__criado_em__date__gte=inicio_mes))
    ).order_by('-tickets_mes')[:5]
    
    # Satisfação por Categoria
    from django.db.models import Value, FloatField
    from django.db.models.functions import Cast
    satisfacao_categoria = Ticket.objects.filter(
        criado_em__date__gte=inicio_mes,
        avaliacaosatisfacao__isnull=False
    ).values('categoria').annotate(
        satisfacao_media=Avg(
            Cast(F('avaliacaosatisfacao__nota_atendimento') + F('avaliacaosatisfacao__nota_resolucao') + F('avaliacaosatisfacao__nota_tempo'), FloatField()) / Value(3.0)
        ),
        total_avaliacoes=Count('avaliacaosatisfacao')
    ).order_by('-satisfacao_media')
    
    # Horário de Pico
    from django.db.models.functions import ExtractHour
    tickets_por_hora = Ticket.objects.filter(
        criado_em__date__gte=inicio_mes
    ).annotate(hora=ExtractHour('criado_em')).values('hora').annotate(
        total=Count('id')
    ).order_by('hora')
    
    context = {
        # KPIs
        'tickets_hoje': tickets_hoje,
        'tickets_mes': tickets_mes,
        'tickets_ano': tickets_ano,
        'taxa_resolucao': round(taxa_resolucao, 1),
        'tempo_medio': tempo_medio,
        'sla_performance': round(sla_performance, 1),
        
        # Gráficos
        'categorias': categorias,
        'agentes': agentes,
        'tendencia_dados': tendencia_dados,
        'top_clientes': top_clientes,
        'satisfacao_categoria': satisfacao_categoria,
        'tickets_por_hora': tickets_por_hora,
        
        # Períodos
        'periodo_mes': inicio_mes.strftime('%m/%Y'),
        'hoje': hoje,
    }
    
    return render(request, 'dashboard/analytics/dashboard.html', context)

@login_required
def relatorio_detalhado(request):
    """Relatório detalhado personalizável"""
    
    # Filtros do formulário
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    categoria = request.GET.get('categoria')
    agente = request.GET.get('agente')
    status = request.GET.get('status')
    
    # Query base
    tickets = Ticket.objects.all()
    
    # Aplicar filtros
    if data_inicio:
        tickets = tickets.filter(criado_em__date__gte=data_inicio)
    if data_fim:
        tickets = tickets.filter(criado_em__date__lte=data_fim)
    if categoria:
        tickets = tickets.filter(categoria=categoria)
    if agente:
        tickets = tickets.filter(agente_id=agente)
    if status:
        tickets = tickets.filter(status=status)
    
    # Estatísticas do período filtrado
    total_tickets = tickets.count()
    tickets_resolvidos = tickets.filter(status='resolvido').count()
    taxa_resolucao = (tickets_resolvidos / total_tickets * 100) if total_tickets > 0 else 0
    
    # Tempo médio de resolução
    tempo_medio = tickets.filter(status='resolvido').aggregate(
        tempo=Avg(F('resolvido_em') - F('criado_em'))
    )['tempo']
    
    # Satisfação média
    satisfacao_media = tickets.filter(
        avaliacaosatisfacao__isnull=False
    ).aggregate(
        satisfacao=Avg('avaliacaosatisfacao__nota_atendimento')
    )['satisfacao']
    
    context = {
        'tickets': tickets.order_by('-criado_em')[:100],  # Últimos 100
        'total_tickets': total_tickets,
        'tickets_resolvidos': tickets_resolvidos,
        'taxa_resolucao': round(taxa_resolucao, 1),
        'tempo_medio': tempo_medio,
        'satisfacao_media': round(satisfacao_media, 1) if satisfacao_media else 0,
        'filtros': {
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'categoria': categoria,
            'agente': agente,
            'status': status,
        }
    }
    
    return render(request, 'analytics/relatorio_detalhado.html', context)
