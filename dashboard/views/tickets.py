"""
Views de tickets: CRUD, Kanban, interações e dashboard do agente.
"""

import json
import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from ..forms import TicketCreateForm
from ..models import (
    CategoriaEstoque,
    CategoriaTicket,
    Cliente,
    InteracaoTicket,
    PerfilAgente,
    PontoDeVenda,
    PrioridadeTicket,
    StatusTicket,
    Ticket,
    TicketAnexo,
)
from .helpers import get_role_filtered_tickets, user_can_access_ticket
from ..utils.rbac import role_required

logger = logging.getLogger("dashboard")
User = get_user_model()


# ========== KANBAN BOARD ==========


@method_decorator(login_required, name="dispatch")
@method_decorator(role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente'), name='dispatch')
class KanbanBoardView(TemplateView):
    """Visualização Kanban do pipeline de tickets"""

    template_name = "dashboard/tickets/kanban.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_qs = Ticket.objects.select_related("cliente", "agente", "categoria").order_by("-prioridade", "-criado_em")

        # RBAC: filtrar tickets por papel do usuário
        base_qs = get_role_filtered_tickets(self.request.user, base_qs)

        # Filtros opcionais
        agente = self.request.GET.get("agente")
        if agente:
            base_qs = base_qs.filter(agente_id=agente)
        categoria = self.request.GET.get("categoria")
        if categoria:
            base_qs = base_qs.filter(categoria_id=categoria)

        columns = [
            ("aberto", "Aberto", "info"),
            ("em_andamento", "Em Andamento", "warning"),
            ("pendente", "Pendente", "secondary"),
            ("resolvido", "Resolvido", "success"),
            ("fechado", "Fechado", "dark"),
        ]
        kanban_columns = []
        for status_key, label, color in columns:
            tickets = base_qs.filter(status=status_key)[:50]
            kanban_columns.append(
                {
                    "status": status_key,
                    "label": label,
                    "color": color,
                    "tickets": tickets,
                    "count": tickets.count() if hasattr(tickets, "count") else len(tickets),
                }
            )

        context["columns"] = kanban_columns
        context["agentes"] = User.objects.filter(perfilagente__isnull=False, is_active=True).order_by("first_name")
        context["categorias"] = CategoriaTicket.objects.all()
        return context


# ========== SISTEMA DE TICKETS ==========


@method_decorator(login_required, name="dispatch")
@method_decorator(role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente'), name='dispatch')
class TicketListView(ListView):
    model = Ticket
    template_name = "dashboard/tickets/list.html"
    context_object_name = "tickets"
    paginate_by = 15

    def get_queryset(self):
        queryset = Ticket.objects.select_related("cliente", "categoria", "agente", "ponto_de_venda").order_by("-criado_em")

        # RBAC: filtrar tickets por papel do usuário
        queryset = get_role_filtered_tickets(self.request.user, queryset)

        # Filtros
        status_filter = self.request.GET.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        categoria_filter = self.request.GET.get("categoria")
        if categoria_filter:
            queryset = queryset.filter(categoria_id=categoria_filter)

        prioridade_filter = self.request.GET.get("prioridade")
        if prioridade_filter:
            queryset = queryset.filter(prioridade=prioridade_filter)

        agente_filter = self.request.GET.get("agente")
        if agente_filter:
            if agente_filter == "none":
                queryset = queryset.filter(agente__isnull=True)
            else:
                queryset = queryset.filter(agente_id=agente_filter)

        # Filtro por data
        data_inicio = self.request.GET.get("data_inicio")
        data_fim = self.request.GET.get("data_fim")
        if data_inicio:
            queryset = queryset.filter(criado_em__date__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(criado_em__date__lte=data_fim)

        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(numero__icontains=search)
                | Q(titulo__icontains=search)
                | Q(cliente__nome__icontains=search)
                | Q(cliente__email__icontains=search)
                | Q(descricao__icontains=search)
            )

        self._filtered_queryset = queryset
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categorias"] = CategoriaTicket.objects.all()
        context["status_choices"] = StatusTicket.choices
        context["prioridade_choices"] = PrioridadeTicket.choices
        context["filters"] = self.request.GET
        context["agentes"] = User.objects.filter(perfilagente__isnull=False, is_active=True).order_by("first_name")

        # KPIs baseados no queryset completo (sem paginação)
        all_tickets = Ticket.objects.all()
        context["kpi_total"] = all_tickets.count()
        context["kpi_abertos"] = all_tickets.filter(status=StatusTicket.ABERTO).count()
        context["kpi_andamento"] = all_tickets.filter(status=StatusTicket.EM_ANDAMENTO).count()
        context["kpi_resolvidos"] = all_tickets.filter(
            status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO]
        ).count()
        context["kpi_criticos"] = all_tickets.filter(
            prioridade=PrioridadeTicket.CRITICA, status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO]
        ).count()
        context["kpi_nao_atribuidos"] = all_tickets.filter(
            agente__isnull=True, status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO]
        ).count()

        # Tempo médio de resolução
        tempo_medio_qs = (
            all_tickets.filter(
                status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO],
                resolvido_em__isnull=False,
            )
            .annotate(duracao=ExpressionWrapper(F("resolvido_em") - F("criado_em"), output_field=DurationField()))
            .aggregate(media=Avg("duracao"))
        )
        tempo = tempo_medio_qs.get("media")
        if tempo:
            total_sec = int(tempo.total_seconds())
            h = total_sec // 3600
            m = (total_sec % 3600) // 60
            context["kpi_tempo_medio"] = f"{h}h {m}min" if h < 24 else f"{h // 24}d {h % 24}h"
        else:
            context["kpi_tempo_medio"] = "--"

        # Taxa de resolução (este mês)
        mes_atual = timezone.now().date().replace(day=1)
        tickets_mes = all_tickets.filter(criado_em__date__gte=mes_atual)
        total_mes = tickets_mes.count()
        resolvidos_mes = tickets_mes.filter(status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO]).count()
        context["kpi_taxa_resolucao"] = round((resolvidos_mes / total_mes * 100), 1) if total_mes > 0 else 0

        return context


@method_decorator(login_required, name="dispatch")
class TicketDetailView(DetailView):
    model = Ticket
    template_name = "dashboard/tickets/detail.html"
    context_object_name = "ticket"

    def get_queryset(self):
        base_qs = Ticket.objects.select_related("cliente", "categoria", "agente").prefetch_related(
            "interacoes__usuario", "itens_atendimento__produto"
        )
        return get_role_filtered_tickets(self.request.user, base_qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["interacoes"] = self.object.interacoes.all().order_by("criado_em")
        context["anexos"] = self.object.anexos.all() if hasattr(self.object, "anexos") else []
        context["status_choices"] = StatusTicket.choices
        context["cliente_total_tickets"] = Ticket.objects.filter(cliente=self.object.cliente).count()

        # Dados de Sala de Monitoramento
        from ..models.vigilante import RegistroVigilante
        registros = RegistroVigilante.objects.filter(ticket=self.object).order_by("criado_em")
        context["registros_vigilante"] = registros
        context["is_sala_monitoramento"] = registros.exists()
        if registros.exists():
            completos = registros.exclude(valor__isnull=True)
            context["valor_total_vigilante"] = sum(float(r.valor) for r in completos if r.valor)
            context["has_pendentes"] = registros.filter(fim__isnull=True).exists()

        # Itens de atendimento (produtos/serviços)
        context["has_itens"] = self.object.itens_atendimento.exists()

        # Descrição limpa (sem a tabela de resumo gerada automaticamente)
        desc = self.object.descricao or ""
        if "<hr>" in desc:
            desc = desc[: desc.index("<hr>")]
        context["descricao_limpa"] = desc.strip()
        return context


@method_decorator(login_required, name="dispatch")
class TicketCreateView(CreateView):
    model = Ticket
    template_name = "dashboard/tickets/create.html"
    form_class = TicketCreateForm

    def get_success_url(self):
        return reverse("dashboard:ticket_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["clientes"] = Cliente.objects.all().order_by("nome")
        context["pontos_de_venda"] = PontoDeVenda.objects.select_related("cliente").all().order_by("nome_fantasia")
        context["categorias"] = CategoriaTicket.objects.all()
        context["categorias_produto"] = CategoriaEstoque.objects.annotate(
            total_produtos=Count("produto", filter=models.Q(produto__status="ativo"))
        ).filter(total_produtos__gt=0).order_by("nome")

        try:
            cliente = Cliente.objects.get(email=self.request.user.email)
            context["cliente_logado"] = cliente
            context["is_cliente"] = True
        except Cliente.DoesNotExist:
            context["is_cliente"] = False

        return context

    def form_valid(self, form):
        # Atribuir o usuário logado como agente responsável
        form.instance.agente = self.request.user

        try:
            cliente = Cliente.objects.get(email=self.request.user.email)
            form.instance.cliente = cliente
        except Cliente.DoesNotExist:
            pass

        response = super().form_valid(form)

        # Processar produtos e serviços (se enviados)
        produtos_dados = self.request.POST.get("produtos_dados")
        if produtos_dados:
            try:
                from decimal import Decimal

                from ..models import ItemAtendimento, Produto

                itens = json.loads(produtos_dados)

                for item in itens:
                    produto_id = item["produto"]["id"]
                    quantidade = Decimal(str(item["quantidade"]))
                    valor_unitario = Decimal(str(item["valorUnitario"]))
                    desconto_percentual = Decimal(str(item["descontoPercentual"]))
                    observacoes = item.get("observacoes", "")
                    tipo_item = item["produto"]["tipo"]

                    try:
                        produto = Produto.objects.get(id=produto_id)
                        ItemAtendimento.objects.create(
                            ticket=self.object,
                            produto=produto,
                            tipo_item=tipo_item,
                            quantidade=quantidade,
                            valor_unitario=valor_unitario,
                            desconto_percentual=desconto_percentual,
                            observacoes=observacoes,
                            adicionado_por=self.request.user,
                        )
                    except Produto.DoesNotExist:
                        logger.warning("Produto ID %s nao encontrado", produto_id)
                        continue

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.error("Erro ao processar produtos: %s", e, exc_info=True)

        # Processar cálculo de vigilante (Sala de Monitoramento)
        calculo_vig_dados = self.request.POST.get("calculo_vigilante_dados")
        if calculo_vig_dados:
            try:
                from datetime import datetime as dt

                from ..models.vigilante import RegistroVigilante

                dados = json.loads(calculo_vig_dados)
                tipo = dados.get("tipo", "implantacao")
                periodos = dados.get("periodos", [])
                valor_total = dados.get("valor_total", 0)

                # Salvar registros estruturados no modelo RegistroVigilante
                for p in periodos:
                    inicio_str = p.get("inicio", "")
                    fim_str = p.get("fim") or ""
                    is_pendente = p.get("pendente", False)
                    try:
                        inicio_dt = dt.fromisoformat(inicio_str) if inicio_str else None
                        fim_dt = dt.fromisoformat(fim_str) if fim_str else None
                    except (ValueError, TypeError):
                        inicio_dt = None
                        fim_dt = None

                    if inicio_dt:
                        RegistroVigilante.objects.create(
                            ticket=self.object,
                            tipo=p.get("tipo", tipo),
                            empresa=p.get("empresa", ""),
                            uf=p.get("uf", ""),
                            inicio=inicio_dt,
                            fim=fim_dt,
                            duracao_minutos=p.get("duracao_minutos") if not is_pendente else None,
                            valor=p.get("valor") if not is_pendente else None,
                            detalhes=p.get("detalhes", ""),
                            criado_por=self.request.user,
                        )

                # Adicionar resumo do cálculo à descrição do ticket
                resumo_html = f"\n<hr><h4>{'Implantação de Vigilante' if tipo == 'implantacao' else 'Pronta Resposta'} — Resumo do Cálculo</h4>"
                resumo_html += "<table style='width:100%;border-collapse:collapse;'>"
                resumo_html += "<tr style='background:#f5f5f5;'><th style='padding:6px;border:1px solid #ddd;'>Empresa</th><th style='padding:6px;border:1px solid #ddd;'>UF</th><th style='padding:6px;border:1px solid #ddd;'>Início</th><th style='padding:6px;border:1px solid #ddd;'>Fim</th><th style='padding:6px;border:1px solid #ddd;'>Duração</th><th style='padding:6px;border:1px solid #ddd;'>Valor</th></tr>"
                for p in periodos:
                    is_pend = p.get("pendente", False)
                    dur_min = p.get("duracao_minutos", 0) or 0
                    dur_h = int(dur_min // 60)
                    dur_m = int(dur_min % 60)
                    fim_display = p.get('fim', '') or '⏳ Pendente'
                    duracao_display = f"{dur_h}h {dur_m}min" if not is_pend else "Pendente"
                    valor_display = f"R$ {p.get('valor', 0):.2f}" if not is_pend else "Pendente"
                    row_style = "background:#fef3c7;" if is_pend else ""
                    resumo_html += f"<tr style='{row_style}'><td style='padding:6px;border:1px solid #ddd;'>{p.get('empresa','')}</td><td style='padding:6px;border:1px solid #ddd;'>{p.get('uf','')}</td><td style='padding:6px;border:1px solid #ddd;'>{p.get('inicio','')}</td><td style='padding:6px;border:1px solid #ddd;'>{fim_display}</td><td style='padding:6px;border:1px solid #ddd;'>{duracao_display}</td><td style='padding:6px;border:1px solid #ddd;'>{valor_display}</td></tr>"
                resumo_html += f"<tr style='font-weight:bold;background:#e8f5e9;'><td colspan='5' style='padding:6px;border:1px solid #ddd;text-align:right;'>TOTAL:</td><td style='padding:6px;border:1px solid #ddd;'>R$ {valor_total:.2f}</td></tr>"
                resumo_html += "</table>"

                self.object.descricao = (self.object.descricao or "") + resumo_html
                self.object.save(update_fields=["descricao"])

                logger.info(
                    "Cálculo de vigilante (%s) salvo no ticket #%s: %d períodos, total R$ %.2f",
                    tipo, self.object.numero, len(periodos), valor_total
                )
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.error("Erro ao processar cálculo de vigilante: %s", e, exc_info=True)

        # Processar anexos
        if "anexos" in self.request.FILES:
            from ..utils.security import validate_file_upload

            anexos = self.request.FILES.getlist("anexos")
            for anexo in anexos:
                is_valid, error_msg = validate_file_upload(anexo)
                if is_valid:
                    TicketAnexo.objects.create(
                        ticket=self.object,
                        arquivo=anexo,
                        nome_original=anexo.name,
                        tamanho=anexo.size,
                        tipo_mime=anexo.content_type or "application/octet-stream",
                        criado_por=self.request.user,
                    )
                else:
                    logger.warning(
                        "Upload rejeitado para ticket #%s: %s — %s", self.object.numero, anexo.name, error_msg
                    )

        messages.success(self.request, f"Ticket #{self.object.numero} criado com sucesso!")
        return response


@method_decorator(login_required, name="dispatch")
@method_decorator(role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente'), name='dispatch')
class TicketUpdateView(UpdateView):
    model = Ticket
    template_name = "dashboard/tickets/update.html"
    fields = ["cliente", "ponto_de_venda", "categoria", "tipo", "subtipo", "sintoma", "titulo", "descricao", "status", "prioridade", "agente"]

    def get_queryset(self):
        base_qs = Ticket.objects.all()
        return get_role_filtered_tickets(self.request.user, base_qs)

    def get_success_url(self):
        return reverse("dashboard:ticket_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["clientes"] = Cliente.objects.all().order_by("nome")
        context["pontos_de_venda"] = PontoDeVenda.objects.select_related("cliente").all().order_by("nome_fantasia")
        context["categorias"] = CategoriaTicket.objects.all()
        context["agentes"] = User.objects.filter(perfilagente__isnull=False)
        context["tipo_choices"] = Ticket.TIPO_CHOICES

        # Dados de Sala de Monitoramento
        from ..models.vigilante import RegistroVigilante
        registros = RegistroVigilante.objects.filter(ticket=self.object).order_by("criado_em")
        context["registros_vigilante"] = registros
        context["is_sala_monitoramento"] = registros.exists()
        context["has_pendentes"] = registros.filter(fim__isnull=True).exists()
        return context

    def form_valid(self, form):
        # Processar cálculo de vigilante (Sala de Monitoramento)
        calculo_vig_dados = self.request.POST.get("calculo_vigilante_dados")
        if calculo_vig_dados:
            try:
                from datetime import datetime as dt

                from ..models.vigilante import RegistroVigilante

                dados = json.loads(calculo_vig_dados)
                registros_update = dados.get("registros_update", [])

                for reg_data in registros_update:
                    reg_id = reg_data.get("id")
                    fim_str = reg_data.get("fim") or ""
                    if reg_id and fim_str:
                        try:
                            reg = RegistroVigilante.objects.get(id=reg_id, ticket=self.object)
                            fim_dt = dt.fromisoformat(fim_str)
                            duracao_min = reg_data.get("duracao_minutos", 0)
                            valor = reg_data.get("valor", 0)
                            detalhes = reg_data.get("detalhes", "")

                            reg.fim = fim_dt
                            reg.duracao_minutos = duracao_min
                            reg.valor = valor
                            reg.detalhes = detalhes
                            reg.save(update_fields=["fim", "duracao_minutos", "valor", "detalhes"])
                        except (RegistroVigilante.DoesNotExist, ValueError, TypeError) as e:
                            logger.warning("Erro ao atualizar registro vigilante %s: %s", reg_id, e)

                # Novos períodos (adicionados na edição)
                novos = dados.get("periodos_novos", [])
                tipo_padrao = dados.get("tipo", "implantacao")
                for p in novos:
                    inicio_str = p.get("inicio", "")
                    fim_str = p.get("fim") or ""
                    is_pendente = p.get("pendente", False)
                    try:
                        inicio_dt = dt.fromisoformat(inicio_str) if inicio_str else None
                        fim_dt = dt.fromisoformat(fim_str) if fim_str else None
                    except (ValueError, TypeError):
                        inicio_dt = None
                        fim_dt = None

                    if inicio_dt:
                        RegistroVigilante.objects.create(
                            ticket=self.object,
                            tipo=p.get("tipo", tipo_padrao),
                            empresa=p.get("empresa", ""),
                            uf=p.get("uf", ""),
                            inicio=inicio_dt,
                            fim=fim_dt,
                            duracao_minutos=p.get("duracao_minutos") if not is_pendente else None,
                            valor=p.get("valor") if not is_pendente else None,
                            detalhes=p.get("detalhes", ""),
                            criado_por=self.request.user,
                        )

                # Recalcular resumo na descrição
                all_registros = RegistroVigilante.objects.filter(ticket=self.object)
                if all_registros.exists():
                    tipo_label = "Implantação de Vigilante" if tipo_padrao == "implantacao" else "Pronta Resposta"
                    # Remove resumo anterior (tudo após <hr>)
                    desc = form.instance.descricao or ""
                    if "<hr>" in desc:
                        desc = desc[:desc.index("<hr>")]
                    resumo_html = f"\n<hr><h4>{tipo_label} — Resumo do Cálculo</h4>"
                    resumo_html += "<table style='width:100%;border-collapse:collapse;'>"
                    resumo_html += "<tr style='background:#f5f5f5;'><th style='padding:6px;border:1px solid #ddd;'>Empresa</th><th style='padding:6px;border:1px solid #ddd;'>UF</th><th style='padding:6px;border:1px solid #ddd;'>Início</th><th style='padding:6px;border:1px solid #ddd;'>Fim</th><th style='padding:6px;border:1px solid #ddd;'>Duração</th><th style='padding:6px;border:1px solid #ddd;'>Valor</th></tr>"
                    valor_total = 0
                    for r in all_registros:
                        is_pend = r.pendente
                        if not is_pend and r.valor:
                            valor_total += float(r.valor)
                        dur_min = r.duracao_minutos or 0
                        dur_h = int(dur_min // 60)
                        dur_m = int(dur_min % 60)
                        inicio_fmt = r.inicio.strftime("%d/%m/%Y %H:%M") if r.inicio else ""
                        fim_fmt = r.fim.strftime("%d/%m/%Y %H:%M") if r.fim else "⏳ Pendente"
                        duracao_display = f"{dur_h}h {dur_m}min" if not is_pend else "Pendente"
                        valor_display = f"R$ {float(r.valor):.2f}" if not is_pend and r.valor else "Pendente"
                        row_style = "background:#fef3c7;" if is_pend else ""
                        resumo_html += f"<tr style='{row_style}'><td style='padding:6px;border:1px solid #ddd;'>{r.empresa}</td><td style='padding:6px;border:1px solid #ddd;'>{r.uf}</td><td style='padding:6px;border:1px solid #ddd;'>{inicio_fmt}</td><td style='padding:6px;border:1px solid #ddd;'>{fim_fmt}</td><td style='padding:6px;border:1px solid #ddd;'>{duracao_display}</td><td style='padding:6px;border:1px solid #ddd;'>{valor_display}</td></tr>"
                    resumo_html += f"<tr style='font-weight:bold;background:#e8f5e9;'><td colspan='5' style='padding:6px;border:1px solid #ddd;text-align:right;'>TOTAL:</td><td style='padding:6px;border:1px solid #ddd;'>R$ {valor_total:.2f}</td></tr>"
                    resumo_html += "</table>"
                    form.instance.descricao = desc + resumo_html

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.error("Erro ao processar cálculo de vigilante na edição: %s", e, exc_info=True)

        messages.success(self.request, "Ticket atualizado com sucesso!")
        return super().form_valid(form)


@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def add_interaction(request, ticket_id):
    """Adiciona uma nova interação ao ticket"""
    if request.method == "POST":
        ticket = get_object_or_404(Ticket, id=ticket_id)

        if not user_can_access_ticket(request.user, ticket):
            messages.error(request, "Você não tem permissão para interagir com este ticket.")
            return redirect("dashboard:ticket_list")

        mensagem = request.POST.get("mensagem")
        eh_publico = request.POST.get("eh_publico") == "on"

        if mensagem:
            InteracaoTicket.objects.create(
                ticket=ticket, usuario=request.user, mensagem=mensagem, eh_publico=eh_publico
            )
            messages.success(request, "Interação adicionada com sucesso!")
        else:
            messages.error(request, "Mensagem não pode estar vazia.")

    return redirect("dashboard:ticket_detail", pk=ticket_id)


@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def update_ticket_status(request):
    """API para atualizar status do ticket via AJAX"""
    if request.method == "POST":
        ticket_id = request.POST.get("ticket_id")
        new_status = request.POST.get("status")

        if not ticket_id or not new_status:
            return JsonResponse({"success": False, "message": "Parâmetros ticket_id e status são obrigatórios!"})

        try:
            ticket = Ticket.objects.select_related("agente").get(id=ticket_id)

            is_assigned = hasattr(ticket, "agente") and ticket.agente == request.user
            if not (request.user.is_staff or is_assigned):
                return JsonResponse(
                    {"success": False, "message": "Sem permissão para alterar este ticket."}, status=403
                )

            old_status = ticket.status
            old_status_display = ticket.get_status_display()

            ticket.status = new_status
            ticket.save()

            new_status_display = ticket.get_status_display()

            InteracaoTicket.objects.create(
                ticket=ticket,
                usuario=request.user,
                mensagem=f'Status alterado de "{old_status_display}" para "{new_status_display}"',
                eh_publico=False,
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": "Status atualizado com sucesso!",
                    "old_status": old_status,
                    "new_status": new_status_display,
                }
            )
        except Ticket.DoesNotExist:
            return JsonResponse({"success": False, "message": "Ticket não encontrado!"})
        except Exception as e:
            logger.error(f"Erro ao atualizar ticket {ticket_id}: {e}", exc_info=True)
            return JsonResponse({"success": False, "message": "Erro interno ao processar a solicitação."}, status=500)

    return JsonResponse({"success": False, "message": "Método não permitido!"}, status=405)


# ========== DASHBOARD DO AGENTE ==========


@method_decorator(login_required, name="dispatch")
@method_decorator(role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente'), name='dispatch')
class AgenteDashboardView(TemplateView):
    template_name = "dashboard/agente/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        tickets_agente = Ticket.objects.filter(agente=user)
        context["meus_tickets_abertos"] = tickets_agente.filter(status__in=["aberto", "em_andamento"]).count()
        context["meus_tickets_total"] = tickets_agente.count()
        context["tickets_nao_atribuidos"] = Ticket.objects.filter(agente__isnull=True, status="aberto").count()
        context["tickets_recentes"] = tickets_agente.select_related("cliente", "categoria").order_by("-atualizado_em")[
            :5
        ]

        try:
            perfil_agente = PerfilAgente.objects.get(user=user)
            context["status_agente"] = perfil_agente.status
        except PerfilAgente.DoesNotExist:
            if user.is_staff or user.groups.filter(name="Agentes").exists():
                perfil_agente = PerfilAgente.objects.create(user=user, status="offline")
                context["status_agente"] = perfil_agente.status
            else:
                context["status_agente"] = "offline"

        return context


@method_decorator(login_required, name="dispatch")
@method_decorator(role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente'), name='dispatch')
class AgenteTicketsView(ListView):
    model = Ticket
    template_name = "dashboard/agente/tickets.html"
    context_object_name = "tickets"
    paginate_by = 15

    def get_queryset(self):
        return (
            Ticket.objects.filter(agente=self.request.user)
            .select_related("cliente", "categoria")
            .order_by("-atualizado_em")
        )
