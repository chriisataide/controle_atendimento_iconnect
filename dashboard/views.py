from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, get_user_model
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

# ========== REDIRECIONAMENTO INTELIGENTE ==========

def home_redirect(request):
    """
    Página inicial que redireciona inteligentemente baseado no status do usuário
    """
    if request.user.is_authenticated:
        # Se é superuser ou admin, vai para dashboard administrativo
        if request.user.is_superuser:
            return redirect('dashboard:admin_dashboard')
        # Se tem perfil de agente, vai para dashboard agente
        try:
            perfil = request.user.perfilusuario
            if perfil.tipo == 'agente':
                return redirect('dashboard:agente_dashboard')
            elif perfil.tipo == 'administrador':
                return redirect('dashboard:admin_dashboard')
        except:
            pass
        # Senão vai para o dashboard normal
        return redirect('dashboard:index')
    else:
        # Se não está logado, vai para login
        return redirect('login')

# ========== VIEWS DE ADMINISTRAÇÃO ==========

@login_required
def admin_dashboard(request):
    """
    Dashboard administrativo com acesso total ao sistema
    """
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Acesso negado. Você não tem permissões administrativas.')
        return redirect('dashboard:index')
    
    # Estatísticas gerais do sistema
    total_usuarios = User.objects.count()
    total_clientes = Cliente.objects.count()
    total_tickets = Ticket.objects.count()
    total_categorias = CategoriaTicket.objects.count()
    
    # Tickets por status
    tickets_abertos = Ticket.objects.filter(status='aberto').count()
    tickets_andamento = Ticket.objects.filter(status='em_andamento').count()
    tickets_resolvidos = Ticket.objects.filter(status='resolvido').count()
    tickets_fechados = Ticket.objects.filter(status='fechado').count()
    
    # Tickets por prioridade
    tickets_alta = Ticket.objects.filter(prioridade='alta').count()
    tickets_media = Ticket.objects.filter(prioridade='media').count()
    tickets_baixa = Ticket.objects.filter(prioridade='baixa').count()
    
    # Tickets recentes
    tickets_recentes = Ticket.objects.select_related('cliente', 'categoria').order_by('-criado_em')[:10]
    
    # Usuários recentes
    usuarios_recentes = User.objects.order_by('-date_joined')[:5]
    
    # Clientes recentes
    clientes_recentes = Cliente.objects.order_by('-criado_em')[:5]
    
    context = {
        'total_usuarios': total_usuarios,
        'total_clientes': total_clientes,
        'total_tickets': total_tickets,
        'total_categorias': total_categorias,
        'tickets_abertos': tickets_abertos,
        'tickets_andamento': tickets_andamento,
        'tickets_resolvidos': tickets_resolvidos,
        'tickets_fechados': tickets_fechados,
        'tickets_alta': tickets_alta,
        'tickets_media': tickets_media,
        'tickets_baixa': tickets_baixa,
        'tickets_recentes': tickets_recentes,
        'usuarios_recentes': usuarios_recentes,
        'clientes_recentes': clientes_recentes,
    }
    
    return render(request, 'dashboard/admin/dashboard.html', context)

# ========== VIEWS DE AUTENTICAÇÃO ==========

def custom_login(request):
    """
    View personalizada para login com template customizado
    """
    if request.user.is_authenticated:
        # Se já estiver logado, redireciona para dashboard
        return redirect('dashboard:index')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Bem-vindo, {user.get_full_name() or user.username}!')
                
                # Redireciona baseado no tipo de usuário
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                else:
                    return redirect('dashboard:index')
            else:
                messages.error(request, 'Nome de usuário ou senha incorretos.')
        else:
            messages.error(request, 'Por favor, preencha todos os campos.')
    
    return render(request, 'registration/login.html')

def custom_logout(request):
    """
    View personalizada para logout
    """
    username = request.user.get_full_name() or request.user.username
    logout(request)
    messages.success(request, f'Até logo, {username}! Logout realizado com sucesso.')
    return redirect('login')

@login_required
def get_user_info(request):
    """
    API para informações do usuário logado
    """
    user_data = {
        'username': request.user.username,
        'full_name': request.user.get_full_name(),
        'email': request.user.email,
        'is_superuser': request.user.is_superuser,
        'is_staff': request.user.is_staff,
        'user_type': 'admin' if request.user.is_superuser else 'user'
    }
    
    return JsonResponse(user_data)

@method_decorator(login_required, name='dispatch')
class DashboardView(TemplateView):
    template_name = 'dashboard/index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Cálculos dinâmicos de métricas
        hoje = timezone.now().date()
        ontem = hoje - timedelta(days=1)
        mes_atual = hoje.replace(day=1)
        
        # Atendimentos hoje vs ontem
        atendimentos_hoje = Ticket.objects.filter(criado_em__date=hoje).count()
        atendimentos_ontem = Ticket.objects.filter(criado_em__date=ontem).count()
        
        if atendimentos_ontem > 0:
            variacao_atendimentos = ((atendimentos_hoje - atendimentos_ontem) / atendimentos_ontem) * 100
        else:
            variacao_atendimentos = 100 if atendimentos_hoje > 0 else 0
        
        # Usuários ativos (logados nas últimas 24h)
        usuarios_ativos = User.objects.filter(
            last_login__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        # Tickets por status
        try:
            tickets_abertos = Ticket.objects.filter(
                status__nome__in=['Aberto', 'Em Andamento']
            ).count()
        except:
            # Fallback se não houver campo 'nome' no status
            tickets_abertos = Ticket.objects.filter(status='aberto').count()
        
        # Taxa de resolução
        tickets_mes = Ticket.objects.filter(criado_em__gte=mes_atual)
        total_mes = tickets_mes.count()
        try:
            resolvidos_mes = tickets_mes.filter(
                status__nome__in=['Resolvido', 'Fechado']
            ).count()
        except:
            resolvidos_mes = tickets_mes.filter(status='resolvido').count()
        
        taxa_resolucao = (resolvidos_mes / total_mes * 100) if total_mes > 0 else 94.2
        
        # Dados para o template
        context.update({
            'atendimentos_hoje': atendimentos_hoje,
            'variacao_atendimentos': round(variacao_atendimentos, 1),
            'usuarios_ativos': usuarios_ativos,
            'tickets_abertos': tickets_abertos,
            'taxa_resolucao': round(taxa_resolucao, 1),
        })
        
        # Tickets recentes com relacionamentos
        context['tickets_recentes'] = Ticket.objects.select_related(
            'cliente', 'categoria'
        ).order_by('-criado_em')[:10]
        
        # Agentes status (simulado por enquanto)
        context['agentes_status'] = [
            {'user': {'get_full_name': lambda: 'João Silva'}, 'status': 'online', 'tickets_ativos': 3},
            {'user': {'get_full_name': lambda: 'Maria Santos'}, 'status': 'ocupado', 'tickets_ativos': 5},
            {'user': {'get_full_name': lambda: 'Carlos Lima'}, 'status': 'online', 'tickets_ativos': 1},
        ]
        
        # Dados para gráficos (em formato JSON-ready)
        context['atendimentos_por_hora'] = [12, 19, 15, 23, 18, 25, 10]
        context['tickets_por_mes'] = [50, 40, 300, 320, 500, 350, 200, 230, 500]
        
        # Dados legados mantidos para compatibilidade
        context['total_clientes'] = Cliente.objects.count()
        context['tickets_fechados'] = resolvidos_mes
        context['total_tickets'] = Ticket.objects.count()
        
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
        
        # Verificar se o usuário é um cliente
        try:
            cliente = Cliente.objects.get(email=self.request.user.email)
            context['cliente_logado'] = cliente
            context['is_cliente'] = True
        except Cliente.DoesNotExist:
            context['is_cliente'] = False
            
        return context
    
    def form_valid(self, form):
        # Se for um cliente logado, associar automaticamente
        try:
            cliente = Cliente.objects.get(email=self.request.user.email)
            form.instance.cliente = cliente
        except Cliente.DoesNotExist:
            pass
            
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
            
            # Estatísticas básicas
            context['cliente'] = cliente
            context['total_tickets'] = tickets_cliente.count()
            context['tickets_abertos'] = tickets_cliente.filter(status='aberto').count()
            context['tickets_em_andamento'] = tickets_cliente.filter(status='em_andamento').count()
            context['tickets_resolvidos'] = tickets_cliente.filter(status='resolvido').count()
            context['tickets_fechados'] = tickets_cliente.filter(status='fechado').count()
            context['tickets_recentes'] = tickets_cliente.order_by('-criado_em')[:5]
            
            # Estatísticas por prioridade
            context['tickets_alta_prioridade'] = tickets_cliente.filter(prioridade='alta').count()
            context['tickets_media_prioridade'] = tickets_cliente.filter(prioridade='media').count()
            context['tickets_baixa_prioridade'] = tickets_cliente.filter(prioridade='baixa').count()
            
            # Estatísticas por categoria (se existir)
            if hasattr(tickets_cliente.first(), 'categoria'):
                context['tickets_por_categoria'] = tickets_cliente.values('categoria').annotate(
                    count=Count('categoria')
                ).order_by('-count')[:5]
            
            # Tempo médio de resposta (simulado por enquanto)
            context['tempo_medio_resposta'] = '2h 15min'
            
            # Último ticket criado
            ultimo_ticket = tickets_cliente.order_by('-criado_em').first()
            context['ultimo_ticket'] = ultimo_ticket
            
            # Notificações - tickets com mudanças recentes (últimas 24h)
            agora = timezone.now()
            ontem = agora - timedelta(days=1)
            context['tickets_recentes_mudancas'] = tickets_cliente.filter(
                atualizado_em__gte=ontem
            ).count()
            
            # Tickets aguardando resposta do cliente
            context['tickets_aguardando_cliente'] = tickets_cliente.filter(
                status='aguardando_cliente'
            ).count()
            
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
            queryset = Ticket.objects.filter(cliente=cliente).select_related('categoria', 'agente')
            
            # Aplicar filtros se fornecidos
            status_filter = self.request.GET.get('status')
            if status_filter:
                queryset = queryset.filter(status=status_filter)
                
            prioridade_filter = self.request.GET.get('prioridade')
            if prioridade_filter:
                queryset = queryset.filter(prioridade=prioridade_filter)
                
            search_query = self.request.GET.get('q')
            if search_query:
                queryset = queryset.filter(
                    Q(numero__icontains=search_query) |
                    Q(titulo__icontains=search_query) |
                    Q(descricao__icontains=search_query)
                )
            
            # Ordenação (padrão: mais recentes primeiro)
            order_by = self.request.GET.get('order', '-criado_em')
            queryset = queryset.order_by(order_by)
            
            return queryset
        except Cliente.DoesNotExist:
            return Ticket.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            cliente = Cliente.objects.get(email=self.request.user.email)
            context['cliente'] = cliente
            
            # Estatísticas para filtros
            all_tickets = Ticket.objects.filter(cliente=cliente)
            context['total_tickets'] = all_tickets.count()
            context['tickets_abertos'] = all_tickets.filter(status='aberto').count()
            context['tickets_em_andamento'] = all_tickets.filter(status='em_andamento').count()
            context['tickets_resolvidos'] = all_tickets.filter(status='resolvido').count()
            context['tickets_fechados'] = all_tickets.filter(status='fechado').count()
            
        except Cliente.DoesNotExist:
            context['cliente'] = None
            
        return context


# ========== APIs AJAX ==========

@login_required
def cliente_stats_ajax(request):
    """API para estatísticas do cliente em tempo real"""
    try:
        cliente = Cliente.objects.get(email=request.user.email)
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


# ========== VIEWS DE MÉTRICAS E AJAX ==========

@login_required
def ajax_metrics(request):
    """
    Endpoint AJAX para atualização das métricas em tempo real
    """
    if request.method == 'GET':
        try:
            # Calcular métricas em tempo real
            hoje = timezone.now().date()
            ontem = hoje - timedelta(days=1)
            
            atendimentos_hoje = Ticket.objects.filter(
                criado_em__date=hoje
            ).count()
            
            atendimentos_ontem = Ticket.objects.filter(
                criado_em__date=ontem
            ).count()
            
            if atendimentos_ontem > 0:
                variacao_atendimentos = ((atendimentos_hoje - atendimentos_ontem) / atendimentos_ontem) * 100
            else:
                variacao_atendimentos = 100 if atendimentos_hoje > 0 else 0
            
            usuarios_ativos = User.objects.filter(
                last_login__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            tickets_abertos = Ticket.objects.filter(
                status__nome__in=['Aberto', 'Em Andamento']
            ).count()
            
            # Taxa de resolução
            mes_atual = hoje.replace(day=1)
            tickets_mes = Ticket.objects.filter(criado_em__gte=mes_atual)
            total_mes = tickets_mes.count()
            resolvidos_mes = tickets_mes.filter(
                status__nome__in=['Resolvido', 'Fechado']
            ).count()
            taxa_resolucao = (resolvidos_mes / total_mes * 100) if total_mes > 0 else 0
            
            metrics = {
                'atendimentos_hoje': atendimentos_hoje,
                'variacao_atendimentos': round(variacao_atendimentos, 1),
                'usuarios_ativos': usuarios_ativos,
                'tickets_abertos': tickets_abertos,
                'taxa_resolucao': round(taxa_resolucao, 1),
            }
            
            return JsonResponse(metrics)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Método não permitido'}, status=405)


@login_required
def export_tickets(request):
    """
    View para exportar dados dos tickets
    """
    from django.http import HttpResponse
    import csv
    from datetime import datetime
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="tickets_{datetime.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Número', 'Cliente', 'Status', 'Data Criação', 'Categoria'])
    
    # Buscar tickets do banco de dados
    tickets = Ticket.objects.select_related('cliente', 'status', 'categoria')[:1000]  # Limitar a 1000
    
    for ticket in tickets:
        writer.writerow([
            ticket.id,
            ticket.numero,
            ticket.cliente.nome if ticket.cliente else 'N/A',
            ticket.status.nome if ticket.status else 'N/A',
            ticket.criado_em.strftime('%d/%m/%Y %H:%M'),
            ticket.categoria.nome if ticket.categoria else 'N/A'
        ])
    
    return response
