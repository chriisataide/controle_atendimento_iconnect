"""
Views de tickets: CRUD, Kanban, interações e dashboard do agente.
"""
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView
from django.db.models import Count, Q, Avg, F, ExpressionWrapper, DurationField
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import json
import logging

from ..models import (
    Cliente, Ticket, CategoriaTicket, InteracaoTicket, PerfilAgente,
    StatusTicket, PrioridadeTicket, TicketAnexo, PontoDeVenda,
)
from ..forms import TicketCreateForm
from .helpers import get_role_filtered_tickets, user_can_access_ticket

logger = logging.getLogger('dashboard')
User = get_user_model()


# ========== KANBAN BOARD ==========

@method_decorator(login_required, name='dispatch')
class KanbanBoardView(TemplateView):
    """Visualização Kanban do pipeline de tickets"""
    template_name = 'dashboard/tickets/kanban.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_qs = Ticket.objects.select_related('cliente', 'agente', 'categoria').order_by('-prioridade', '-criado_em')

        # RBAC: filtrar tickets por papel do usuário
        base_qs = get_role_filtered_tickets(self.request.user, base_qs)

        # Filtros opcionais
        agente = self.request.GET.get('agente')
        if agente:
            base_qs = base_qs.filter(agente_id=agente)
        categoria = self.request.GET.get('categoria')
        if categoria:
            base_qs = base_qs.filter(categoria_id=categoria)

        columns = [
            ('aberto', 'Aberto', 'info'),
            ('em_andamento', 'Em Andamento', 'warning'),
            ('aguardando_cliente', 'Aguardando Cliente', 'secondary'),
            ('resolvido', 'Resolvido', 'success'),
            ('fechado', 'Fechado', 'dark'),
        ]
        kanban_columns = []
        for status_key, label, color in columns:
            tickets = base_qs.filter(status=status_key)[:50]
            kanban_columns.append({
                'status': status_key,
                'label': label,
                'color': color,
                'tickets': tickets,
                'count': tickets.count() if hasattr(tickets, 'count') else len(tickets),
            })

        context['columns'] = kanban_columns
        context['agentes'] = User.objects.filter(perfilagente__isnull=False, is_active=True).order_by('first_name')
        context['categorias'] = CategoriaTicket.objects.all()
        return context


# ========== SISTEMA DE TICKETS ==========

@method_decorator(login_required, name='dispatch')
class TicketListView(ListView):
    model = Ticket
    template_name = 'dashboard/tickets/list.html'
    context_object_name = 'tickets'
    paginate_by = 15

    def get_queryset(self):
        queryset = Ticket.objects.select_related('cliente', 'categoria', 'agente').order_by('-criado_em')

        # RBAC: filtrar tickets por papel do usuário
        queryset = get_role_filtered_tickets(self.request.user, queryset)

        # Filtros
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        categoria_filter = self.request.GET.get('categoria')
        if categoria_filter:
            queryset = queryset.filter(categoria_id=categoria_filter)

        prioridade_filter = self.request.GET.get('prioridade')
        if prioridade_filter:
            queryset = queryset.filter(prioridade=prioridade_filter)

        agente_filter = self.request.GET.get('agente')
        if agente_filter:
            if agente_filter == 'none':
                queryset = queryset.filter(agente__isnull=True)
            else:
                queryset = queryset.filter(agente_id=agente_filter)

        # Filtro por data
        data_inicio = self.request.GET.get('data_inicio')
        data_fim = self.request.GET.get('data_fim')
        if data_inicio:
            queryset = queryset.filter(criado_em__date__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(criado_em__date__lte=data_fim)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(numero__icontains=search) |
                Q(titulo__icontains=search) |
                Q(cliente__nome__icontains=search) |
                Q(cliente__email__icontains=search) |
                Q(descricao__icontains=search)
            )

        self._filtered_queryset = queryset
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categorias'] = CategoriaTicket.objects.all()
        context['status_choices'] = StatusTicket.choices
        context['prioridade_choices'] = PrioridadeTicket.choices
        context['filters'] = self.request.GET
        context['agentes'] = User.objects.filter(perfilagente__isnull=False, is_active=True).order_by('first_name')

        # KPIs baseados no queryset completo (sem paginação)
        all_tickets = Ticket.objects.all()
        context['kpi_total'] = all_tickets.count()
        context['kpi_abertos'] = all_tickets.filter(status=StatusTicket.ABERTO).count()
        context['kpi_andamento'] = all_tickets.filter(status=StatusTicket.EM_ANDAMENTO).count()
        context['kpi_resolvidos'] = all_tickets.filter(status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO]).count()
        context['kpi_criticos'] = all_tickets.filter(prioridade=PrioridadeTicket.CRITICA, status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO]).count()
        context['kpi_nao_atribuidos'] = all_tickets.filter(agente__isnull=True, status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO]).count()

        # Tempo médio de resolução
        tempo_medio_qs = all_tickets.filter(
            status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO],
            resolvido_em__isnull=False,
        ).annotate(
            duracao=ExpressionWrapper(F('resolvido_em') - F('criado_em'), output_field=DurationField())
        ).aggregate(media=Avg('duracao'))
        tempo = tempo_medio_qs.get('media')
        if tempo:
            total_sec = int(tempo.total_seconds())
            h = total_sec // 3600
            m = (total_sec % 3600) // 60
            context['kpi_tempo_medio'] = f'{h}h {m}min' if h < 24 else f'{h // 24}d {h % 24}h'
        else:
            context['kpi_tempo_medio'] = '--'

        # Taxa de resolução (este mês)
        mes_atual = timezone.now().date().replace(day=1)
        tickets_mes = all_tickets.filter(criado_em__date__gte=mes_atual)
        total_mes = tickets_mes.count()
        resolvidos_mes = tickets_mes.filter(status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO]).count()
        context['kpi_taxa_resolucao'] = round((resolvidos_mes / total_mes * 100), 1) if total_mes > 0 else 0

        return context


@method_decorator(login_required, name='dispatch')
class TicketDetailView(DetailView):
    model = Ticket
    template_name = 'dashboard/tickets/detail.html'
    context_object_name = 'ticket'

    def get_queryset(self):
        base_qs = Ticket.objects.select_related('cliente', 'categoria', 'agente').prefetch_related('interacoes__usuario')
        return get_role_filtered_tickets(self.request.user, base_qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['interacoes'] = self.object.interacoes.all().order_by('criado_em')
        context['anexos'] = self.object.anexos.all() if hasattr(self.object, 'anexos') else []
        context['status_choices'] = StatusTicket.choices
        context['cliente_total_tickets'] = Ticket.objects.filter(cliente=self.object.cliente).count()
        return context


@method_decorator(login_required, name='dispatch')
class TicketCreateView(CreateView):
    model = Ticket
    template_name = 'dashboard/tickets/create.html'
    form_class = TicketCreateForm

    def get_success_url(self):
        return reverse('dashboard:ticket_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['clientes'] = Cliente.objects.all().order_by('nome')
        context['pontos_de_venda'] = PontoDeVenda.objects.select_related('cliente').all().order_by('nome_fantasia')
        context['categorias'] = CategoriaTicket.objects.all()

        try:
            cliente = Cliente.objects.get(email=self.request.user.email)
            context['cliente_logado'] = cliente
            context['is_cliente'] = True
        except Cliente.DoesNotExist:
            context['is_cliente'] = False

        return context

    def form_valid(self, form):
        try:
            cliente = Cliente.objects.get(email=self.request.user.email)
            form.instance.cliente = cliente
        except Cliente.DoesNotExist:
            pass

        response = super().form_valid(form)

        # Processar produtos e serviços (se enviados)
        produtos_dados = self.request.POST.get('produtos_dados')
        if produtos_dados:
            try:
                from decimal import Decimal
                from ..models import ItemAtendimento
                from ..models import Produto

                itens = json.loads(produtos_dados)

                for item in itens:
                    produto_id = item['produto']['id']
                    quantidade = Decimal(str(item['quantidade']))
                    valor_unitario = Decimal(str(item['valorUnitario']))
                    desconto_percentual = Decimal(str(item['descontoPercentual']))
                    observacoes = item.get('observacoes', '')
                    tipo_item = item['produto']['tipo']

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
                            adicionado_por=self.request.user
                        )
                    except Produto.DoesNotExist:
                        logger.warning("Produto ID %s nao encontrado", produto_id)
                        continue

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.error("Erro ao processar produtos: %s", e, exc_info=True)

        # Processar anexos
        if 'anexos' in self.request.FILES:
            from ..utils.security import validate_file_upload
            anexos = self.request.FILES.getlist('anexos')
            for anexo in anexos:
                is_valid, error_msg = validate_file_upload(anexo)
                if is_valid:
                    TicketAnexo.objects.create(
                        ticket=self.object,
                        arquivo=anexo,
                        nome_original=anexo.name,
                        tamanho=anexo.size,
                        tipo_mime=anexo.content_type or 'application/octet-stream',
                        criado_por=self.request.user
                    )
                else:
                    logger.warning('Upload rejeitado para ticket #%s: %s — %s', self.object.numero, anexo.name, error_msg)

        messages.success(self.request, f'Ticket #{self.object.numero} criado com sucesso!')
        return response


@method_decorator(login_required, name='dispatch')
class TicketUpdateView(UpdateView):
    model = Ticket
    template_name = 'dashboard/tickets/update.html'
    fields = ['cliente', 'ponto_de_venda', 'categoria', 'titulo', 'descricao', 'status', 'prioridade', 'agente']

    def get_queryset(self):
        base_qs = Ticket.objects.all()
        return get_role_filtered_tickets(self.request.user, base_qs)

    def get_success_url(self):
        return reverse('dashboard:ticket_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['clientes'] = Cliente.objects.all().order_by('nome')
        context['pontos_de_venda'] = PontoDeVenda.objects.select_related('cliente').all().order_by('nome_fantasia')
        context['categorias'] = CategoriaTicket.objects.all()
        context['agentes'] = User.objects.filter(perfilagente__isnull=False)
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Ticket atualizado com sucesso!')
        return super().form_valid(form)


@login_required
def add_interaction(request, ticket_id):
    """Adiciona uma nova interação ao ticket"""
    if request.method == 'POST':
        ticket = get_object_or_404(Ticket, id=ticket_id)

        if not user_can_access_ticket(request.user, ticket):
            messages.error(request, 'Você não tem permissão para interagir com este ticket.')
            return redirect('dashboard:ticket_list')

        mensagem = request.POST.get('mensagem')
        eh_publico = request.POST.get('eh_publico') == 'on'

        if mensagem:
            InteracaoTicket.objects.create(
                ticket=ticket,
                usuario=request.user,
                mensagem=mensagem,
                eh_publico=eh_publico
            )
            messages.success(request, 'Interação adicionada com sucesso!')
        else:
            messages.error(request, 'Mensagem não pode estar vazia.')

    return redirect('dashboard:ticket_detail', pk=ticket_id)


@login_required
def update_ticket_status(request):
    """API para atualizar status do ticket via AJAX"""
    if request.method == 'POST':
        ticket_id = request.POST.get('ticket_id')
        new_status = request.POST.get('status')

        if not ticket_id or not new_status:
            return JsonResponse({
                'success': False,
                'message': 'Parâmetros ticket_id e status são obrigatórios!'
            })

        try:
            ticket = Ticket.objects.select_related('agente').get(id=ticket_id)

            is_assigned = hasattr(ticket, 'agente') and ticket.agente == request.user
            if not (request.user.is_staff or is_assigned):
                return JsonResponse({
                    'success': False,
                    'message': 'Sem permissão para alterar este ticket.'
                }, status=403)

            old_status = ticket.status
            old_status_display = ticket.get_status_display()

            ticket.status = new_status
            ticket.save()

            new_status_display = ticket.get_status_display()

            InteracaoTicket.objects.create(
                ticket=ticket,
                usuario=request.user,
                mensagem=f'Status alterado de "{old_status_display}" para "{new_status_display}"',
                eh_publico=False
            )

            return JsonResponse({
                'success': True,
                'message': 'Status atualizado com sucesso!',
                'old_status': old_status,
                'new_status': new_status_display
            })
        except Ticket.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Ticket não encontrado!'
            })
        except Exception as e:
            logger.error(f'Erro ao atualizar ticket {ticket_id}: {e}', exc_info=True)
            return JsonResponse({
                'success': False,
                'message': 'Erro interno ao processar a solicitação.'
            }, status=500)

    return JsonResponse({'success': False, 'message': 'Método não permitido!'}, status=405)


# ========== DASHBOARD DO AGENTE ==========

@method_decorator(login_required, name='dispatch')
class AgenteDashboardView(TemplateView):
    template_name = 'dashboard/agente/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        tickets_agente = Ticket.objects.filter(agente=user)
        context['meus_tickets_abertos'] = tickets_agente.filter(status__in=['aberto', 'em_andamento']).count()
        context['meus_tickets_total'] = tickets_agente.count()
        context['tickets_nao_atribuidos'] = Ticket.objects.filter(agente__isnull=True, status='aberto').count()
        context['tickets_recentes'] = tickets_agente.select_related('cliente', 'categoria').order_by('-atualizado_em')[:5]

        try:
            perfil_agente = PerfilAgente.objects.get(user=user)
            context['status_agente'] = perfil_agente.status
        except PerfilAgente.DoesNotExist:
            if user.is_staff or user.groups.filter(name='Agentes').exists():
                perfil_agente = PerfilAgente.objects.create(user=user, status='offline')
                context['status_agente'] = perfil_agente.status
            else:
                context['status_agente'] = 'offline'

        return context


@method_decorator(login_required, name='dispatch')
class AgenteTicketsView(ListView):
    model = Ticket
    template_name = 'dashboard/agente/tickets.html'
    context_object_name = 'tickets'
    paginate_by = 15

    def get_queryset(self):
        return Ticket.objects.filter(agente=self.request.user).select_related('cliente', 'categoria').order_by('-atualizado_em')
