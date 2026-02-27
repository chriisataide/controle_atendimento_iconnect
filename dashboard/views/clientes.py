"""
Views de clientes: portal, listagem, CRUD e estatísticas AJAX.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, ListView, CreateView, UpdateView
from django.db.models import Count, Q, Min
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from datetime import timedelta
import logging

from ..models import Cliente, Ticket
from ..forms import ClienteForm
from ..utils.security import rate_limit

logger = logging.getLogger('dashboard')
User = get_user_model()


def _calcular_tempo_medio_resposta(tickets_qs):
    """Calcula o tempo médio de primeira resposta dos tickets"""
    tickets_com_interacao = tickets_qs.filter(
        interacoes__isnull=False
    ).annotate(
        primeira_resposta=Min('interacoes__criado_em')
    ).filter(primeira_resposta__isnull=False)

    total_minutos = 0
    count = 0
    for t in tickets_com_interacao[:100]:
        diff = t.primeira_resposta - t.criado_em
        total_minutos += diff.total_seconds() / 60
        count += 1

    if count == 0:
        return 'N/A'

    media_min = total_minutos / count
    if media_min < 60:
        return f'{int(media_min)}min'
    horas = int(media_min // 60)
    minutos = int(media_min % 60)
    return f'{horas}h {minutos:02d}min'


# ========== PORTAL DO CLIENTE ==========

@method_decorator(login_required, name='dispatch')
class ClientePortalView(TemplateView):
    template_name = 'dashboard/cliente/portal.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_admin = user.is_staff or user.is_superuser
        context['is_admin'] = is_admin

        if is_admin:
            clientes = Cliente.objects.all()
            all_tickets = Ticket.objects.filter(cliente__isnull=False)

            context['cliente'] = True
            context['admin_view'] = True
            context['total_clientes'] = clientes.count()
            context['clientes_recentes'] = clientes.order_by('-criado_em')[:5]
            context['total_tickets'] = all_tickets.count()
            context['tickets_abertos'] = all_tickets.filter(status='aberto').count()
            context['tickets_em_andamento'] = all_tickets.filter(status='em_andamento').count()
            context['tickets_resolvidos'] = all_tickets.filter(status='resolvido').count()
            context['tickets_fechados'] = all_tickets.filter(status='fechado').count()
            context['tickets_recentes'] = all_tickets.order_by('-criado_em')[:10]
            context['tickets_alta_prioridade'] = all_tickets.filter(prioridade='alta').count()
            context['tickets_media_prioridade'] = all_tickets.filter(prioridade='media').count()
            context['tickets_baixa_prioridade'] = all_tickets.filter(prioridade='baixa').count()
            context['tempo_medio_resposta'] = _calcular_tempo_medio_resposta(all_tickets)

            ultimo_ticket = all_tickets.order_by('-criado_em').first()
            context['ultimo_ticket'] = ultimo_ticket

            agora = timezone.now()
            ontem = agora - timedelta(days=1)
            context['tickets_recentes_mudancas'] = all_tickets.filter(atualizado_em__gte=ontem).count()
            context['tickets_aguardando_cliente'] = all_tickets.filter(status='aguardando_cliente').count()

            context['top_clientes'] = Cliente.objects.annotate(
                num_tickets=Count('tickets')
            ).order_by('-num_tickets')[:10]
        else:
            try:
                cliente = Cliente.objects.get(email=user.email)
                tickets_cliente = Ticket.objects.filter(cliente=cliente)

                context['cliente'] = cliente
                context['admin_view'] = False
                context['total_tickets'] = tickets_cliente.count()
                context['tickets_abertos'] = tickets_cliente.filter(status='aberto').count()
                context['tickets_em_andamento'] = tickets_cliente.filter(status='em_andamento').count()
                context['tickets_resolvidos'] = tickets_cliente.filter(status='resolvido').count()
                context['tickets_fechados'] = tickets_cliente.filter(status='fechado').count()
                context['tickets_recentes'] = tickets_cliente.order_by('-criado_em')[:5]
                context['tickets_alta_prioridade'] = tickets_cliente.filter(prioridade='alta').count()
                context['tickets_media_prioridade'] = tickets_cliente.filter(prioridade='media').count()
                context['tickets_baixa_prioridade'] = tickets_cliente.filter(prioridade='baixa').count()
                context['tempo_medio_resposta'] = _calcular_tempo_medio_resposta(tickets_cliente)

                ultimo_ticket = tickets_cliente.order_by('-criado_em').first()
                context['ultimo_ticket'] = ultimo_ticket

                agora = timezone.now()
                ontem = agora - timedelta(days=1)
                context['tickets_recentes_mudancas'] = tickets_cliente.filter(atualizado_em__gte=ontem).count()
                context['tickets_aguardando_cliente'] = tickets_cliente.filter(status='aguardando_cliente').count()

            except Cliente.DoesNotExist:
                context['cliente'] = None
                context['admin_view'] = False

        return context


@method_decorator(login_required, name='dispatch')
class ClienteTicketsView(ListView):
    model = Ticket
    template_name = 'dashboard/cliente/tickets.html'
    context_object_name = 'tickets'
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        is_admin = user.is_staff or user.is_superuser

        if is_admin:
            queryset = Ticket.objects.filter(cliente__isnull=False).select_related('categoria', 'agente', 'cliente')
        else:
            try:
                cliente = Cliente.objects.get(email=user.email)
                queryset = Ticket.objects.filter(cliente=cliente).select_related('categoria', 'agente')
            except Cliente.DoesNotExist:
                return Ticket.objects.none()

        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        prioridade_filter = self.request.GET.get('prioridade')
        if prioridade_filter:
            queryset = queryset.filter(prioridade=prioridade_filter)

        cliente_filter = self.request.GET.get('cliente')
        if cliente_filter and is_admin:
            queryset = queryset.filter(cliente_id=cliente_filter)

        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(numero__icontains=search_query) |
                Q(titulo__icontains=search_query) |
                Q(descricao__icontains=search_query)
            )

        order_by = self.request.GET.get('order', '-criado_em')
        queryset = queryset.order_by(order_by)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_admin = user.is_staff or user.is_superuser
        context['is_admin'] = is_admin

        if is_admin:
            all_tickets = Ticket.objects.filter(cliente__isnull=False)
            context['cliente'] = True
            context['admin_view'] = True
            context['total_tickets'] = all_tickets.count()
            context['tickets_abertos'] = all_tickets.filter(status='aberto').count()
            context['tickets_em_andamento'] = all_tickets.filter(status='em_andamento').count()
            context['tickets_resolvidos'] = all_tickets.filter(status='resolvido').count()
            context['tickets_fechados'] = all_tickets.filter(status='fechado').count()
            context['clientes_list'] = Cliente.objects.all().order_by('nome')
        else:
            try:
                cliente = Cliente.objects.get(email=user.email)
                context['cliente'] = cliente
                context['admin_view'] = False
                all_tickets = Ticket.objects.filter(cliente=cliente)
                context['total_tickets'] = all_tickets.count()
                context['tickets_abertos'] = all_tickets.filter(status='aberto').count()
                context['tickets_em_andamento'] = all_tickets.filter(status='em_andamento').count()
                context['tickets_resolvidos'] = all_tickets.filter(status='resolvido').count()
                context['tickets_fechados'] = all_tickets.filter(status='fechado').count()
            except Cliente.DoesNotExist:
                context['cliente'] = None
                context['admin_view'] = False

        return context


# ========== CRUD DE CLIENTES (Admin) ==========

@method_decorator(login_required, name='dispatch')
class ClienteListView(ListView):
    model = Cliente
    template_name = 'dashboard/cliente/cliente_list.html'
    context_object_name = 'clientes'
    paginate_by = 15

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, 'Acesso restrito a administradores.')
            return redirect('dashboard:index')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Cliente.objects.annotate(
            num_pdvs=Count('pontos_de_venda', distinct=True),
            num_tickets=Count('tickets', distinct=True),
            tickets_abertos=Count('tickets', filter=Q(tickets__status='aberto'), distinct=True),
            tickets_andamento=Count('tickets', filter=Q(tickets__status='em_andamento'), distinct=True),
            tickets_resolvidos=Count('tickets', filter=Q(tickets__status__in=['resolvido', 'fechado']), distinct=True),
        ).order_by('-criado_em')

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nome__icontains=search) |
                Q(email__icontains=search) |
                Q(segmento__icontains=search) |
                Q(telefone__icontains=search)
            )

        segmento = self.request.GET.get('segmento')
        if segmento:
            queryset = queryset.filter(segmento__iexact=segmento)

        status = self.request.GET.get('status')
        if status == 'ativo':
            queryset = queryset.filter(ativo=True)
        elif status == 'inativo':
            queryset = queryset.filter(ativo=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from ..models import PontoDeVenda
        all_clients = Cliente.objects.all()
        context['total_clientes'] = all_clients.count()
        context['clientes_ativos'] = all_clients.filter(ativo=True).count()
        context['clientes_inativos'] = all_clients.filter(ativo=False).count()
        context['total_pdvs'] = PontoDeVenda.objects.count()
        context['clientes_com_tickets'] = all_clients.filter(tickets__isnull=False).distinct().count()
        context['total_tickets_clientes'] = Ticket.objects.filter(cliente__isnull=False).count()
        context['segmentos'] = all_clients.exclude(
            Q(segmento='') | Q(segmento__isnull=True)
        ).values_list('segmento', flat=True).distinct().order_by('segmento')
        context['search'] = self.request.GET.get('search', '')
        context['segmento_selected'] = self.request.GET.get('segmento', '')
        context['status_selected'] = self.request.GET.get('status', '')
        return context


@method_decorator(login_required, name='dispatch')
class ClienteCreateView(CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'dashboard/cliente/cliente_form.html'
    success_url = reverse_lazy('dashboard:cliente_list')

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, 'Acesso restrito a administradores.')
            return redirect('dashboard:index')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, f'Cliente "{form.instance.nome}" criado com sucesso!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo Cliente'
        context['btn_text'] = 'Cadastrar'
        return context


@method_decorator(login_required, name='dispatch')
class ClienteUpdateView(UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'dashboard/cliente/cliente_form.html'
    success_url = reverse_lazy('dashboard:cliente_list')

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, 'Acesso restrito a administradores.')
            return redirect('dashboard:index')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, f'Cliente "{form.instance.nome}" atualizado com sucesso!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Editar Cliente: {self.object.nome}'
        context['btn_text'] = 'Salvar Alterações'
        return context


@login_required
def cliente_detail_view(request, pk):
    """Detalhe de um cliente com seus tickets"""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Acesso restrito a administradores.')
        return redirect('dashboard:index')

    cliente = get_object_or_404(Cliente, pk=pk)
    tickets = Ticket.objects.filter(cliente=cliente).select_related('categoria', 'agente').order_by('-criado_em')

    context = {
        'cliente': cliente,
        'tickets': tickets[:20],
        'total_tickets': tickets.count(),
        'tickets_abertos': tickets.filter(status='aberto').count(),
        'tickets_em_andamento': tickets.filter(status='em_andamento').count(),
        'tickets_resolvidos': tickets.filter(status='resolvido').count(),
        'tickets_fechados': tickets.filter(status='fechado').count(),
        'tickets_alta': tickets.filter(prioridade='alta').count(),
        'tempo_medio': _calcular_tempo_medio_resposta(tickets),
    }
    return render(request, 'dashboard/cliente/cliente_detail.html', context)


@login_required
def cliente_delete_view(request, pk):
    """Excluir um cliente"""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Acesso restrito a administradores.')
        return redirect('dashboard:index')

    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        nome = cliente.nome
        cliente.delete()
        messages.success(request, f'Cliente "{nome}" excluído com sucesso!')
        return redirect('dashboard:cliente_list')

    return redirect('dashboard:cliente_list')


@login_required
@rate_limit(max_requests=120, window_seconds=3600)
def cliente_stats_ajax(request):
    """
    API para estatísticas do cliente em tempo real
    """
    user = request.user
    is_admin = user.is_staff or user.is_superuser

    try:
        if is_admin:
            tickets_cliente = Ticket.objects.filter(cliente__isnull=False)
        else:
            cliente = Cliente.objects.get(email=user.email)
            tickets_cliente = Ticket.objects.filter(cliente=cliente)

        stats = {
            'total_tickets': tickets_cliente.count(),
            'tickets_abertos': tickets_cliente.filter(status='aberto').count(),
            'tickets_em_andamento': tickets_cliente.filter(status='em_andamento').count(),
            'tickets_resolvidos': tickets_cliente.filter(status='resolvido').count(),
            'tickets_fechados': tickets_cliente.filter(status='fechado').count(),
            'ultimo_update': timezone.now().strftime('%H:%M:%S'),
            'tickets_alta_prioridade': tickets_cliente.filter(prioridade='alta').count(),
            'tickets_media_prioridade': tickets_cliente.filter(prioridade='media').count(),
            'tickets_baixa_prioridade': tickets_cliente.filter(prioridade='baixa').count(),
        }

        return JsonResponse(stats)
    except Cliente.DoesNotExist:
        return JsonResponse({'error': 'Cliente não encontrado'}, status=404)
