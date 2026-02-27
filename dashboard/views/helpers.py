# dashboard/views_helpers.py
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.auth.models import User
import json
import logging

logger = logging.getLogger('dashboard')


def get_role_filtered_tickets(user, base_queryset=None):
    """
    Filtra tickets baseado no papel do usuário (RBAC).
    
    - Superuser/Staff: vê todos os tickets
    - Agente (tem PerfilAgente): vê tickets atribuídos a ele + não atribuídos
    - Cliente: vê apenas tickets onde cliente.email == user.email
    
    Args:
        user: O usuário autenticado (request.user)
        base_queryset: QuerySet base opcional. Se None, usa Ticket.objects.all()
    
    Returns:
        QuerySet filtrado por papel do usuário
    """
    from ..models import Ticket, Cliente
    
    if base_queryset is None:
        base_queryset = Ticket.objects.all()
    
    # Admin/Staff: acesso total
    if user.is_superuser or user.is_staff:
        return base_queryset
    
    # Agente: tickets atribuídos a ele + não atribuídos (para auto-atribuição)
    if hasattr(user, 'perfilagente'):
        return base_queryset.filter(
            Q(agente=user) | Q(agente__isnull=True)
        )
    
    # Cliente: apenas seus próprios tickets
    try:
        cliente = Cliente.objects.get(email=user.email)
        return base_queryset.filter(cliente=cliente)
    except Cliente.DoesNotExist:
        # Usuário sem papel definido — sem acesso a tickets
        return base_queryset.none()


def user_can_access_ticket(user, ticket):
    """
    Verifica se um usuário específico pode acessar um ticket específico.
    
    Returns:
        bool: True se o usuário tem acesso ao ticket
    """
    from ..models import Cliente
    
    # Admin/Staff: acesso total
    if user.is_superuser or user.is_staff:
        return True
    
    # Agente: pode acessar tickets atribuídos a ele ou não atribuídos
    if hasattr(user, 'perfilagente'):
        return ticket.agente == user or ticket.agente is None
    
    # Cliente: apenas seus próprios tickets
    try:
        cliente = Cliente.objects.get(email=user.email)
        return ticket.cliente_id == cliente.id
    except Cliente.DoesNotExist:
        return False


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
        from ..models import Ticket, PerfilAgente
        
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
            'cliente', 'categoria', 'agente'
        ).order_by('-criado_em')[:10]
        
        # Status dos agentes
        agentes_status = PerfilAgente.objects.select_related('user')[:5]
        
        # Dados para gráficos - usar dados reais de analytics
        analytics_data = get_analytics_data()
        
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
        
        return {
            'atendimentos_hoje': atendimentos_hoje,
            'variacao_atendimentos': round(variacao_atendimentos, 1),
            'usuarios_ativos': usuarios_ativos,
            'tickets_abertos': tickets_abertos,
            'taxa_resolucao': round(taxa_resolucao, 1),
            'tickets_recentes': tickets_recentes,
            'agentes_status': agentes_status,
            'atendimentos_por_hora': json.dumps(atendimentos_por_hora),
            # Usar dados reais de analytics em vez de dados de exemplo
            'tickets_por_mes': json.dumps(analytics_data.get('tickets_por_mes', [])),
            'status_data': json.dumps(analytics_data.get('status_data', {}), ensure_ascii=False),
            'agent_performance': json.dumps(analytics_data.get('agent_performance', []), ensure_ascii=False),
            'heatmap_data': json.dumps(analytics_data.get('heatmap_data', [])),
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


def get_analytics_data():
    """
    Retorna dados específicos para gráficos e analytics
    """
    try:
        from ..models import Ticket
        
        # Dados para gráfico de linha (últimos 12 meses)
        hoje = timezone.now().date()
        tickets_por_mes = []
        for i in range(12):
            mes = hoje.replace(day=1) - timedelta(days=30*i)
            proximo_mes = mes + timedelta(days=32)
            proximo_mes = proximo_mes.replace(day=1)
            
            count = Ticket.objects.filter(
                criado_em__date__gte=mes,
                criado_em__date__lt=proximo_mes
            ).count()
            tickets_por_mes.insert(0, count)
        
        # Distribuição por status
        status_counts = Ticket.objects.values('status').annotate(count=Count('id'))
        status_data = {item['status']: item['count'] for item in status_counts}
        
        # Performance por agente
        agent_performance = Ticket.objects.filter(
            status__in=['resolvido', 'fechado']
        ).values('agente__username').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Heatmap de horários (por dia da semana e hora)
        heatmap_data = []
        for dia_semana in range(7):  # 0=domingo, 6=sábado
            dia_data = []
            for hora in range(0, 24, 2):  # A cada 2 horas
                count = Ticket.objects.filter(
                    criado_em__week_day=dia_semana+1,
                    criado_em__hour__gte=hora,
                    criado_em__hour__lt=hora+2
                ).count()
                dia_data.append(count)
            heatmap_data.append(dia_data)
        
        return {
            'tickets_por_mes': json.dumps(tickets_por_mes),
            'status_data': status_data,
            'agent_performance': list(agent_performance),
            'heatmap_data': heatmap_data,
            'tickets_abertos': status_data.get('aberto', 0),
            'tickets_andamento': status_data.get('em_andamento', 0),
            'tickets_resolvidos': status_data.get('resolvido', 0),
            'tickets_fechados': status_data.get('fechado', 0),
        }
        
    except Exception:
        # Dados de exemplo em caso de erro
        return {
            'tickets_por_mes': json.dumps([10, 15, 12, 20, 25, 18, 22, 30, 28, 35, 40, 38]),
            'status_data': {'aberto': 8, 'em_andamento': 15, 'resolvido': 42, 'fechado': 120},
            'agent_performance': [],
            'heatmap_data': [],
            'tickets_abertos': 8,
            'tickets_andamento': 15,
            'tickets_resolvidos': 42,
            'tickets_fechados': 120,
        }
