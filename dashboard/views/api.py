"""
API Views - REST endpoints for iConnect helpdesk
"""

import logging
from datetime import timedelta

from django.db.models import Avg, Count, F, Q
from django.utils import timezone
from rest_framework import generics, permissions, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import (
    AgentBadge,
    APIKey,
    CannedResponse,
    Cliente,
    CustomerHealthScore,
    GamificationBadge,
    SharedDashboard,
    SLAPolicy,
    SLAViolation,
    Ticket,
    TimeEntry,
    WebhookEndpoint,
)
from ..utils.rbac import ROLE_ADMIN, ROLE_AGENTE, ROLE_CLIENTE, ROLE_SUPERVISOR, get_user_role


def _safe_period_days(request, default=30, max_days=365):
    """Sanitiza o parâmetro 'days' de query string (previne abuso de recursos)."""
    try:
        days = int(request.query_params.get("days", default))
    except (ValueError, TypeError):
        days = default
    return max(1, min(days, max_days))


from ..serializers import (
    ClienteSerializer,
    TicketCreateSerializer,
    TicketSerializer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RBAC helpers for API views
# ---------------------------------------------------------------------------


def _get_user_role(user):
    """Returns the user's role from UserRole, defaulting to 'agente'."""
    return get_user_role(user)


def _is_admin_or_supervisor(user):
    """Check if user is admin or supervisor."""
    role = _get_user_role(user)
    return role in (ROLE_ADMIN, ROLE_SUPERVISOR) or user.is_superuser


class IsAdminOrSupervisor(permissions.BasePermission):
    """Only allow admin or supervisor users."""

    def has_permission(self, request, view):
        return _is_admin_or_supervisor(request.user)


# ---------------------------------------------------------------------------
# Ticket CRUD
# ---------------------------------------------------------------------------


class TicketListCreateAPIView(generics.ListCreateAPIView):
    """GET /api/tickets/ — lista tickets; POST /api/tickets/ — cria ticket"""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TicketCreateSerializer
        return TicketSerializer

    def get_queryset(self):
        qs = Ticket.objects.select_related("cliente", "agente", "categoria").order_by("-criado_em")

        # RBAC: filtrar tickets por role do usuario
        user = self.request.user
        role = _get_user_role(user)
        if role == ROLE_CLIENTE:
            # Clientes veem apenas seus proprios tickets
            qs = qs.filter(cliente__user=user)
        elif role == ROLE_AGENTE:
            # Agentes veem apenas tickets atribuidos a eles
            qs = qs.filter(agente=user)
        # admin/supervisor veem todos

        # Filtros opcionais via query params
        params = self.request.query_params
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("prioridade"):
            qs = qs.filter(prioridade=params["prioridade"])
        if params.get("agente"):
            qs = qs.filter(agente_id=params["agente"])
        if params.get("cliente"):
            qs = qs.filter(cliente_id=params["cliente"])
        if params.get("search"):
            term = params["search"]
            qs = qs.filter(Q(titulo__icontains=term) | Q(descricao__icontains=term) | Q(numero__icontains=term))
        return qs


class TicketDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PUT/PATCH/DELETE /api/tickets/<pk>/"""

    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Ticket.objects.select_related("cliente", "agente", "categoria")
        user = self.request.user
        role = _get_user_role(user)
        if role == ROLE_CLIENTE:
            return qs.filter(cliente__user=user)
        elif role == ROLE_AGENTE:
            return qs.filter(agente=user)
        return qs  # admin/supervisor


# ---------------------------------------------------------------------------
# Cliente CRUD
# ---------------------------------------------------------------------------


class ClienteListCreateAPIView(generics.ListCreateAPIView):
    """GET /api/clientes/ — lista; POST /api/clientes/ — cria"""

    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Cliente.objects.order_by("-criado_em")

        # RBAC: filtrar clientes por role do usuario
        user = self.request.user
        role = _get_user_role(user)
        if role == ROLE_CLIENTE:
            # Clientes veem apenas a si mesmos
            qs = qs.filter(user=user)
        elif role == ROLE_AGENTE:
            # Agentes veem apenas clientes dos seus tickets
            client_ids = Ticket.objects.filter(agente=user).values_list("cliente_id", flat=True).distinct()
            qs = qs.filter(id__in=client_ids)
        # admin/supervisor veem todos

        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(Q(nome__icontains=search) | Q(email__icontains=search) | Q(telefone__icontains=search))
        return qs


class ClienteDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PUT/PATCH/DELETE /api/clientes/<pk>/"""

    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Cliente.objects.all()
        user = self.request.user
        role = _get_user_role(user)
        if role == ROLE_CLIENTE:
            return qs.filter(user=user)
        elif role == ROLE_AGENTE:
            client_ids = Ticket.objects.filter(agente=user).values_list("cliente_id", flat=True).distinct()
            return qs.filter(id__in=client_ids)
        return qs  # admin/supervisor


# ---------------------------------------------------------------------------
# Analytics endpoints
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_overview(request):
    """Visao geral de metricas"""
    now = timezone.now()
    period = _safe_period_days(request)
    since = now - timedelta(days=period)

    tickets = Ticket.objects.filter(criado_em__gte=since)
    total = tickets.count()
    by_status = dict(tickets.values_list("status").annotate(c=Count("id")).values_list("status", "c"))

    resolved = tickets.filter(status__in=["resolvido", "fechado"])
    avg_hours = None
    if resolved.filter(resolvido_em__isnull=False).exists():
        avg_delta = resolved.filter(resolvido_em__isnull=False).aggregate(avg=Avg(F("resolvido_em") - F("criado_em")))[
            "avg"
        ]
        if avg_delta:
            avg_hours = round(avg_delta.total_seconds() / 3600, 1)

    return Response(
        {
            "period_days": period,
            "total_tickets": total,
            "by_status": by_status,
            "resolved_count": resolved.count(),
            "avg_resolution_hours": avg_hours,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_time_series(request):
    """Tickets ao longo do tempo (agrupados por dia)"""
    period = _safe_period_days(request)
    since = timezone.now() - timedelta(days=period)

    from django.db.models.functions import TruncDate

    data = (
        Ticket.objects.filter(criado_em__gte=since)
        .annotate(day=TruncDate("criado_em"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    return Response({"series": list(data)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_satisfaction(request):
    """Metricas de satisfacao"""
    try:
        from ..models import AvaliacaoSatisfacao

        period = _safe_period_days(request)
        since = timezone.now() - timedelta(days=period)
        evals = AvaliacaoSatisfacao.objects.filter(criado_em__gte=since)
        avg_data = evals.aggregate(
            avg_atendimento=Avg("nota_atendimento"),
            avg_resolucao=Avg("nota_resolucao"),
            avg_tempo=Avg("nota_tempo"),
        )
        return Response(
            {
                "total_evaluations": evals.count(),
                "averages": {k: round(v, 2) if v else None for k, v in avg_data.items()},
            }
        )
    except Exception as e:
        logger.error(f"Erro em analytics_satisfaction: {e}")
        return Response({"error": "Erro interno ao obter métricas de satisfação"}, status=500)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_sla_metrics(request):
    """Metricas de SLA"""
    period = _safe_period_days(request)
    since = timezone.now() - timedelta(days=period)
    violations = SLAViolation.objects.filter(created_at__gte=since)
    total_tickets = Ticket.objects.filter(criado_em__gte=since).count()
    violation_count = violations.count()
    compliance = round((1 - violation_count / total_tickets) * 100, 1) if total_tickets else 100.0

    return Response(
        {
            "total_tickets": total_tickets,
            "sla_violations": violation_count,
            "compliance_rate": compliance,
            "policies_active": SLAPolicy.objects.filter(is_active=True).count(),
        }
    )


# ---------------------------------------------------------------------------
# ML prediction stubs (placeholder until proper ML is integrated)
# ---------------------------------------------------------------------------


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ml_predict_priority(request):
    """Predizer prioridade de um ticket baseado no texto"""
    title = request.data.get("titulo", "")
    description = request.data.get("descricao", "")
    if not title and not description:
        return Response({"error": "Informe titulo ou descricao"}, status=400)

    # Heuristica simples ate ML real ser integrado
    text = f"{title} {description}".lower()
    urgency_words = ["urgente", "critico", "emergencia", "parado", "fora do ar", "nao funciona"]
    high_words = ["erro", "bug", "falha", "problema grave", "impacto"]

    if any(w in text for w in urgency_words):
        priority = "critica"
        confidence = 0.85
    elif any(w in text for w in high_words):
        priority = "alta"
        confidence = 0.75
    else:
        priority = "media"
        confidence = 0.60

    return Response(
        {
            "predicted_priority": priority,
            "confidence": confidence,
            "model_version": "heuristic-v1",
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ml_predict_category(request):
    """Predizer categoria de um ticket baseado no texto"""
    title = request.data.get("titulo", "")
    description = request.data.get("descricao", "")
    if not title and not description:
        return Response({"error": "Informe titulo ou descricao"}, status=400)

    from ..models import CategoriaTicket

    categories = list(CategoriaTicket.objects.values_list("nome", flat=True))
    if not categories:
        return Response({"predicted_category": "Geral", "confidence": 0.5})

    text = f"{title} {description}".lower()
    best = categories[0] if categories else "Geral"
    best_score = 0
    for cat in categories:
        score = sum(1 for word in cat.lower().split() if word in text)
        if score > best_score:
            best_score = score
            best = cat

    return Response(
        {
            "predicted_category": best,
            "confidence": min(0.5 + best_score * 0.15, 0.95),
            "model_version": "heuristic-v1",
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ml_predict_resolution_time(request):
    """Predizer tempo de resolucao baseado em historico"""
    priority = request.data.get("prioridade", "media")

    # Buscar media historica por prioridade
    resolved = Ticket.objects.filter(
        prioridade=priority,
        status__in=["resolvido", "fechado"],
        resolvido_em__isnull=False,
    )
    if resolved.exists():
        avg_delta = resolved.aggregate(avg=Avg(F("resolvido_em") - F("criado_em")))["avg"]
        hours = round(avg_delta.total_seconds() / 3600, 1) if avg_delta else None
    else:
        defaults = {"critica": 2, "alta": 8, "media": 24, "baixa": 72}
        hours = defaults.get(priority, 24)

    return Response(
        {
            "predicted_hours": hours,
            "priority": priority,
            "model_version": "historical-avg-v1",
        }
    )


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([])
def health_check(request):
    """Health check endpoint para load balancers e monitoramento"""
    from django.db import connection

    checks = {"status": "healthy", "timestamp": timezone.now().isoformat()}
    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
        checks["status"] = "unhealthy"

    try:
        from django.core.cache import cache

        cache.set("_healthcheck", 1, 10)
        checks["cache"] = "ok" if cache.get("_healthcheck") == 1 else "error"
    except Exception:
        checks["cache"] = "unavailable"

    # Não expor contagem de tickets em endpoint público (information disclosure)
    http_status = 200 if checks["status"] == "healthy" else 503
    return Response(checks, status=http_status)


# ---------------------------------------------------------------------------
# Canned Responses / Macros
# ---------------------------------------------------------------------------


class CannedResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = CannedResponse
        fields = "__all__"
        read_only_fields = ["id", "criado_por", "uso_count", "criado_em", "atualizado_em"]

    def create(self, validated_data):
        validated_data["criado_por"] = self.context["request"].user
        return super().create(validated_data)


class CannedResponseListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = CannedResponseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return CannedResponse.objects.filter(Q(compartilhado=True) | Q(criado_por=user)).order_by("-uso_count")


class CannedResponseDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CannedResponseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if _is_admin_or_supervisor(user):
            # Admin/supervisor podem editar todas (incluindo compartilhadas)
            return CannedResponse.objects.all()
        # Usuarios comuns so podem editar suas proprias respostas
        return CannedResponse.objects.filter(criado_por=user)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_tickets_excel(request):
    """Exportar tickets para Excel"""
    from django.http import HttpResponse
    from openpyxl import Workbook

    period = _safe_period_days(request)  # Already capped at 365
    since = timezone.now() - timedelta(days=period)

    tickets = (
        Ticket.objects.filter(criado_em__gte=since)
        .select_related("cliente", "agente", "categoria")
        .order_by("-criado_em")
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Tickets"
    headers = [
        "Numero",
        "Titulo",
        "Status",
        "Prioridade",
        "Tipo",
        "Cliente",
        "Agente",
        "Categoria",
        "Criado em",
        "Resolvido em",
    ]
    ws.append(headers)

    for t in tickets.iterator():  # .iterator() to avoid loading all into memory
        ws.append(
            [
                t.numero,
                t.titulo,
                t.status,
                t.prioridade,
                t.tipo,
                t.cliente.nome if t.cliente else "",
                t.agente.get_full_name() if t.agente else "",
                t.categoria.nome if t.categoria else "",
                t.criado_em.strftime("%Y-%m-%d %H:%M") if t.criado_em else "",
                t.resolvido_em.strftime("%Y-%m-%d %H:%M") if t.resolvido_em else "",
            ]
        )

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="tickets_{period}d.xlsx"'
    wb.save(response)
    return response


# ===========================================================================
# Bulk Actions
# ===========================================================================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bulk_action_tickets(request):
    """Acao em massa em tickets: fechar, reatribuir, mudar prioridade"""
    if not _is_admin_or_supervisor(request.user):
        return Response({"error": "Apenas admin/supervisor podem executar acoes em massa"}, status=403)

    ticket_ids = request.data.get("ticket_ids", [])
    action = request.data.get("action")
    value = request.data.get("value")

    if not ticket_ids or not action:
        return Response({"error": "ticket_ids e action sao obrigatorios"}, status=400)

    tickets = Ticket.objects.filter(id__in=ticket_ids)
    count = tickets.count()

    if action == "close":
        tickets.update(status="fechado", fechado_em=timezone.now())
    elif action == "change_status":
        tickets.update(status=value)
    elif action == "change_priority":
        tickets.update(prioridade=value)
    elif action == "assign":
        tickets.update(agente_id=value)
    else:
        return Response({"error": f"Acao '{action}' desconhecida"}, status=400)

    return Response({"updated": count, "action": action})


# ===========================================================================
# Time Entries
# ===========================================================================


class TimeEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeEntry
        fields = "__all__"
        read_only_fields = ["id", "usuario", "criado_em"]


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def ticket_time_entries(request, pk):
    """GET: listar registros de tempo; POST: adicionar registro"""
    try:
        ticket = Ticket.objects.get(pk=pk)
    except Ticket.DoesNotExist:
        return Response({"error": "Ticket nao encontrado"}, status=404)

    if request.method == "GET":
        entries = TimeEntry.objects.filter(ticket=ticket).order_by("-data")
        data = TimeEntrySerializer(entries, many=True).data
        total_min = sum(e.minutos for e in entries)
        return Response({"entries": data, "total_minutes": total_min, "total_hours": round(total_min / 60, 1)})

    # POST
    ser = TimeEntrySerializer(data=request.data)
    if ser.is_valid():
        ser.save(ticket=ticket, usuario=request.user)
        return Response(ser.data, status=201)
    return Response(ser.errors, status=400)


# ===========================================================================
# Webhooks Management
# ===========================================================================


class WebhookSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEndpoint
        fields = "__all__"
        read_only_fields = ["id", "criado_por", "last_triggered", "failure_count", "criado_em", "atualizado_em"]


class WebhookListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = WebhookSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSupervisor]
    queryset = WebhookEndpoint.objects.filter(is_active=True)

    def perform_create(self, serializer):
        serializer.save(criado_por=self.request.user)


class WebhookDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WebhookSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSupervisor]
    queryset = WebhookEndpoint.objects.all()


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def webhook_external_trigger(request):
    """Trigger externo para disparar workflows"""
    event = request.data.get("event")
    payload = request.data.get("data", {})

    if not event:
        return Response({"error": "event obrigatorio"}, status=400)

    from ..services.webhook_service import webhook_service

    webhook_service.trigger_event(event, payload)
    return Response({"triggered": event})


# ===========================================================================
# API Keys
# ===========================================================================


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def api_key_list_create(request):
    """GET: listar chaves; POST: criar nova chave de API"""
    if not _is_admin_or_supervisor(request.user):
        return Response({"error": "Apenas administradores podem gerenciar API keys"}, status=403)

    if request.method == "GET":
        keys = APIKey.objects.filter(criado_por=request.user).values(
            "id", "nome", "prefix", "is_active", "rate_limit", "permissions", "expires_at", "last_used", "criado_em"
        )
        return Response(list(keys))

    # POST - Criar nova API Key
    nome = request.data.get("nome", "API Key")
    perms = request.data.get("permissions", ["tickets.read"])
    rate_limit = request.data.get("rate_limit", 1000)

    raw_key, key_hash, prefix = APIKey.generate_key()
    api_key = APIKey.objects.create(
        nome=nome,
        key_hash=key_hash,
        prefix=prefix,
        criado_por=request.user,
        permissions=perms,
        rate_limit=rate_limit,
    )
    return Response(
        {
            "id": api_key.id,
            "nome": api_key.nome,
            "key": raw_key,  # Mostrado apenas uma vez
            "prefix": prefix,
            "message": "Guarde a chave - ela nao sera mostrada novamente!",
        },
        status=201,
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def api_key_revoke(request, pk):
    """Revogar (desativar) uma API key"""
    try:
        key = APIKey.objects.get(pk=pk, criado_por=request.user)
        key.is_active = False
        key.save(update_fields=["is_active"])
        return Response({"revoked": True})
    except APIKey.DoesNotExist:
        return Response({"error": "API Key nao encontrada"}, status=404)


# ===========================================================================
# AI - Auto-triage, Suggest Response, Summarize, Sentiment, Duplicates
# ===========================================================================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_triage_ticket(request, pk):
    """Auto-triagem de ticket: categorizar + priorizar + duplicatas + KB"""
    try:
        ticket = Ticket.objects.get(pk=pk)
    except Ticket.DoesNotExist:
        return Response({"error": "Ticket nao encontrado"}, status=404)

    from ..services.ai_service import ai_service

    result = ai_service.auto_triage(ticket.titulo, ticket.descricao)
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_suggest_response(request, pk):
    """Sugerir resposta baseada em KB + historico"""
    try:
        ticket = Ticket.objects.select_related("cliente").get(pk=pk)
    except Ticket.DoesNotExist:
        return Response({"error": "Ticket nao encontrado"}, status=404)

    from ..services.ai_service import ai_service

    result = ai_service.suggest_response(ticket)
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_summarize_ticket(request, pk):
    """Resumir conversa do ticket"""
    try:
        ticket = Ticket.objects.get(pk=pk)
    except Ticket.DoesNotExist:
        return Response({"error": "Ticket nao encontrado"}, status=404)

    from ..services.ai_service import ai_service

    result = ai_service.summarize_conversation(ticket)
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_sentiment_analysis(request):
    """Analisar sentimento de texto"""
    text = request.data.get("text", "")
    if not text:
        return Response({"error": "text obrigatorio"}, status=400)

    from ..services.ai_service import ai_service

    result = ai_service.analyze_sentiment(text)
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_find_duplicates(request):
    """Encontrar tickets duplicados/similares"""
    titulo = request.data.get("titulo", "")
    descricao = request.data.get("descricao", "")
    if not titulo and not descricao:
        return Response({"error": "titulo ou descricao obrigatorio"}, status=400)

    from ..services.ai_service import ai_service

    result = ai_service.find_duplicates(titulo, descricao)
    return Response({"duplicates": result})


# ===========================================================================
# Analytics - Agent Performance & Period Comparison
# ===========================================================================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_agent_performance(request):
    """Performance detalhada por agente"""
    if not _is_admin_or_supervisor(request.user):
        return Response({"error": "Apenas admin/supervisor podem ver performance de agentes"}, status=403)

    period = _safe_period_days(request)
    since = timezone.now() - timedelta(days=period)

    from django.contrib.auth.models import User

    agents = User.objects.filter(is_staff=True, is_active=True)

    data = []
    for agent in agents:
        tickets = Ticket.objects.filter(agente=agent, criado_em__gte=since)
        resolved = tickets.filter(status__in=["resolvido", "fechado"])
        avg_time = None
        if resolved.filter(resolvido_em__isnull=False).exists():
            avg_delta = resolved.filter(resolvido_em__isnull=False).aggregate(
                avg=Avg(F("resolvido_em") - F("criado_em"))
            )["avg"]
            if avg_delta:
                avg_time = round(avg_delta.total_seconds() / 3600, 1)

        data.append(
            {
                "agent_id": agent.id,
                "agent_name": agent.get_full_name() or agent.username,
                "total_tickets": tickets.count(),
                "resolved": resolved.count(),
                "open": tickets.filter(status="aberto").count(),
                "avg_resolution_hours": avg_time,
            }
        )

    data.sort(key=lambda x: x["resolved"], reverse=True)
    return Response({"period_days": period, "agents": data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_period_comparison(request):
    """Comparacao entre dois periodos"""
    days = _safe_period_days(request)
    now = timezone.now()
    current_start = now - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)

    def _period_stats(since, until):
        tickets = Ticket.objects.filter(criado_em__gte=since, criado_em__lt=until)
        total = tickets.count()
        resolved = tickets.filter(status__in=["resolvido", "fechado"]).count()
        return {"total": total, "resolved": resolved, "open": total - resolved}

    current = _period_stats(current_start, now)
    previous = _period_stats(previous_start, current_start)

    def _delta(cur, prev):
        if prev == 0:
            return 100.0 if cur > 0 else 0.0
        return round((cur - prev) / prev * 100, 1)

    return Response(
        {
            "period_days": days,
            "current": current,
            "previous": previous,
            "delta": {
                "total": _delta(current["total"], previous["total"]),
                "resolved": _delta(current["resolved"], previous["resolved"]),
            },
        }
    )


# ===========================================================================
# Customer Health Score
# ===========================================================================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def client_health_score(request, pk):
    """Obter ou recalcular health score de um cliente"""
    try:
        cliente = Cliente.objects.get(pk=pk)
    except Cliente.DoesNotExist:
        return Response({"error": "Cliente nao encontrado"}, status=404)

    hs, created = CustomerHealthScore.objects.get_or_create(cliente=cliente)
    if created or request.query_params.get("recalculate"):
        hs.calculate()

    return Response(
        {
            "cliente_id": cliente.id,
            "cliente_nome": cliente.nome,
            "score": round(hs.score, 1),
            "risk_level": hs.risk_level,
            "factors": hs.factors,
            "last_calculated": hs.last_calculated.isoformat() if hs.last_calculated else None,
        }
    )


# ===========================================================================
# Gamification
# ===========================================================================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def gamification_leaderboard(request):
    """Top agentes com pontuação"""
    from ..services.gamification_service import gamification_service

    limit = int(request.query_params.get("limit", 10))
    data = gamification_service.get_leaderboard(limit)
    return Response({"leaderboard": data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def gamification_badges(request):
    """Badges disponíveis e conquistadas pelo usuário"""
    all_badges = GamificationBadge.objects.all().values("id", "nome", "descricao", "icone", "cor", "pontos")
    user_badges = AgentBadge.objects.filter(usuario=request.user).values_list("badge_id", flat=True)
    return Response(
        {
            "badges": list(all_badges),
            "earned": list(user_badges),
        }
    )


# ===========================================================================
# Shared Dashboards
# ===========================================================================


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def shared_dashboard_list(request):
    """GET: listar dashboards compartilhados; POST: criar"""
    if request.method == "GET":
        dashboards = SharedDashboard.objects.filter(criado_por=request.user, is_active=True).values(
            "id", "nome", "token", "view_count", "expires_at", "criado_em"
        )
        return Response(list(dashboards))

    nome = request.data.get("nome", "Dashboard")
    config = request.data.get("config", {})
    expires = request.data.get("expires_hours")

    dash = SharedDashboard.objects.create(
        nome=nome,
        dashboard_config=config,
        criado_por=request.user,
        expires_at=timezone.now() + timedelta(hours=int(expires)) if expires else None,
    )
    return Response(
        {
            "id": dash.id,
            "token": dash.token,
            "url": f"/api/v1/dashboards/shared/{dash.token}/",
        },
        status=201,
    )


@api_view(["GET"])
@permission_classes([])
def shared_dashboard_view(request, token):
    """View pública de dashboard compartilhado (sem auth)"""
    try:
        dash = SharedDashboard.objects.get(token=token)
    except SharedDashboard.DoesNotExist:
        return Response({"error": "Dashboard nao encontrado"}, status=404)

    if not dash.is_valid():
        return Response({"error": "Dashboard expirado ou inativo"}, status=410)

    dash.view_count += 1
    dash.save(update_fields=["view_count"])

    # Gerar dados em tempo real
    now = timezone.now()
    period = dash.dashboard_config.get("period_days", 30)
    since = now - timedelta(days=period)
    tickets = Ticket.objects.filter(criado_em__gte=since)

    return Response(
        {
            "nome": dash.nome,
            "data": {
                "total_tickets": tickets.count(),
                "by_status": dict(tickets.values_list("status").annotate(c=Count("id")).values_list("status", "c")),
                "by_priority": dict(
                    tickets.values_list("prioridade").annotate(c=Count("id")).values_list("prioridade", "c")
                ),
            },
            "config": dash.dashboard_config,
            "views": dash.view_count,
        }
    )
