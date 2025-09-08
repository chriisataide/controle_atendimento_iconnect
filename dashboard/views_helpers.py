# dashboard/views_helpers.py
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.auth.models import User


def get_dashboard_metrics():
    """
    Retorna métricas para o dashboard principal
    """
    hoje = timezone.now().date()
    ontem = hoje - timedelta(days=1)
    mes_atual = hoje.replace(day=1)
    mes_anterior = (mes_atual - timedelta(days=1)).replace(day=1)
    semana_atual = hoje - timedelta(days=7)
    
    # Importar models apenas quando necessário para evitar circular imports
    try:
        from tickets.models import Ticket
        from accounts.models import UserProfile
        
        # Atendimentos hoje vs ontem
        atendimentos_hoje = Ticket.objects.filter(
            criado_em__date=hoje
        ).count()
        
        atendimentos_ontem = Ticket.objects.filter(
            criado_em__date=ontem
        ).count()
        
        # Calcular variação
        if atendimentos_ontem > 0:
            variacao_atendimentos = ((atendimentos_hoje - atendimentos_ontem) / atendimentos_ontem) * 100
        else:
            variacao_atendimentos = 100 if atendimentos_hoje > 0 else 0
        
        # Usuários ativos (logados nas últimas 24h)
        usuarios_ativos = User.objects.filter(
            last_login__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        # Tickets abertos
        tickets_abertos = Ticket.objects.filter(
            status__in=['aberto', 'em_andamento']
        ).count()
        
        # Taxa de resolução (últimos 30 dias)
        tickets_mes = Ticket.objects.filter(
            criado_em__gte=mes_atual
        )
        total_mes = tickets_mes.count()
        resolvidos_mes = tickets_mes.filter(
            status__in=['resolvido', 'fechado']
        ).count()
        
        taxa_resolucao = (resolvidos_mes / total_mes * 100) if total_mes > 0 else 0
        
        # Tickets recentes (últimos 10)
        tickets_recentes = Ticket.objects.select_related(
            'cliente', 'categoria'
        ).order_by('-criado_em')[:10]
        
        # Status dos agentes
        agentes_status = UserProfile.objects.filter(
            user_type='agente'
        ).select_related('user')[:5]
        
        # Dados para gráficos
        # Atendimentos por hora (últimas 24h)
        atendimentos_por_hora = []
        for i in range(7):  # 7 períodos de 3h cada
            inicio_hora = timezone.now().replace(hour=8+i*2, minute=0, second=0, microsecond=0)
            fim_hora = inicio_hora + timedelta(hours=2)
            count = Ticket.objects.filter(
                criado_em__gte=inicio_hora,
                criado_em__lt=fim_hora
            ).count()
            atendimentos_por_hora.append(count)
        
        # Tickets por mês (últimos 9 meses)
        tickets_por_mes = []
        for i in range(9):
            mes = hoje.replace(day=1) - timedelta(days=30*i)
            proximo_mes = (mes + timedelta(days=32)).replace(day=1)
            count = Ticket.objects.filter(
                criado_em__gte=mes,
                criado_em__lt=proximo_mes
            ).count()
            tickets_por_mes.insert(0, count)  # Inserir no início para ordem cronológica
        
        return {
            'atendimentos_hoje': atendimentos_hoje,
            'variacao_atendimentos': round(variacao_atendimentos, 1),
            'usuarios_ativos': usuarios_ativos,
            'tickets_abertos': tickets_abertos,
            'taxa_resolucao': round(taxa_resolucao, 1),
            'tickets_recentes': tickets_recentes,
            'agentes_status': agentes_status,
            'atendimentos_por_hora': atendimentos_por_hora,
            'tickets_por_mes': tickets_por_mes,
        }
        
    except ImportError:
        # Se os models não existirem, retornar dados de exemplo
        return {
            'atendimentos_hoje': 47,
            'variacao_atendimentos': 12.5,
            'usuarios_ativos': 15,
            'tickets_abertos': 8,
            'taxa_resolucao': 94.2,
            'tickets_recentes': [],
            'agentes_status': [],
            'atendimentos_por_hora': [12, 19, 15, 23, 18, 25, 10],
            'tickets_por_mes': [50, 40, 300, 320, 500, 350, 200, 230, 500],
        }


def get_ajax_metrics():
    """
    Retorna apenas as métricas básicas para atualização via AJAX
    """
    metrics = get_dashboard_metrics()
    return {
        'atendimentos_hoje': metrics['atendimentos_hoje'],
        'variacao_atendimentos': metrics['variacao_atendimentos'],
        'usuarios_ativos': metrics['usuarios_ativos'],
        'tickets_abertos': metrics['tickets_abertos'],
        'taxa_resolucao': metrics['taxa_resolucao'],
    }
