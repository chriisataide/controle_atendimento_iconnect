"""
Views do dashboard principal, admin dashboard e métricas AJAX.
"""

import calendar
import json
import logging
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.db.models.functions import ExtractHour, ExtractWeekDay, TruncDay, TruncMonth
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from ..models import (
    Cliente,
    PerfilAgente,
    StatusTicket,
    Ticket,
)
from ..utils.security import rate_limit
from ..utils.rbac import role_required

logger = logging.getLogger("dashboard")
User = get_user_model()


def home_redirect(request):
    """
    Página inicial que redireciona inteligentemente baseado no status do usuário
    """
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect("dashboard:admin_dashboard")
        try:
            perfil = request.user.perfilusuario
            if perfil.tipo == "agente":
                return redirect("dashboard:agente_dashboard")
            elif perfil.tipo == "administrador":
                return redirect("dashboard:admin_dashboard")
        except Exception:
            pass
        return redirect("dashboard:index")
    else:
        return redirect("login")


@login_required
@role_required('admin', 'gerente', 'supervisor')
def admin_dashboard(request):
    """
    Dashboard administrativo com acesso total ao sistema
    """
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Acesso negado. Você não tem permissões administrativas.")
        return redirect("dashboard:index")

    from ..models import CategoriaTicket

    # Estatísticas gerais do sistema
    total_usuarios = User.objects.count()
    total_clientes = Cliente.objects.count()
    total_tickets = Ticket.objects.count()
    total_categorias = CategoriaTicket.objects.count()

    # Tickets por status (otimizado com uma query)
    ticket_stats = Ticket.objects.aggregate(
        abertos=Count("id", filter=Q(status="aberto")),
        andamento=Count("id", filter=Q(status="em_andamento")),
        resolvidos=Count("id", filter=Q(status="resolvido")),
        fechados=Count("id", filter=Q(status="fechado")),
        alta=Count("id", filter=Q(prioridade="alta")),
        media=Count("id", filter=Q(prioridade="media")),
        baixa=Count("id", filter=Q(prioridade="baixa")),
    )

    tickets_abertos = ticket_stats["abertos"]
    tickets_andamento = ticket_stats["andamento"]
    tickets_resolvidos = ticket_stats["resolvidos"]
    tickets_fechados = ticket_stats["fechados"]
    tickets_alta = ticket_stats["alta"]
    tickets_media = ticket_stats["media"]
    tickets_baixa = ticket_stats["baixa"]

    # Usuários ativos nas últimas 24h
    agora = timezone.now()
    usuarios_ativos_24h = User.objects.filter(last_login__gte=agora - timedelta(hours=24)).count()

    # Taxa de resolução (resolvidos + fechados / total)
    total_resolvidos = tickets_resolvidos + tickets_fechados
    taxa_resolucao = round((total_resolvidos / total_tickets * 100) if total_tickets > 0 else 0, 1)

    # Tendência de tickets dos últimos 7 dias (dados reais)
    tendencia_labels = []
    tendencia_criados = []
    tendencia_fechados = []
    for i in range(6, -1, -1):
        dia = (agora - timedelta(days=i)).date()
        tendencia_labels.append(dia.strftime("%d/%m"))
        tendencia_criados.append(Ticket.objects.filter(criado_em__date=dia).count())
        tendencia_fechados.append(
            Ticket.objects.filter(Q(status__in=["resolvido", "fechado"]), Q(atualizado_em__date=dia)).count()
        )

    # Tickets recentes com otimização
    tickets_recentes = Ticket.objects.select_related("cliente", "categoria", "agente", "sla_policy").order_by(
        "-criado_em"
    )[:10]

    # Usuários recentes
    usuarios_recentes = User.objects.order_by("-date_joined")[:5]

    # Clientes recentes
    clientes_recentes = Cliente.objects.order_by("-criado_em")[:5]

    context = {
        "total_usuarios": total_usuarios,
        "total_clientes": total_clientes,
        "total_tickets": total_tickets,
        "total_categorias": total_categorias,
        "tickets_abertos": tickets_abertos,
        "tickets_andamento": tickets_andamento,
        "tickets_resolvidos": tickets_resolvidos,
        "tickets_fechados": tickets_fechados,
        "tickets_alta": tickets_alta,
        "tickets_media": tickets_media,
        "tickets_baixa": tickets_baixa,
        "tickets_recentes": tickets_recentes,
        "usuarios_recentes": usuarios_recentes,
        "clientes_recentes": clientes_recentes,
        "usuarios_ativos_24h": usuarios_ativos_24h,
        "taxa_resolucao": taxa_resolucao,
        "tendencia_labels": json.dumps(tendencia_labels),
        "tendencia_criados": json.dumps(tendencia_criados),
        "tendencia_fechados": json.dumps(tendencia_fechados),
    }

    return render(request, "dashboard/admin/dashboard.html", context)


@method_decorator(login_required, name="dispatch")
class DashboardView(TemplateView):
    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        now = timezone.now()
        hoje = now.date()
        ontem = hoje - timedelta(days=1)
        mes_atual = hoje.replace(day=1)
        doze_meses_atras = (now - timedelta(days=365)).replace(day=1)

        # 1. Tickets por mês (ano atual Jan-Dez) — UMA query com TruncMonth
        tickets_por_mes_qs = (
            Ticket.objects.filter(criado_em__year=now.year)
            .annotate(mes=TruncMonth("criado_em"))
            .values("mes")
            .annotate(count=Count("id"))
            .order_by("mes")
        )
        mes_dict = {item["mes"].month: item["count"] for item in tickets_por_mes_qs}
        tickets_por_mes = [mes_dict.get(m, 0) for m in range(1, 13)]

        # 2. Distribuição por status (UMA query com aggregate + conditional)
        status_data = Ticket.objects.aggregate(
            aberto=Count("id", filter=Q(status=StatusTicket.ABERTO)),
            em_andamento=Count("id", filter=Q(status=StatusTicket.EM_ANDAMENTO)),
            resolvido=Count("id", filter=Q(status=StatusTicket.RESOLVIDO)),
            fechado=Count("id", filter=Q(status=StatusTicket.FECHADO)),
        )

        # 3. Performance por agente (UMA query com annotate)
        agent_performance = list(
            Ticket.objects.filter(status=StatusTicket.RESOLVIDO, agente__is_staff=True)
            .values("agente__username", "agente__first_name")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]
        )

        # 4. Heatmap de horários — UMA query com ExtractWeekDay + ExtractHour
        heatmap_qs = (
            Ticket.objects.annotate(dia=ExtractWeekDay("criado_em"), hora=ExtractHour("criado_em"))
            .values("dia", "hora")
            .annotate(count=Count("id"))
        )
        heatmap_lookup = {}
        for item in heatmap_qs:
            heatmap_lookup[(item["dia"], item["hora"])] = item["count"]

        heatmap_data = []
        for dia in range(7):
            linha = []
            for hora in range(0, 24, 2):
                total = sum(heatmap_lookup.get((dia + 1, h), 0) for h in range(hora, hora + 2))
                linha.append(total)
            heatmap_data.append(linha)

        # 5. Atendimentos por hora — UMA query
        hora_qs = Ticket.objects.annotate(hora=ExtractHour("criado_em")).values("hora").annotate(count=Count("id"))
        hora_dict = {item["hora"]: item["count"] for item in hora_qs}
        atendimentos_por_hora = [hora_dict.get(h, 0) for h in range(24)]

        # --- Mêses em Português ---
        MESES_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

        # --- Dados Semestral (6 meses do semestre atual) ---
        sem_start_month = 1 if now.month <= 6 else 7
        semestre_labels = []
        tickets_por_semestre = []
        for i in range(6):
            s_month = sem_start_month + i
            s_year = now.year
            while s_month > 12:
                s_month -= 12
                s_year += 1
            semestre_labels.append(MESES_PT[s_month - 1])
            tickets_por_semestre.append(mes_dict.get(s_month, 0))

        # --- Dados Mensal (dias do mês atual) ---
        days_in_month = calendar.monthrange(hoje.year, hoje.month)[1]
        tickets_por_dia_qs = (
            Ticket.objects.filter(criado_em__year=hoje.year, criado_em__month=hoje.month)
            .annotate(dia=TruncDay("criado_em"))
            .values("dia")
            .annotate(count=Count("id"))
        )
        dia_dict = {item["dia"].date(): item["count"] for item in tickets_por_dia_qs}
        mensal_labels = []
        tickets_por_mes_atual = []
        for day in range(1, days_in_month + 1):
            mensal_labels.append(str(day))
            tickets_por_mes_atual.append(dia_dict.get(hoje.replace(day=day), 0))

        context.update(
            {
                "tickets_por_mes": json.dumps(tickets_por_mes),
                "status_data": json.dumps(status_data),
                "agent_performance": json.dumps(agent_performance),
                "heatmap_data": json.dumps(heatmap_data),
                "atendimentos_por_hora": json.dumps(atendimentos_por_hora),
                "semestre_labels": json.dumps(semestre_labels),
                "tickets_por_semestre": json.dumps(tickets_por_semestre),
                "mensal_labels": json.dumps(mensal_labels),
                "tickets_por_mes_atual": json.dumps(tickets_por_mes_atual),
            }
        )

        # Atendimentos hoje vs ontem
        atendimentos_hoje = Ticket.objects.filter(criado_em__date=hoje).count()
        atendimentos_ontem = Ticket.objects.filter(criado_em__date=ontem).count()

        if atendimentos_ontem > 0:
            variacao_atendimentos = ((atendimentos_hoje - atendimentos_ontem) / atendimentos_ontem) * 100
        else:
            variacao_atendimentos = 100 if atendimentos_hoje > 0 else 0

        # Usuários ativos (logados nas últimas 24h)
        usuarios_ativos = User.objects.filter(last_login__gte=timezone.now() - timedelta(hours=24)).count()

        # Tickets abertos
        tickets_abertos = Ticket.objects.filter(status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO]).count()

        # Taxa de resolução
        tickets_mes = Ticket.objects.filter(criado_em__gte=mes_atual)
        total_mes = tickets_mes.count()
        resolvidos_mes = tickets_mes.filter(status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO]).count()
        taxa_resolucao = (resolvidos_mes / total_mes * 100) if total_mes > 0 else 0

        context.update(
            {
                "atendimentos_hoje": atendimentos_hoje,
                "variacao_atendimentos": round(variacao_atendimentos, 1),
                "usuarios_ativos": usuarios_ativos,
                "tickets_abertos": tickets_abertos,
                "taxa_resolucao": round(taxa_resolucao, 1),
            }
        )

        # Tickets recentes com relacionamentos
        context["tickets_recentes"] = Ticket.objects.select_related("cliente").order_by("-criado_em")[:10]

        # Agentes status (busca real do banco)
        try:
            agentes_qs = PerfilAgente.objects.select_related("user").filter(user__is_active=True)[:10]
            context["agentes_status"] = agentes_qs
        except Exception:
            context["agentes_status"] = []

        # Dados legados mantidos para compatibilidade
        context["total_clientes"] = Cliente.objects.count()
        context["tickets_fechados"] = resolvidos_mes
        context["total_tickets"] = Ticket.objects.count()

        # === SLA Dados dinâmicos ===
        try:
            from ..models import SLAAlert, SLAPolicy

            context["sla_policies_count"] = SLAPolicy.objects.filter(is_active=True).count()
            context["sla_alerts_count"] = SLAAlert.objects.filter(resolved_at__isnull=True).count()
        except Exception:
            context["sla_policies_count"] = 0
            context["sla_alerts_count"] = 0

        # === WhatsApp status dinâmico ===
        try:
            from ..models import WhatsAppBusinessAccount

            whatsapp_ativo = WhatsAppBusinessAccount.objects.filter(ativo=True).exists()
            context["whatsapp_status"] = "Conectado" if whatsapp_ativo else "Desconectado"
        except Exception:
            context["whatsapp_status"] = "Desconectado"

        # === Variações percentuais reais ===
        inicio_mes_passado = (mes_atual - timedelta(days=1)).replace(day=1)
        usuarios_mes_passado = User.objects.filter(last_login__gte=inicio_mes_passado, last_login__lt=mes_atual).count()
        if usuarios_mes_passado > 0:
            context["variacao_usuarios"] = round(
                ((usuarios_ativos - usuarios_mes_passado) / usuarios_mes_passado) * 100, 1
            )
        else:
            context["variacao_usuarios"] = 100 if usuarios_ativos > 0 else 0

        # Variação de tickets abertos (semana atual vs semana passada)
        semana_passada_inicio = hoje - timedelta(days=14)
        semana_passada_fim = hoje - timedelta(days=7)
        tickets_semana_passada = Ticket.objects.filter(
            criado_em__date__gte=semana_passada_inicio,
            criado_em__date__lt=semana_passada_fim,
            status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO],
        ).count()
        if tickets_semana_passada > 0:
            context["variacao_tickets"] = round(
                ((tickets_abertos - tickets_semana_passada) / tickets_semana_passada) * 100, 1
            )
        else:
            context["variacao_tickets"] = 0

        # Variação da taxa de resolução (mês atual vs mês anterior)
        tickets_mes_passado = Ticket.objects.filter(criado_em__gte=inicio_mes_passado, criado_em__lt=mes_atual)
        total_mes_passado = tickets_mes_passado.count()
        resolvidos_mes_passado = tickets_mes_passado.filter(
            status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO]
        ).count()
        taxa_resolucao_passada = (resolvidos_mes_passado / total_mes_passado * 100) if total_mes_passado > 0 else 0
        context["variacao_resolucao"] = round(taxa_resolucao - taxa_resolucao_passada, 1)

        # === Tendência de tickets (últimos 30 dias vs 30 dias anteriores) ===
        trinta_dias = hoje - timedelta(days=30)
        sessenta_dias = hoje - timedelta(days=60)
        tickets_30d = Ticket.objects.filter(criado_em__date__gte=trinta_dias).count()
        tickets_60_30d = Ticket.objects.filter(
            criado_em__date__gte=sessenta_dias, criado_em__date__lt=trinta_dias
        ).count()
        if tickets_60_30d > 0:
            context["tendencia_tickets"] = round(((tickets_30d - tickets_60_30d) / tickets_60_30d) * 100, 1)
        else:
            context["tendencia_tickets"] = 100 if tickets_30d > 0 else 0

        # === Resumo mensal ===
        if total_mes_passado > 0:
            context["resumo_mensal_pct"] = round(((total_mes - total_mes_passado) / total_mes_passado) * 100, 1)
        else:
            context["resumo_mensal_pct"] = 100 if total_mes > 0 else 0

        # === Tickets recentes para timeline ===
        context["tickets_timeline"] = Ticket.objects.select_related("cliente", "agente").order_by("-criado_em")[:3]

        # === Labels de meses (ano calendário atual: Jan-Dez) ===
        meses_labels = MESES_PT[:]
        context["meses_labels"] = json.dumps(meses_labels)

        # === Tempo Médio de Resolução ===
        tempo_medio_qs = (
            Ticket.objects.filter(
                status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO],
                resolvido_em__isnull=False,
                criado_em__isnull=False,
            )
            .annotate(duracao=ExpressionWrapper(F("resolvido_em") - F("criado_em"), output_field=DurationField()))
            .aggregate(media=Avg("duracao"))
        )

        tempo_medio = tempo_medio_qs.get("media")
        if tempo_medio:
            total_seconds = int(tempo_medio.total_seconds())
            hours = total_seconds // 3600
            if hours >= 24:
                days = hours // 24
                context["tempo_medio_resolucao"] = f"{days}d {hours % 24}h"
            else:
                minutes = (total_seconds % 3600) // 60
                context["tempo_medio_resolucao"] = f"{hours}h {minutes}m"
        else:
            context["tempo_medio_resolucao"] = "--"

        # Variação do tempo médio vs mês anterior
        tempo_medio_atual_qs = (
            Ticket.objects.filter(
                status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO],
                resolvido_em__isnull=False,
                resolvido_em__gte=mes_atual,
            )
            .annotate(duracao=ExpressionWrapper(F("resolvido_em") - F("criado_em"), output_field=DurationField()))
            .aggregate(media=Avg("duracao"))
        )

        tempo_medio_passado_qs = (
            Ticket.objects.filter(
                status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO],
                resolvido_em__isnull=False,
                resolvido_em__gte=inicio_mes_passado,
                resolvido_em__lt=mes_atual,
            )
            .annotate(duracao=ExpressionWrapper(F("resolvido_em") - F("criado_em"), output_field=DurationField()))
            .aggregate(media=Avg("duracao"))
        )

        tm_atual = tempo_medio_atual_qs.get("media")
        tm_passado = tempo_medio_passado_qs.get("media")
        if tm_atual and tm_passado and tm_passado.total_seconds() > 0:
            context["variacao_tempo_medio"] = round(
                ((tm_atual.total_seconds() - tm_passado.total_seconds()) / tm_passado.total_seconds()) * 100, 1
            )
        else:
            context["variacao_tempo_medio"] = 0

        # === Tickets Urgentes ===
        tickets_urgentes = list(
            Ticket.objects.filter(
                Q(prioridade="critica", status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO])
                | Q(sla_resolution_deadline__lt=now, status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO])
                | Q(is_escalated=True, status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO])
            )
            .select_related("cliente", "agente", "categoria")
            .distinct()
            .order_by("-criado_em")[:10]
        )
        context["tickets_urgentes"] = tickets_urgentes

        # === Agentes Online ===
        try:
            context["agentes_online"] = PerfilAgente.objects.filter(status="online").count()
        except Exception:
            context["agentes_online"] = 0

        return context


@login_required
@role_required('admin', 'gerente', 'supervisor')
@rate_limit(max_requests=100, window_seconds=3600)
def ajax_metrics(request):
    """
    Endpoint AJAX para atualização das métricas em tempo real
    """
    if request.method == "GET":
        try:
            hoje = timezone.now().date()
            ontem = hoje - timedelta(days=1)

            atendimentos_hoje = Ticket.objects.filter(criado_em__date=hoje).count()
            atendimentos_ontem = Ticket.objects.filter(criado_em__date=ontem).count()

            if atendimentos_ontem > 0:
                variacao_atendimentos = ((atendimentos_hoje - atendimentos_ontem) / atendimentos_ontem) * 100
            else:
                variacao_atendimentos = 100 if atendimentos_hoje > 0 else 0

            usuarios_ativos = User.objects.filter(last_login__gte=timezone.now() - timedelta(hours=24)).count()

            tickets_abertos = Ticket.objects.filter(status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO]).count()

            mes_atual = hoje.replace(day=1)
            tickets_mes = Ticket.objects.filter(criado_em__gte=mes_atual)
            total_mes = tickets_mes.count()
            resolvidos_mes = tickets_mes.filter(status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO]).count()
            taxa_resolucao = (resolvidos_mes / total_mes * 100) if total_mes > 0 else 0

            metrics = {
                "atendimentos_hoje": atendimentos_hoje,
                "variacao_atendimentos": round(variacao_atendimentos, 1),
                "usuarios_ativos": usuarios_ativos,
                "tickets_abertos": tickets_abertos,
                "taxa_resolucao": round(taxa_resolucao, 1),
            }

            return JsonResponse(metrics)

        except Exception as e:
            logger.error(f"Erro em ajax_metrics: {e}", exc_info=True)
            return JsonResponse({"error": "Erro interno ao processar métricas."}, status=500)

    return JsonResponse({"error": "Método não permitido"}, status=405)


@login_required
def tickets_chart_api(request):
    """
    API para filtrar dados do gráfico de tickets por período
    """
    period = request.GET.get("period", "30days")
    now = timezone.now()

    if period == "7days":
        labels = []
        data = []
        for i in range(7):
            date = now.date() - timedelta(days=i)
            count = Ticket.objects.filter(criado_em__date=date).count()
            labels.insert(0, date.strftime("%d/%m"))
            data.insert(0, count)

    elif period == "30days":
        labels = []
        data = []
        for i in range(4):
            end_date = now.date() - timedelta(days=i * 7)
            start_date = end_date - timedelta(days=6)
            count = Ticket.objects.filter(criado_em__date__range=[start_date, end_date]).count()
            labels.insert(0, f'{start_date.strftime("%d/%m")} - {end_date.strftime("%d/%m")}')
            data.insert(0, count)

    elif period == "90days":
        labels = []
        data = []
        for i in range(3):
            year = now.year
            month = now.month - i
            while month <= 0:
                month += 12
                year -= 1
            count = Ticket.objects.filter(criado_em__year=year, criado_em__month=month).count()
            month_names = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
            labels.insert(0, f"{month_names[month - 1]} {year}")
            data.insert(0, count)

    else:
        labels = []
        data = []

    return JsonResponse({"labels": labels, "data": data})
