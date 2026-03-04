"""
Views para Gestão de Equipamentos / Ativos (Asset Management).
Controle de equipamentos instalados, histórico de trocas e alertas.
"""

import json
import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, ListView

from ..models import Cliente, PontoDeVenda, Ticket
from ..models.equipamento import AlertaEquipamento, ConfiguracaoAlertaEquipamento, Equipamento, HistoricoEquipamento
from ..utils.rbac import role_required

logger = logging.getLogger("dashboard")


# ========== DASHBOARD DE EQUIPAMENTOS ==========


@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def equipamento_dashboard(request):
    """Dashboard principal do módulo de equipamentos."""
    agora = timezone.now()
    limite_30d = agora - timedelta(days=30)

    # Métricas principais
    total_equipamentos = Equipamento.objects.count()
    equipamentos_ativos = Equipamento.objects.filter(status="ativo").count()
    equipamentos_manutencao = Equipamento.objects.filter(status="em_manutencao").count()
    equipamentos_estoque = Equipamento.objects.filter(status="em_estoque").count()

    # Alertas pendentes
    alertas_pendentes = AlertaEquipamento.objects.filter(resolvido=False).count()

    # Trocas no mês
    trocas_mes = HistoricoEquipamento.objects.filter(tipo_movimentacao="troca", realizado_em__gte=limite_30d).count()

    # Equipamentos problemáticos (3+ chamados em 30 dias)
    config = ConfiguracaoAlertaEquipamento.get_config()
    equipamentos_problematicos = (
        Equipamento.objects.filter(status="ativo", tickets__criado_em__gte=limite_30d)
        .annotate(chamados_recentes=Count("tickets"))
        .filter(chamados_recentes__gte=config.chamados_limiar)
        .order_by("-chamados_recentes")[:10]
    )

    # Top 10 tipos de equipamento mais problemáticos
    tipos_problematicos = (
        Equipamento.objects.filter(status="ativo", tickets__criado_em__gte=limite_30d)
        .values("tipo")
        .annotate(total_chamados=Count("tickets"))
        .order_by("-total_chamados")[:10]
    )

    # Movimentações recentes
    movimentacoes_recentes = HistoricoEquipamento.objects.select_related(
        "equipamento", "pdv_novo", "realizado_por", "ticket"
    )[:10]

    # Equipamentos por tipo (para gráfico)
    equipamentos_por_tipo = Equipamento.objects.values("tipo").annotate(total=Count("id")).order_by("-total")[:8]

    # Equipamentos por status (para gráfico)
    equipamentos_por_status = {
        "ativos": equipamentos_ativos,
        "manutencao": equipamentos_manutencao,
        "estoque": equipamentos_estoque,
        "desativados": Equipamento.objects.filter(status="desativado").count(),
    }

    # Trocas por mês (últimos 6 meses)
    trocas_por_mes = []
    for i in range(6):
        mes_inicio = (agora - timedelta(days=30 * i)).replace(day=1)
        if i == 0:
            mes_fim = agora
        else:
            mes_fim = (agora - timedelta(days=30 * (i - 1))).replace(day=1)
        count = HistoricoEquipamento.objects.filter(
            tipo_movimentacao="troca", realizado_em__gte=mes_inicio, realizado_em__lt=mes_fim
        ).count()
        trocas_por_mes.append({"mes": mes_inicio.strftime("%b/%y"), "total": count})
    trocas_por_mes.reverse()

    context = {
        "total_equipamentos": total_equipamentos,
        "equipamentos_ativos": equipamentos_ativos,
        "equipamentos_manutencao": equipamentos_manutencao,
        "equipamentos_estoque": equipamentos_estoque,
        "alertas_pendentes": alertas_pendentes,
        "trocas_mes": trocas_mes,
        "equipamentos_problematicos": equipamentos_problematicos,
        "tipos_problematicos": tipos_problematicos,
        "movimentacoes_recentes": movimentacoes_recentes,
        "equipamentos_por_tipo": json.dumps(list(equipamentos_por_tipo)),
        "equipamentos_por_status": json.dumps(equipamentos_por_status),
        "trocas_por_mes": json.dumps(trocas_por_mes),
        "config": config,
    }
    return render(request, "equipamentos/dashboard.html", context)


# ========== CRUD DE EQUIPAMENTOS ==========


@method_decorator(login_required, name="dispatch")
class EquipamentoListView(ListView):
    """Listagem de equipamentos com filtros."""

    model = Equipamento
    template_name = "equipamentos/equipamento_list.html"
    context_object_name = "equipamentos"
    paginate_by = 20

    def get_queryset(self):
        qs = Equipamento.objects.select_related("ponto_de_venda", "ponto_de_venda__cliente", "criado_por")

        # Filtros
        search = self.request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(
                Q(numero_serie__icontains=search)
                | Q(modelo__icontains=search)
                | Q(marca__icontains=search)
                | Q(tipo__icontains=search)
                | Q(patrimonio__icontains=search)
                | Q(ponto_de_venda__nome_fantasia__icontains=search)
                | Q(ponto_de_venda__cliente__nome__icontains=search)
            )

        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)

        tipo = self.request.GET.get("tipo")
        if tipo:
            qs = qs.filter(tipo=tipo)

        pdv_id = self.request.GET.get("pdv")
        if pdv_id:
            qs = qs.filter(ponto_de_venda_id=pdv_id)

        cliente_id = self.request.GET.get("cliente")
        if cliente_id:
            qs = qs.filter(ponto_de_venda__cliente_id=cliente_id)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = Equipamento.StatusEquipamento.choices
        ctx["tipos"] = Equipamento.objects.values_list("tipo", flat=True).distinct().order_by("tipo")
        ctx["clientes"] = Cliente.objects.all().order_by("nome")
        ctx["pontos_de_venda"] = PontoDeVenda.objects.select_related("cliente").all().order_by("nome_fantasia")
        ctx["filtros"] = {
            "q": self.request.GET.get("q", ""),
            "status": self.request.GET.get("status", ""),
            "tipo": self.request.GET.get("tipo", ""),
            "pdv": self.request.GET.get("pdv", ""),
            "cliente": self.request.GET.get("cliente", ""),
        }
        ctx["alertas_pendentes"] = AlertaEquipamento.objects.filter(resolvido=False).count()
        return ctx


@method_decorator(login_required, name="dispatch")
class EquipamentoDetailView(DetailView):
    """Detalhe de um equipamento com histórico e chamados."""

    model = Equipamento
    template_name = "equipamentos/equipamento_detail.html"
    context_object_name = "equipamento"

    def get_queryset(self):
        return Equipamento.objects.select_related("ponto_de_venda", "ponto_de_venda__cliente", "criado_por")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        equip = self.object
        agora = timezone.now()
        limite_30d = agora - timedelta(days=30)

        # Histórico de movimentações
        ctx["historico"] = equip.historico.select_related(
            "pdv_anterior", "pdv_novo", "equipamento_substituido", "ticket", "realizado_por"
        )[:20]

        # Chamados vinculados
        ctx["tickets"] = equip.tickets.select_related("cliente", "agente", "categoria").order_by("-criado_em")[:15]

        # Chamados nos últimos 30 dias
        ctx["chamados_30d"] = equip.tickets.filter(criado_em__gte=limite_30d).count()

        # Alertas deste equipamento
        ctx["alertas"] = equip.alertas.filter(resolvido=False)

        # Estatísticas
        ctx["total_chamados"] = equip.tickets.count()
        ctx["total_trocas"] = equip.historico.filter(tipo_movimentacao="troca").count()
        ctx["total_manutencoes"] = equip.historico.filter(tipo_movimentacao="manutencao").count()

        return ctx


@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def equipamento_create(request):
    """Criar novo equipamento."""
    if request.method == "POST":
        try:
            with transaction.atomic():
                equip = Equipamento(
                    numero_serie=request.POST["numero_serie"].strip(),
                    modelo=request.POST["modelo"].strip(),
                    marca=request.POST.get("marca", "").strip(),
                    tipo=request.POST["tipo"].strip(),
                    descricao=request.POST.get("descricao", "").strip(),
                    patrimonio=request.POST.get("patrimonio", "").strip(),
                    local_instalacao=request.POST.get("local_instalacao", "").strip(),
                    status=request.POST.get("status", "em_estoque"),
                    observacoes=request.POST.get("observacoes", "").strip(),
                    criado_por=request.user,
                )

                pdv_id = request.POST.get("ponto_de_venda")
                if pdv_id:
                    equip.ponto_de_venda_id = int(pdv_id)

                data_instalacao = request.POST.get("data_instalacao")
                if data_instalacao:
                    equip.data_instalacao = data_instalacao

                data_garantia = request.POST.get("data_garantia")
                if data_garantia:
                    equip.data_garantia = data_garantia

                equip.save()

                # Se está instalado em PdV, registrar no histórico
                if equip.ponto_de_venda and equip.status == "ativo":
                    HistoricoEquipamento.objects.create(
                        equipamento=equip,
                        tipo_movimentacao="instalacao",
                        pdv_novo=equip.ponto_de_venda,
                        motivo="Cadastro inicial — equipamento já instalado",
                        realizado_por=request.user,
                    )

                messages.success(request, f"Equipamento {equip.numero_serie} cadastrado com sucesso!")
                return redirect("equipamentos:equipamento_detail", pk=equip.pk)

        except Exception as e:
            logger.error(f"Erro ao criar equipamento: {e}")
            messages.error(request, f"Erro ao cadastrar equipamento: {e}")

    clientes = Cliente.objects.all().order_by("nome")
    pontos_de_venda = PontoDeVenda.objects.select_related("cliente").all().order_by("nome_fantasia")
    status_choices = Equipamento.StatusEquipamento.choices
    # Sugerir tipos já existentes
    tipos_existentes = list(Equipamento.objects.values_list("tipo", flat=True).distinct().order_by("tipo"))

    return render(
        request,
        "equipamentos/equipamento_form.html",
        {
            "clientes": clientes,
            "pontos_de_venda": pontos_de_venda,
            "status_choices": status_choices,
            "tipos_existentes": tipos_existentes,
            "modo": "criar",
        },
    )


@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def equipamento_update(request, pk):
    """Editar equipamento existente."""
    equip = get_object_or_404(Equipamento, pk=pk)

    if request.method == "POST":
        try:
            with transaction.atomic():
                equip.numero_serie = request.POST["numero_serie"].strip()
                equip.modelo = request.POST["modelo"].strip()
                equip.marca = request.POST.get("marca", "").strip()
                equip.tipo = request.POST["tipo"].strip()
                equip.descricao = request.POST.get("descricao", "").strip()
                equip.patrimonio = request.POST.get("patrimonio", "").strip()
                equip.local_instalacao = request.POST.get("local_instalacao", "").strip()
                equip.status = request.POST.get("status", equip.status)
                equip.observacoes = request.POST.get("observacoes", "").strip()

                pdv_id = request.POST.get("ponto_de_venda")
                equip.ponto_de_venda_id = int(pdv_id) if pdv_id else None

                data_instalacao = request.POST.get("data_instalacao")
                equip.data_instalacao = data_instalacao if data_instalacao else None

                data_garantia = request.POST.get("data_garantia")
                equip.data_garantia = data_garantia if data_garantia else None

                equip.save()
                messages.success(request, f"Equipamento {equip.numero_serie} atualizado!")
                return redirect("equipamentos:equipamento_detail", pk=equip.pk)

        except Exception as e:
            logger.error(f"Erro ao atualizar equipamento {pk}: {e}")
            messages.error(request, f"Erro ao atualizar: {e}")

    clientes = Cliente.objects.all().order_by("nome")
    pontos_de_venda = PontoDeVenda.objects.select_related("cliente").all().order_by("nome_fantasia")
    status_choices = Equipamento.StatusEquipamento.choices
    tipos_existentes = list(Equipamento.objects.values_list("tipo", flat=True).distinct().order_by("tipo"))

    return render(
        request,
        "equipamentos/equipamento_form.html",
        {
            "equipamento": equip,
            "clientes": clientes,
            "pontos_de_venda": pontos_de_venda,
            "status_choices": status_choices,
            "tipos_existentes": tipos_existentes,
            "modo": "editar",
        },
    )


# ========== MOVIMENTAÇÕES / HISTÓRICO ==========


@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def registrar_movimentacao(request, pk):
    """Registrar instalação, troca, retirada ou manutenção."""
    equip = get_object_or_404(Equipamento, pk=pk)

    if request.method == "POST":
        try:
            with transaction.atomic():
                tipo_mov = request.POST["tipo_movimentacao"]
                pdv_anterior = equip.ponto_de_venda

                mov = HistoricoEquipamento(
                    equipamento=equip,
                    tipo_movimentacao=tipo_mov,
                    pdv_anterior=pdv_anterior,
                    motivo=request.POST.get("motivo", "").strip(),
                    observacoes=request.POST.get("observacoes", "").strip(),
                    realizado_por=request.user,
                )

                # Data personalizada ou agora
                data_str = request.POST.get("data_realizacao")
                if data_str:
                    mov.realizado_em = timezone.datetime.fromisoformat(data_str)

                # Ticket vinculado
                ticket_id = request.POST.get("ticket")
                if ticket_id:
                    mov.ticket_id = int(ticket_id)

                # Novo PdV (para instalação/troca)
                novo_pdv_id = request.POST.get("novo_pdv")
                if novo_pdv_id:
                    mov.pdv_novo_id = int(novo_pdv_id)

                # Equipamento substituído (para troca)
                substituido_id = request.POST.get("equipamento_substituido")
                if substituido_id:
                    mov.equipamento_substituido_id = int(substituido_id)
                    # Desativar equipamento antigo
                    equip_antigo = Equipamento.objects.get(pk=substituido_id)
                    equip_antigo.status = "desativado"
                    equip_antigo.data_desativacao = timezone.now().date()
                    equip_antigo.save(update_fields=["status", "data_desativacao"])

                mov.save()

                # Atualizar o equipamento com base no tipo de movimentação
                if tipo_mov == "instalacao":
                    equip.status = "ativo"
                    if novo_pdv_id:
                        equip.ponto_de_venda_id = int(novo_pdv_id)
                    equip.data_instalacao = timezone.now().date()
                elif tipo_mov == "troca":
                    equip.status = "ativo"
                    if novo_pdv_id:
                        equip.ponto_de_venda_id = int(novo_pdv_id)
                elif tipo_mov == "retirada" or tipo_mov == "devolucao":
                    equip.status = "em_estoque"
                    equip.ponto_de_venda = None
                elif tipo_mov == "manutencao":
                    equip.status = "em_manutencao"

                equip.save()
                equip.atualizar_contadores()

                messages.success(request, f"{mov.get_tipo_movimentacao_display()} registrada com sucesso!")
                return redirect("equipamentos:equipamento_detail", pk=equip.pk)

        except Exception as e:
            logger.error(f"Erro ao registrar movimentação: {e}")
            messages.error(request, f"Erro: {e}")

    # Buscar tickets do PdV para vincular
    tickets_pdv = []
    if equip.ponto_de_venda:
        tickets_pdv = Ticket.objects.filter(ponto_de_venda=equip.ponto_de_venda).order_by("-criado_em")[:20]

    # Equipamentos do mesmo PdV (para troca)
    equipamentos_pdv = []
    if equip.ponto_de_venda:
        equipamentos_pdv = Equipamento.objects.filter(ponto_de_venda=equip.ponto_de_venda, status="ativo").exclude(
            pk=equip.pk
        )

    pontos_de_venda = PontoDeVenda.objects.select_related("cliente").all().order_by("nome_fantasia")
    tipo_choices = HistoricoEquipamento.TipoMovimentacao.choices

    return render(
        request,
        "equipamentos/registrar_movimentacao.html",
        {
            "equipamento": equip,
            "tipo_choices": tipo_choices,
            "pontos_de_venda": pontos_de_venda,
            "tickets_pdv": tickets_pdv,
            "equipamentos_pdv": equipamentos_pdv,
        },
    )


# ========== ALERTAS ==========


@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def alerta_list(request):
    """Lista de alertas de equipamentos."""
    filtro = request.GET.get("filtro", "pendentes")

    if filtro == "todos":
        alertas = AlertaEquipamento.objects.all()
    elif filtro == "resolvidos":
        alertas = AlertaEquipamento.objects.filter(resolvido=True)
    else:
        alertas = AlertaEquipamento.objects.filter(resolvido=False)

    alertas = alertas.select_related(
        "equipamento", "equipamento__ponto_de_venda", "equipamento__ponto_de_venda__cliente", "resolvido_por"
    ).order_by("-criado_em")

    # Paginação
    from django.core.paginator import Paginator

    paginator = Paginator(alertas, 20)
    page = request.GET.get("page")
    alertas_page = paginator.get_page(page)

    return render(
        request,
        "equipamentos/alerta_list.html",
        {
            "alertas": alertas_page,
            "filtro": filtro,
            "total_pendentes": AlertaEquipamento.objects.filter(resolvido=False).count(),
        },
    )


@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def alerta_resolver(request, pk):
    """Resolver um alerta de equipamento."""
    alerta = get_object_or_404(AlertaEquipamento, pk=pk)

    if request.method == "POST":
        acao = request.POST.get("acao_tomada", "").strip()
        alerta.resolver(usuario=request.user, acao=acao)
        messages.success(request, "Alerta resolvido!")
        return redirect("equipamentos:alerta_list")

    return render(
        request,
        "equipamentos/alerta_resolver.html",
        {
            "alerta": alerta,
        },
    )


# ========== RELATÓRIO POR PONTO DE VENDA ==========


@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def equipamentos_por_cliente(request, cliente_id):
    """Equipamentos instalados nos PdVs de um cliente específico."""
    cliente = get_object_or_404(Cliente, pk=cliente_id)
    pdvs = PontoDeVenda.objects.filter(cliente=cliente)
    equipamentos = (
        Equipamento.objects.filter(ponto_de_venda__cliente=cliente)
        .select_related("ponto_de_venda")
        .order_by("ponto_de_venda__nome_fantasia", "tipo", "modelo")
    )

    limite_30d = timezone.now() - timedelta(days=30)

    total_equipamentos = equipamentos.count()
    total_chamados_equip = 0
    total_trocas = 0

    for equip in equipamentos:
        total_chamados_equip += equip.tickets.filter(criado_em__gte=limite_30d).count()
        total_trocas += equip.historico.filter(tipo_movimentacao="troca").count()

    return render(
        request,
        "equipamentos/equipamentos_cliente.html",
        {
            "cliente": cliente,
            "pontos_de_venda": pdvs,
            "equipamentos": equipamentos,
            "total_equipamentos": total_equipamentos,
            "total_chamados_equip": total_chamados_equip,
            "total_trocas": total_trocas,
        },
    )


# ========== APIs AJAX ==========


@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def api_equipamentos_cliente(request, cliente_id):
    """API ajax: retorna equipamentos dos PdVs de um cliente."""
    equipamentos = Equipamento.objects.filter(ponto_de_venda__cliente_id=cliente_id, status="ativo").values(
        "id", "numero_serie", "tipo", "modelo", "marca"
    )

    return JsonResponse({"equipamentos": list(equipamentos)})


@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def api_dashboard_stats(request):
    """API ajax: métricas resumidas para badges e cards dinâmicos."""
    alertas = AlertaEquipamento.objects.filter(resolvido=False).count()
    problematicos = Equipamento.objects.filter(status="ativo", total_chamados__gte=3).count()

    return JsonResponse(
        {
            "alertas_pendentes": alertas,
            "equipamentos_problematicos": problematicos,
        }
    )
