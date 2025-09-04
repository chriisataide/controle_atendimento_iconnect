from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView
from django.db.models import Count, Q
from django.http import JsonResponse
from django.urls import reverse_lazy, reverse
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Cliente, Ticket, PerfilUsuario, CategoriaTicket, InteracaoTicket, PerfilAgente, StatusTicket, PrioridadeTicket

User = get_user_model()

@method_decorator(login_required, name='dispatch')
class DashboardView(TemplateView):
    template_name = 'dashboard/index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_clientes'] = Cliente.objects.count()
        
        # Contagem de tickets por status
        tickets_stats = Ticket.objects.values('status').annotate(count=Count('id'))
        context['tickets_abertos'] = sum(item['count'] for item in tickets_stats if item['status'] in ['aberto', 'em_andamento'])
        context['tickets_fechados'] = sum(item['count'] for item in tickets_stats if item['status'] == 'fechado')
        context['total_tickets'] = Ticket.objects.count()
        
        # Tickets recentes
        context['tickets_recentes'] = Ticket.objects.select_related('cliente', 'categoria', 'agente')[:5]
        
        # Dados para gráficos
        hoje = timezone.now().date()
        semana_passada = hoje - timedelta(days=7)
        context['tickets_semana'] = Ticket.objects.filter(criado_em__date__gte=semana_passada).count()
        
        return context


# ========== SISTEMA DE TICKETS ==========

@method_decorator(login_required, name='dispatch')
class TicketListView(ListView):
    model = Ticket
    template_name = 'dashboard/tickets/list.html'
    context_object_name = 'tickets'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = Ticket.objects.select_related('cliente', 'categoria', 'agente').order_by('-criado_em')
        
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
            
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(numero__icontains=search) |
                Q(titulo__icontains=search) |
                Q(cliente__nome__icontains=search) |
                Q(cliente__email__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categorias'] = CategoriaTicket.objects.all()
        context['status_choices'] = StatusTicket.choices
        context['prioridade_choices'] = PrioridadeTicket.choices
        context['filters'] = self.request.GET
        return context


@method_decorator(login_required, name='dispatch')
class TicketDetailView(DetailView):
    model = Ticket
    template_name = 'dashboard/tickets/detail.html'
    context_object_name = 'ticket'
    
    def get_queryset(self):
        return Ticket.objects.select_related('cliente', 'categoria', 'agente').prefetch_related('interacoes__usuario')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['interacoes'] = self.object.interacoes.all().order_by('criado_em')
        return context


@method_decorator(login_required, name='dispatch')
class TicketCreateView(CreateView):
    model = Ticket
    template_name = 'dashboard/tickets/create.html'
    fields = ['cliente', 'categoria', 'titulo', 'descricao', 'prioridade']
    
    def get_success_url(self):
        return reverse('dashboard:ticket_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['clientes'] = Cliente.objects.all().order_by('nome')
        context['categorias'] = CategoriaTicket.objects.all()
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'Ticket criado com sucesso!')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class TicketUpdateView(UpdateView):
    model = Ticket
    template_name = 'dashboard/tickets/update.html'
    fields = ['cliente', 'categoria', 'titulo', 'descricao', 'status', 'prioridade', 'agente']
    
    def get_success_url(self):
        return reverse('dashboard:ticket_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['clientes'] = Cliente.objects.all().order_by('nome')
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


# ========== DASHBOARD DO AGENTE ==========

@method_decorator(login_required, name='dispatch')
class AgenteDashboardView(TemplateView):
    template_name = 'dashboard/agente/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Tickets do agente
        tickets_agente = Ticket.objects.filter(agente=user)
        context['meus_tickets_abertos'] = tickets_agente.filter(status__in=['aberto', 'em_andamento']).count()
        context['meus_tickets_total'] = tickets_agente.count()
        
        # Tickets não atribuídos
        context['tickets_nao_atribuidos'] = Ticket.objects.filter(agente__isnull=True, status='aberto').count()
        
        # Tickets recentes do agente
        context['tickets_recentes'] = tickets_agente.order_by('-atualizado_em')[:5]
        
        # Status do agente
        try:
            perfil_agente = PerfilAgente.objects.get(user=user)
            context['status_agente'] = perfil_agente.status
        except PerfilAgente.DoesNotExist:
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


# ========== PORTAL DO CLIENTE ==========

@method_decorator(login_required, name='dispatch')
class ClientePortalView(TemplateView):
    template_name = 'dashboard/cliente/portal.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Buscar cliente pelo email do usuário
        try:
            cliente = Cliente.objects.get(email=self.request.user.email)
            tickets_cliente = Ticket.objects.filter(cliente=cliente)
            
            context['cliente'] = cliente
            context['total_tickets'] = tickets_cliente.count()
            context['tickets_abertos'] = tickets_cliente.filter(status__in=['aberto', 'em_andamento']).count()
            context['tickets_fechados'] = tickets_cliente.filter(status='fechado').count()
            context['tickets_recentes'] = tickets_cliente.order_by('-criado_em')[:5]
            
        except Cliente.DoesNotExist:
            context['cliente'] = None
            
        return context


@method_decorator(login_required, name='dispatch')
class ClienteTicketsView(ListView):
    model = Ticket
    template_name = 'dashboard/cliente/tickets.html'
    context_object_name = 'tickets'
    paginate_by = 10
    
    def get_queryset(self):
        try:
            cliente = Cliente.objects.get(email=self.request.user.email)
            return Ticket.objects.filter(cliente=cliente).select_related('categoria', 'agente').order_by('-criado_em')
        except Cliente.DoesNotExist:
            return Ticket.objects.none()


# ========== APIs AJAX ==========

@login_required
def update_ticket_status(request):
    """API para atualizar status do ticket via AJAX"""
    if request.method == 'POST':
        ticket_id = request.POST.get('ticket_id')
        new_status = request.POST.get('status')
        
        try:
            ticket = Ticket.objects.get(id=ticket_id)
            ticket.status = new_status
            ticket.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Status atualizado com sucesso!',
                'new_status': ticket.get_status_display()
            })
        except Ticket.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Ticket não encontrado!'
            })
    
    return JsonResponse({'success': False, 'message': 'Método não permitido!'})


@login_required
def update_agent_status(request):
    """API para atualizar status do agente"""
    if request.method == 'POST':
        new_status = request.POST.get('status')
        
        try:
            perfil_agente, created = PerfilAgente.objects.get_or_create(
                user=request.user,
                defaults={'status': new_status}
            )
            if not created:
                perfil_agente.status = new_status
                perfil_agente.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Status alterado para {perfil_agente.get_status_display()}',
                'new_status': perfil_agente.get_status_display()
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método não permitido!'})

@method_decorator(login_required, name='dispatch')
class ProfileView(TemplateView):
    template_name = 'dashboard/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Busca ou cria o perfil do usuário
        perfil, created = PerfilUsuario.objects.get_or_create(
            user=self.request.user,
            defaults={'telefone': ''}
        )
        context['perfil'] = perfil
        return context
    
    def post(self, request, *args, **kwargs):
        try:
            # Busca ou cria o perfil do usuário
            perfil, created = PerfilUsuario.objects.get_or_create(
                user=request.user,
                defaults={'telefone': ''}
            )
            
            # Atualiza dados básicos do usuário
            user = request.user
            user.first_name = request.POST.get('first_name', '')
            user.last_name = request.POST.get('last_name', '')
            user.email = request.POST.get('email', '')
            user.save()
            
            # Atualiza dados do perfil
            perfil.telefone = request.POST.get('telefone', '')
            perfil.endereco = request.POST.get('endereco', '')
            perfil.bio = request.POST.get('bio', '')
            
            # Processa upload de avatar
            if 'avatar' in request.FILES:
                perfil.avatar = request.FILES['avatar']
            
            perfil.save()
            
            messages.success(request, 'Perfil atualizado com sucesso!')
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar perfil: {str(e)}')
            
        return redirect('dashboard:profile')
