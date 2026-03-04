# =============================================================================
# Views para Dashboard de Implantação / Pronta Resposta de Vigilante
# =============================================================================
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.shortcuts import render
from django.utils import timezone

from ..models.vigilante import RegistroVigilante
from ..utils.rbac import role_required


@login_required
@role_required("admin", "gerente", "supervisor")
def vigilante_dashboard(request):
    """Dashboard de Implantação e Pronta Resposta de Vigilante."""

    hoje = timezone.now().date()
    inicio_mes = hoje.replace(day=1)
    inicio_ano = hoje.replace(month=1, day=1)
    mes_anterior_fim = inicio_mes - timedelta(days=1)
    mes_anterior_inicio = mes_anterior_fim.replace(day=1)

    # Filtro de período (query params)
    filtro_tipo = request.GET.get("tipo", "todos")  # todos, implantacao, pronta-resposta
    filtro_empresa = request.GET.get("empresa", "")
    filtro_uf = request.GET.get("uf", "")

    base_qs = RegistroVigilante.objects.all()
    if filtro_tipo != "todos":
        base_qs = base_qs.filter(tipo=filtro_tipo)
    if filtro_empresa:
        base_qs = base_qs.filter(empresa=filtro_empresa)
    if filtro_uf:
        base_qs = base_qs.filter(uf=filtro_uf)

    # =====================
    # KPIs
    # =====================
    total_registros = base_qs.count()
    total_implantacoes = base_qs.filter(tipo="implantacao").count()
    total_pronta_resposta = base_qs.filter(tipo="pronta-resposta").count()
    valor_total = base_qs.aggregate(total=Sum("valor"))["total"] or Decimal("0")
    valor_mes = base_qs.filter(criado_em__date__gte=inicio_mes).aggregate(total=Sum("valor"))["total"] or Decimal("0")
    valor_mes_anterior = (
        base_qs.filter(criado_em__date__gte=mes_anterior_inicio, criado_em__date__lte=mes_anterior_fim).aggregate(
            total=Sum("valor")
        )["total"]
        or Decimal("0")
    )

    # Variação mensal
    if valor_mes_anterior > 0:
        variacao_mensal = float((valor_mes - valor_mes_anterior) / valor_mes_anterior * 100)
    else:
        variacao_mensal = 100 if valor_mes > 0 else 0

    registros_mes = base_qs.filter(criado_em__date__gte=inicio_mes).count()
    duracao_media = base_qs.aggregate(media=Avg("duracao_minutos"))["media"] or 0
    duracao_media_h = int(duracao_media // 60)
    duracao_media_m = int(duracao_media % 60)

    # =====================
    # GRÁFICOS
    # =====================

    # 1. Evolução mensal (últimos 12 meses)
    doze_meses_atras = hoje - timedelta(days=365)
    evolucao_mensal = (
        base_qs.filter(criado_em__date__gte=doze_meses_atras)
        .annotate(mes=TruncMonth("criado_em"))
        .values("mes")
        .annotate(
            total_valor=Sum("valor"),
            total_registros=Count("id"),
            implantacoes=Count("id", filter=Count("id", filter=None) if False else None)
            if False
            else Count("id"),
        )
        .order_by("mes")
    )
    # Recalcular com split por tipo
    evolucao_impl = (
        base_qs.filter(criado_em__date__gte=doze_meses_atras, tipo="implantacao")
        .annotate(mes=TruncMonth("criado_em"))
        .values("mes")
        .annotate(total_valor=Sum("valor"), qtd=Count("id"))
        .order_by("mes")
    )
    evolucao_pr = (
        base_qs.filter(criado_em__date__gte=doze_meses_atras, tipo="pronta-resposta")
        .annotate(mes=TruncMonth("criado_em"))
        .values("mes")
        .annotate(total_valor=Sum("valor"), qtd=Count("id"))
        .order_by("mes")
    )

    # Montar série temporal
    meses_labels = []
    impl_valores = []
    pr_valores = []
    impl_qtd = []
    pr_qtd = []

    impl_map = {item["mes"].strftime("%Y-%m"): item for item in evolucao_impl}
    pr_map = {item["mes"].strftime("%Y-%m"): item for item in evolucao_pr}

    for i in range(12):
        mes_dt = (hoje.replace(day=1) - timedelta(days=30 * (11 - i))).replace(day=1)
        chave = mes_dt.strftime("%Y-%m")
        meses_labels.append(mes_dt.strftime("%b/%y"))
        impl_data = impl_map.get(chave, {})
        pr_data = pr_map.get(chave, {})
        impl_valores.append(float(impl_data.get("total_valor", 0) or 0))
        pr_valores.append(float(pr_data.get("total_valor", 0) or 0))
        impl_qtd.append(impl_data.get("qtd", 0))
        pr_qtd.append(pr_data.get("qtd", 0))

    # 2. Gastos por empresa (top 10)
    gastos_empresa = (
        base_qs.values("empresa")
        .annotate(total=Sum("valor"), qtd=Count("id"))
        .order_by("-total")[:10]
    )
    empresas_labels = [e["empresa"] for e in gastos_empresa]
    empresas_valores = [float(e["total"]) for e in gastos_empresa]

    # 3. Distribuição por UF
    gastos_uf = (
        base_qs.values("uf")
        .annotate(total=Sum("valor"), qtd=Count("id"))
        .order_by("-total")
    )
    ufs_labels = [u["uf"] for u in gastos_uf]
    ufs_valores = [float(u["total"]) for u in gastos_uf]

    # 4. Tendência diária (últimos 30 dias)
    trinta_dias = hoje - timedelta(days=29)
    tendencia_qs = (
        base_qs.filter(criado_em__date__gte=trinta_dias)
        .annotate(dia=TruncDate("criado_em"))
        .values("dia")
        .annotate(total=Sum("valor"), qtd=Count("id"))
        .order_by("dia")
    )
    tendencia_map = {item["dia"]: item for item in tendencia_qs}
    tendencia_labels = []
    tendencia_valores = []
    tendencia_qtd = []
    for i in range(30):
        dia = trinta_dias + timedelta(days=i)
        tendencia_labels.append(dia.strftime("%d/%m"))
        data = tendencia_map.get(dia, {})
        tendencia_valores.append(float(data.get("total", 0) or 0))
        tendencia_qtd.append(data.get("qtd", 0))

    # 5. Split tipo (pie chart)
    valor_impl_total = base_qs.filter(tipo="implantacao").aggregate(t=Sum("valor"))["t"] or Decimal("0")
    valor_pr_total = base_qs.filter(tipo="pronta-resposta").aggregate(t=Sum("valor"))["t"] or Decimal("0")

    # =====================
    # TABELA DE REGISTROS RECENTES
    # =====================
    registros_recentes = base_qs.select_related("ticket", "criado_por")[:25]

    # Listas para filtros
    empresas_disponiveis = (
        RegistroVigilante.objects.values_list("empresa", flat=True).distinct().order_by("empresa")
    )
    ufs_disponiveis = RegistroVigilante.objects.values_list("uf", flat=True).distinct().order_by("uf")

    context = {
        "active_page": "vigilante_dashboard",
        # KPIs
        "total_registros": total_registros,
        "total_implantacoes": total_implantacoes,
        "total_pronta_resposta": total_pronta_resposta,
        "valor_total": valor_total,
        "valor_mes": valor_mes,
        "valor_mes_anterior": valor_mes_anterior,
        "variacao_mensal": variacao_mensal,
        "registros_mes": registros_mes,
        "duracao_media_h": duracao_media_h,
        "duracao_media_m": duracao_media_m,
        # Gráficos (JSON para Chart.js)
        "meses_labels": json.dumps(meses_labels),
        "impl_valores": json.dumps(impl_valores),
        "pr_valores": json.dumps(pr_valores),
        "impl_qtd": json.dumps(impl_qtd),
        "pr_qtd": json.dumps(pr_qtd),
        "empresas_labels": json.dumps(empresas_labels),
        "empresas_valores": json.dumps(empresas_valores),
        "ufs_labels": json.dumps(ufs_labels),
        "ufs_valores": json.dumps(ufs_valores),
        "tendencia_labels": json.dumps(tendencia_labels),
        "tendencia_valores": json.dumps(tendencia_valores),
        "tendencia_qtd": json.dumps(tendencia_qtd),
        "valor_impl_total": float(valor_impl_total),
        "valor_pr_total": float(valor_pr_total),
        # Tabela
        "registros_recentes": registros_recentes,
        # Filtros
        "filtro_tipo": filtro_tipo,
        "filtro_empresa": filtro_empresa,
        "filtro_uf": filtro_uf,
        "empresas_disponiveis": empresas_disponiveis,
        "ufs_disponiveis": ufs_disponiveis,
    }

    return render(request, "dashboard/vigilante/dashboard.html", context)
