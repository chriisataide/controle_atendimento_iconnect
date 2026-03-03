from django import template
from django.utils import timezone
from django.utils.timesince import timesince

register = template.Library()


@register.filter
def sla_status_color(porcentagem_tempo_restante):
    """Retorna cor baseada na porcentagem de tempo restante do SLA"""
    if porcentagem_tempo_restante <= 10:
        return "danger"
    elif porcentagem_tempo_restante <= 25:
        return "warning"
    elif porcentagem_tempo_restante <= 50:
        return "info"
    else:
        return "success"


@register.filter
def sla_status_text(porcentagem_tempo_restante):
    """Retorna texto do status baseado na porcentagem de tempo restante"""
    if porcentagem_tempo_restante <= 10:
        return "Crítico"
    elif porcentagem_tempo_restante <= 25:
        return "Atenção"
    elif porcentagem_tempo_restante <= 50:
        return "Normal"
    else:
        return "OK"


@register.filter
def tempo_ate_prazo(prazo):
    """Retorna tempo até o prazo em formato legível"""
    if not prazo:
        return "Sem prazo"

    agora = timezone.now()
    if prazo <= agora:
        return f"Vencido há {timesince(prazo, agora)}"
    else:
        diferenca = prazo - agora
        dias = diferenca.days
        horas = diferenca.seconds // 3600
        minutos = (diferenca.seconds % 3600) // 60

        if dias > 0:
            return f"{dias}d {horas}h restantes"
        elif horas > 0:
            return f"{horas}h {minutos}m restantes"
        else:
            return f"{minutos}m restantes"


@register.filter
def porcentagem_sla(ticket):
    """Calcula porcentagem do SLA consumida"""
    from dashboard.services.sla_calculator import SLACalculator

    if not ticket.politica_sla or not ticket.prazo_sla:
        return 0

    try:
        calculator = SLACalculator()
        tempo_total = calculator.calcular_tempo_util(ticket.data_criacao, ticket.prazo_sla, ticket.politica_sla)

        tempo_decorrido = calculator.calcular_tempo_util(ticket.data_criacao, timezone.now(), ticket.politica_sla)

        if tempo_total.total_seconds() == 0:
            return 100

        porcentagem = (tempo_decorrido.total_seconds() / tempo_total.total_seconds()) * 100
        return min(100, max(0, porcentagem))
    except Exception:
        return 0


@register.filter
def sla_icon(porcentagem):
    """Retorna ícone baseado na porcentagem do SLA"""
    if porcentagem >= 90:
        return "warning"
    elif porcentagem >= 75:
        return "schedule"
    elif porcentagem >= 50:
        return "access_time"
    else:
        return "check_circle"


@register.simple_tag
def sla_dashboard_stats():
    """Retorna estatísticas do dashboard SLA"""
    from dashboard.models import Ticket

    agora = timezone.now()

    stats = {
        "total_tickets": Ticket.objects.filter(status__in=["aberto", "em_andamento"]).count(),
        "sla_critico": Ticket.objects.filter(status__in=["aberto", "em_andamento"], prazo_sla__lt=agora).count(),
        "sla_atencao": 0,
        "sla_ok": 0,
    }

    # Calcular tickets em atenção e OK
    tickets_ativos = Ticket.objects.filter(
        status__in=["aberto", "em_andamento"], prazo_sla__gte=agora, politica_sla__isnull=False
    )

    for ticket in tickets_ativos:
        porcentagem = porcentagem_sla(ticket)
        if 75 <= porcentagem < 90:
            stats["sla_atencao"] += 1
        elif porcentagem < 75:
            stats["sla_ok"] += 1

    return stats
