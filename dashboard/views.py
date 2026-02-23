from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView
from django.db.models import Count, Q, Min
from django.http import JsonResponse
from django.urls import reverse_lazy, reverse
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count, Case, When, IntegerField
from datetime import datetime, timedelta
import json
import logging
from .models import Cliente, Ticket, PerfilUsuario, CategoriaTicket, InteracaoTicket, PerfilAgente, StatusTicket, PrioridadeTicket, TicketAnexo, Notification
from .security import rate_limit, log_suspicious_activity
from .api_versioning import api_version, APIResponseTransformer
from .audit_system import audit_action, audit_model_changes, audit_sensitive_data_access
from .forms import DashboardUserCreationForm, TicketCreateForm
from .views_helpers import get_role_filtered_tickets, user_can_access_ticket

logger = logging.getLogger('dashboard')

from .models import PontoDeVenda
from django import forms

# Formulário para PontoDeVenda
class PontoDeVendaForm(forms.ModelForm):
    class Meta:
        model = PontoDeVenda
        fields = '__all__'
        widgets = {
            'razao_social': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'nome_fantasia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'inscricao_estadual': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'inscricao_municipal': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'cep': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'logradouro': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'numero': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'complemento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'bairro': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'cidade': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'estado': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'pais': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'celular': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'email_principal': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'email_financeiro': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'responsavel_nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'responsavel_cpf': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'responsavel_cargo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'responsavel_telefone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '}),
            'responsavel_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': ' '}),
        }

@method_decorator([login_required], name='dispatch')
class PontoDeVendaListView(ListView):
    model = PontoDeVenda
    template_name = 'dashboard/pontodevenda_list.html'
    context_object_name = 'pontosdevenda'
    paginate_by = 25

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, 'Acesso negado. Você não tem permissão para ver pontos de venda.')
            return redirect('dashboard:index')
        return super().dispatch(request, *args, **kwargs)

@method_decorator([login_required], name='dispatch')
class PontoDeVendaCreateView(CreateView):
    model = PontoDeVenda
    form_class = PontoDeVendaForm
    template_name = 'dashboard/pontodevenda_form.html'
    success_url = reverse_lazy('dashboard:pontodevenda_list')

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, 'Acesso negado. Você não tem permissão para criar pontos de venda.')
            return redirect('dashboard:index')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        obj = form.save()
        messages.success(self.request, f'Ponto de Venda "{obj.nome_fantasia}" cadastrado com sucesso.')
        return super().form_valid(form)

@method_decorator([login_required], name='dispatch')
class PontoDeVendaDetailView(DetailView):
    model = PontoDeVenda
    template_name = 'dashboard/pontodevenda_detail.html'
    context_object_name = 'object'

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, 'Acesso negado. Você não tem permissão para ver detalhes de pontos de venda.')
            return redirect('dashboard:pontodevenda_list')
        return super().dispatch(request, *args, **kwargs)

@method_decorator([login_required], name='dispatch')
class PontoDeVendaUpdateView(UpdateView):
    model = PontoDeVenda
    form_class = PontoDeVendaForm
    template_name = 'dashboard/pontodevenda_form.html'
    success_url = reverse_lazy('dashboard:pontodevenda_list')

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, 'Acesso negado. Você não tem permissão para editar pontos de venda.')
            return redirect('dashboard:pontodevenda_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        obj = form.save()
        messages.success(self.request, f'Ponto de Venda "{obj.nome_fantasia}" atualizado com sucesso.')
        return super().form_valid(form)

User = get_user_model()

@method_decorator([login_required], name='dispatch')
class UserListView(ListView):
    model = User
    template_name = 'dashboard/user_list.html'
    context_object_name = 'users'
    paginate_by = 25
    ordering = ['-date_joined']

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, 'Acesso negado. Você não tem permissão para ver usuários.')
            return redirect('dashboard:index')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_users = User.objects.all()
        context['total_users'] = all_users.count()
        context['active_users'] = all_users.filter(is_active=True).count()
        context['staff_users'] = all_users.filter(is_staff=True).count()
        context['admin_users'] = all_users.filter(is_superuser=True).count()
        return context


@method_decorator([login_required], name='dispatch')
class UserCreateView(CreateView):
    model = User
    template_name = 'dashboard/user_form.html'
    form_class = DashboardUserCreationForm
    success_url = reverse_lazy('dashboard:user_list')

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, 'Acesso negado. Você não tem permissão para criar usuários.')
            return redirect('dashboard:index')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        messages.success(self.request, f'Usuário {user.username} criado com sucesso.')
        return super().form_valid(form)

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
        except Exception:
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
    
    import json
    from datetime import timedelta
    from django.db.models import Count, Q
    from django.utils import timezone
    
    # Estatísticas gerais do sistema
    total_usuarios = User.objects.count()
    total_clientes = Cliente.objects.count()
    total_tickets = Ticket.objects.count()
    total_categorias = CategoriaTicket.objects.count()
    
    # Tickets por status (otimizado com uma query)
    ticket_stats = Ticket.objects.aggregate(
        abertos=Count('id', filter=Q(status='aberto')),
        andamento=Count('id', filter=Q(status='em_andamento')),
        resolvidos=Count('id', filter=Q(status='resolvido')),
        fechados=Count('id', filter=Q(status='fechado')),
        alta=Count('id', filter=Q(prioridade='alta')),
        media=Count('id', filter=Q(prioridade='media')),
        baixa=Count('id', filter=Q(prioridade='baixa'))
    )
    
    tickets_abertos = ticket_stats['abertos']
    tickets_andamento = ticket_stats['andamento']
    tickets_resolvidos = ticket_stats['resolvidos']
    tickets_fechados = ticket_stats['fechados']
    tickets_alta = ticket_stats['alta']
    tickets_media = ticket_stats['media']
    tickets_baixa = ticket_stats['baixa']
    
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
        tendencia_labels.append(dia.strftime('%d/%m'))
        tendencia_criados.append(
            Ticket.objects.filter(criado_em__date=dia).count()
        )
        tendencia_fechados.append(
            Ticket.objects.filter(
                Q(status__in=['resolvido', 'fechado']),
                Q(atualizado_em__date=dia)
            ).count()
        )
    
    # Tickets recentes com otimização
    tickets_recentes = Ticket.objects.select_related(
        'cliente', 'categoria', 'agente', 'sla_policy'
    ).order_by('-criado_em')[:10]
    
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
        'usuarios_ativos_24h': usuarios_ativos_24h,
        'taxa_resolucao': taxa_resolucao,
        'tendencia_labels': json.dumps(tendencia_labels),
        'tendencia_criados': json.dumps(tendencia_criados),
        'tendencia_fechados': json.dumps(tendencia_fechados),
    }
    
    return render(request, 'dashboard/admin/dashboard.html', context)

# ========== VIEWS DE AUTENTICAÇÃO ==========

def custom_login(request):
    """
    View personalizada para login com template customizado
    """
    from .forms import CustomLoginForm
    
    if request.user.is_authenticated:
        # Se já estiver logado, redireciona para dashboard
        return redirect('dashboard:index')
    
    form = CustomLoginForm()
    
    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Bem-vindo, {user.get_full_name() or user.username}!')
            
            # Redireciona baseado no tipo de usuário
            next_url = request.GET.get('next')
            if next_url:
                from django.utils.http import url_has_allowed_host_and_scheme
                if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                    return redirect(next_url)
            return redirect('dashboard:index')
        else:
            messages.error(request, 'Nome de usuário ou senha incorretos.')
    
    return render(request, 'registration/login.html', {'form': form})

def custom_logout(request):
    """
    View personalizada para logout
    """
    if request.user.is_authenticated:
        username = request.user.get_full_name() or request.user.username
        logout(request)
        messages.success(request, f'Até logo, {username}! Logout realizado com sucesso.')
    else:
        logout(request)
    return redirect('login')

@login_required
@rate_limit(max_requests=60, window_seconds=3600)  # 60 requests per hour
@log_suspicious_activity
@api_version(supported_versions=['v1', 'v2'])
def get_user_info(request):
    """
    API para informações do usuário logado
    Suporta versões v1 e v2 com diferentes formatos de resposta
    """
    user_data = {
        'id': request.user.id,
        'username': request.user.username,
        'full_name': request.user.get_full_name(),
        'first_name': request.user.first_name,
        'last_name': request.user.last_name,
        'email': request.user.email,
        'is_superuser': request.user.is_superuser,
        'is_staff': request.user.is_staff,
        'is_active': request.user.is_active,
        'user_type': 'admin' if request.user.is_superuser else 'user',
        'date_joined': request.user.date_joined.isoformat() if request.user.date_joined else None,
        'last_login': request.user.last_login.isoformat() if request.user.last_login else None,
    }
    
    # Transformar dados baseado na versão da API
    version = getattr(request, 'api_version', 'v2')
    transformed_data = APIResponseTransformer.transform_user_data(user_data, version)
    
    return JsonResponse(transformed_data)

@method_decorator(login_required, name='dispatch')
class DashboardView(TemplateView):
    template_name = 'dashboard/index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # === IMPORTAÇÕES ===
        from django.utils import timezone
        from datetime import timedelta, datetime
        from django.db.models import Count, Q, Avg, F, ExpressionWrapper, DurationField
        from django.db.models.functions import TruncDate, TruncHour, TruncMonth, ExtractWeekDay, ExtractHour
        import json
        
        now = timezone.now()
        hoje = now.date()
        ontem = hoje - timedelta(days=1)
        mes_atual = hoje.replace(day=1)
        doze_meses_atras = (now - timedelta(days=365)).replace(day=1)
        
        # 1. Tickets por mês (últimos 12 meses) — UMA query com TruncMonth
        tickets_por_mes_qs = (
            Ticket.objects.filter(criado_em__gte=doze_meses_atras)
            .annotate(mes=TruncMonth('criado_em'))
            .values('mes')
            .annotate(count=Count('id'))
            .order_by('mes')
        )
        # Montar dicionário mês -> count
        mes_dict = {item['mes'].date(): item['count'] for item in tickets_por_mes_qs}
        tickets_por_mes = []
        for i in range(12):
            year = now.year
            month = now.month - i
            while month <= 0:
                month += 12
                year -= 1
            dt = datetime(year, month, 1).date()
            tickets_por_mes.insert(0, mes_dict.get(dt, 0))
        
        # 2. Distribuição por status (UMA query com aggregate + conditional)
        status_data = Ticket.objects.aggregate(
            aberto=Count('id', filter=Q(status=StatusTicket.ABERTO)),
            em_andamento=Count('id', filter=Q(status=StatusTicket.EM_ANDAMENTO)),
            resolvido=Count('id', filter=Q(status=StatusTicket.RESOLVIDO)),
            fechado=Count('id', filter=Q(status=StatusTicket.FECHADO))
        )
        
        # 3. Performance por agente (UMA query com annotate)
        agent_performance = list(
            Ticket.objects.filter(
                status=StatusTicket.RESOLVIDO,
                agente__is_staff=True
            ).values('agente__username', 'agente__first_name').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
        )
        
        # 4. Heatmap de horários — UMA query com ExtractWeekDay + ExtractHour
        heatmap_qs = (
            Ticket.objects
            .annotate(dia=ExtractWeekDay('criado_em'), hora=ExtractHour('criado_em'))
            .values('dia', 'hora')
            .annotate(count=Count('id'))
        )
        heatmap_lookup = {}
        for item in heatmap_qs:
            heatmap_lookup[(item['dia'], item['hora'])] = item['count']
        
        heatmap_data = []
        for dia in range(7):
            linha = []
            for hora in range(0, 24, 2):
                total = sum(
                    heatmap_lookup.get((dia + 1, h), 0) for h in range(hora, hora + 2)
                )
                linha.append(total)
            heatmap_data.append(linha)
        
        # 5. Atendimentos por hora — UMA query
        hora_qs = (
            Ticket.objects
            .annotate(hora=ExtractHour('criado_em'))
            .values('hora')
            .annotate(count=Count('id'))
        )
        hora_dict = {item['hora']: item['count'] for item in hora_qs}
        atendimentos_por_hora = [hora_dict.get(h, 0) for h in range(24)]
        
        context.update({
            'tickets_por_mes': json.dumps(tickets_por_mes),
            'status_data': json.dumps(status_data),
            'agent_performance': json.dumps(agent_performance),
            'heatmap_data': json.dumps(heatmap_data),
            'atendimentos_por_hora': json.dumps(atendimentos_por_hora),
        })
        
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
        
        # Tickets abertos
        tickets_abertos = Ticket.objects.filter(
            status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO]
        ).count()
        
        # Taxa de resolução
        tickets_mes = Ticket.objects.filter(criado_em__gte=mes_atual)
        total_mes = tickets_mes.count()
        resolvidos_mes = tickets_mes.filter(
            status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO]
        ).count()
        taxa_resolucao = (resolvidos_mes / total_mes * 100) if total_mes > 0 else 0
        
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
            'cliente'
        ).order_by('-criado_em')[:10]
        
        # Agentes status (busca real do banco)
        try:
            from dashboard.models import PerfilAgente
            agentes_qs = PerfilAgente.objects.select_related('user').filter(
                user__is_active=True
            )[:10]
            context['agentes_status'] = agentes_qs
        except Exception:
            context['agentes_status'] = []
        
        # Dados para gráficos (em formato JSON-ready) são gerados acima
        
        # Dados legados mantidos para compatibilidade
        context['total_clientes'] = Cliente.objects.count()
        context['tickets_fechados'] = resolvidos_mes
        context['total_tickets'] = Ticket.objects.count()
        
        # === SLA Dados dinâmicos ===
        try:
            from dashboard.models import SLAPolicy, SLAAlert
            context['sla_policies_count'] = SLAPolicy.objects.filter(is_active=True).count()
            context['sla_alerts_count'] = SLAAlert.objects.filter(resolved_at__isnull=True).count()
        except Exception:
            context['sla_policies_count'] = 0
            context['sla_alerts_count'] = 0
        
        # === WhatsApp status dinâmico ===
        try:
            from dashboard.models_whatsapp import WhatsAppBusinessAccount
            whatsapp_ativo = WhatsAppBusinessAccount.objects.filter(ativo=True).exists()
            context['whatsapp_status'] = 'Conectado' if whatsapp_ativo else 'Desconectado'
        except Exception:
            context['whatsapp_status'] = 'Desconectado'
        
        # === Variações percentuais reais ===
        # Variação de usuários ativos (mês atual vs mês anterior)
        inicio_mes_passado = (mes_atual - timedelta(days=1)).replace(day=1)
        usuarios_mes_passado = User.objects.filter(
            last_login__gte=inicio_mes_passado,
            last_login__lt=mes_atual
        ).count()
        if usuarios_mes_passado > 0:
            context['variacao_usuarios'] = round(((usuarios_ativos - usuarios_mes_passado) / usuarios_mes_passado) * 100, 1)
        else:
            context['variacao_usuarios'] = 100 if usuarios_ativos > 0 else 0
        
        # Variação de tickets abertos (semana atual vs semana passada)
        semana_passada_inicio = hoje - timedelta(days=14)
        semana_passada_fim = hoje - timedelta(days=7)
        tickets_semana_passada = Ticket.objects.filter(
            criado_em__date__gte=semana_passada_inicio,
            criado_em__date__lt=semana_passada_fim,
            status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO]
        ).count()
        if tickets_semana_passada > 0:
            context['variacao_tickets'] = round(((tickets_abertos - tickets_semana_passada) / tickets_semana_passada) * 100, 1)
        else:
            context['variacao_tickets'] = 0
        
        # Variação da taxa de resolução (mês atual vs mês anterior)
        tickets_mes_passado = Ticket.objects.filter(
            criado_em__gte=inicio_mes_passado,
            criado_em__lt=mes_atual
        )
        total_mes_passado = tickets_mes_passado.count()
        resolvidos_mes_passado = tickets_mes_passado.filter(
            status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO]
        ).count()
        taxa_resolucao_passada = (resolvidos_mes_passado / total_mes_passado * 100) if total_mes_passado > 0 else 0
        context['variacao_resolucao'] = round(taxa_resolucao - taxa_resolucao_passada, 1)
        
        # === Tendência de tickets (últimos 30 dias vs 30 dias anteriores) ===
        trinta_dias = hoje - timedelta(days=30)
        sessenta_dias = hoje - timedelta(days=60)
        tickets_30d = Ticket.objects.filter(criado_em__date__gte=trinta_dias).count()
        tickets_60_30d = Ticket.objects.filter(
            criado_em__date__gte=sessenta_dias,
            criado_em__date__lt=trinta_dias
        ).count()
        if tickets_60_30d > 0:
            context['tendencia_tickets'] = round(((tickets_30d - tickets_60_30d) / tickets_60_30d) * 100, 1)
        else:
            context['tendencia_tickets'] = 100 if tickets_30d > 0 else 0
        
        # === Resumo mensal (tickets resolvidos este mês vs mês passado) ===
        if total_mes_passado > 0:
            context['resumo_mensal_pct'] = round(((total_mes - total_mes_passado) / total_mes_passado) * 100, 1)
        else:
            context['resumo_mensal_pct'] = 100 if total_mes > 0 else 0
        
        # === Tickets recentes para timeline ===
        context['tickets_timeline'] = Ticket.objects.select_related(
            'cliente', 'agente'
        ).order_by('-criado_em')[:3]
        
        # === Labels de meses dinâmicos para gráficos ===
        meses_labels = []
        for i in range(11, -1, -1):
            year = now.year
            month = now.month - i
            while month <= 0:
                month += 12
                year -= 1
            dt = datetime(year, month, 1)
            meses_labels.append(dt.strftime('%b'))
        context['meses_labels'] = json.dumps(meses_labels)
        
        # === NOVO: Tempo Médio de Resolução ===
        tempo_medio_qs = Ticket.objects.filter(
            status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO],
            resolvido_em__isnull=False,
            criado_em__isnull=False,
        ).annotate(
            duracao=ExpressionWrapper(
                F('resolvido_em') - F('criado_em'),
                output_field=DurationField()
            )
        ).aggregate(media=Avg('duracao'))
        
        tempo_medio = tempo_medio_qs.get('media')
        if tempo_medio:
            total_seconds = int(tempo_medio.total_seconds())
            hours = total_seconds // 3600
            if hours >= 24:
                days = hours // 24
                context['tempo_medio_resolucao'] = f'{days}d {hours % 24}h'
            else:
                minutes = (total_seconds % 3600) // 60
                context['tempo_medio_resolucao'] = f'{hours}h {minutes}m'
        else:
            context['tempo_medio_resolucao'] = '--'
        
        # Variação do tempo médio vs mês anterior
        tempo_medio_atual_qs = Ticket.objects.filter(
            status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO],
            resolvido_em__isnull=False,
            resolvido_em__gte=mes_atual,
        ).annotate(
            duracao=ExpressionWrapper(F('resolvido_em') - F('criado_em'), output_field=DurationField())
        ).aggregate(media=Avg('duracao'))
        
        tempo_medio_passado_qs = Ticket.objects.filter(
            status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO],
            resolvido_em__isnull=False,
            resolvido_em__gte=inicio_mes_passado,
            resolvido_em__lt=mes_atual,
        ).annotate(
            duracao=ExpressionWrapper(F('resolvido_em') - F('criado_em'), output_field=DurationField())
        ).aggregate(media=Avg('duracao'))
        
        tm_atual = tempo_medio_atual_qs.get('media')
        tm_passado = tempo_medio_passado_qs.get('media')
        if tm_atual and tm_passado and tm_passado.total_seconds() > 0:
            context['variacao_tempo_medio'] = round(
                ((tm_atual.total_seconds() - tm_passado.total_seconds()) / tm_passado.total_seconds()) * 100, 1
            )
        else:
            context['variacao_tempo_medio'] = 0
        
        # === NOVO: Tickets Urgentes (SLA expirado ou prioridade crítica aberto) ===
        tickets_urgentes = list(Ticket.objects.filter(
            Q(prioridade='critica', status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO]) |
            Q(sla_resolution_deadline__lt=now, status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO]) |
            Q(is_escalated=True, status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO])
        ).select_related('cliente', 'agente', 'categoria').distinct().order_by('-criado_em')[:10])
        context['tickets_urgentes'] = tickets_urgentes
        
        # === NOVO: Agentes Online ===
        try:
            from dashboard.models import PerfilAgente
            context['agentes_online'] = PerfilAgente.objects.filter(status='online').count()
        except Exception:
            context['agentes_online'] = 0
        
        return context


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
            ('pendente', 'Pendente', 'secondary'),
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
        from django.db.models import Avg, F, ExpressionWrapper, DurationField
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
        from datetime import timedelta
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
        # RBAC: filtrar tickets por papel do usuário (previne IDOR)
        return get_role_filtered_tickets(self.request.user, base_qs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['interacoes'] = self.object.interacoes.all().order_by('criado_em')
        context['anexos'] = self.object.anexos.all() if hasattr(self.object, 'anexos') else []
        context['status_choices'] = StatusTicket.choices
        # Total de tickets do mesmo cliente
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
            
        response = super().form_valid(form)
        
        # Processar produtos e serviços (se enviados)
        produtos_dados = self.request.POST.get('produtos_dados')
        if produtos_dados:
            try:
                import json
                from decimal import Decimal
                from .models import ItemAtendimento
                from .models_estoque import Produto
                
                itens = json.loads(produtos_dados)
                
                for item in itens:
                    produto_id = item['produto']['id']
                    quantidade = Decimal(str(item['quantidade']))
                    valor_unitario = Decimal(str(item['valorUnitario']))
                    desconto_percentual = Decimal(str(item['descontoPercentual']))
                    observacoes = item.get('observacoes', '')
                    tipo_item = item['produto']['tipo']
                    
                    # Buscar o produto
                    try:
                        produto = Produto.objects.get(id=produto_id)
                        
                        # Criar item de atendimento
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
                        # Log do produto não encontrado, mas não interrompe o processo
                        logger.warning("Produto ID %s nao encontrado", produto_id)
                        continue
                        
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                # Log do erro, mas não interrompe a criação do ticket
                logger.error("Erro ao processar produtos: %s", e, exc_info=True)
        
        # Processar anexos
        if 'anexos' in self.request.FILES:
            from .security import validate_file_upload
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
    fields = ['categoria', 'titulo', 'descricao', 'status', 'prioridade', 'agente']
    
    def get_queryset(self):
        base_qs = Ticket.objects.all()
        # RBAC: filtrar tickets por papel do usuário (previne IDOR)
        return get_role_filtered_tickets(self.request.user, base_qs)
    
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
        
        # RBAC: verificar se o usuário tem acesso ao ticket
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
        context['tickets_recentes'] = tickets_agente.select_related('cliente', 'categoria').order_by('-atualizado_em')[:5]
        
        # Status do agente - criar perfil se não existir
        try:
            perfil_agente = PerfilAgente.objects.get(user=user)
            context['status_agente'] = perfil_agente.status
        except PerfilAgente.DoesNotExist:
            # Criar perfil automaticamente para agentes
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


# ========== PORTAL DO CLIENTE ==========

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


@method_decorator(login_required, name='dispatch')
class ClientePortalView(TemplateView):
    template_name = 'dashboard/cliente/portal.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_admin = user.is_staff or user.is_superuser
        context['is_admin'] = is_admin
        
        if is_admin:
            # Admin vê visão geral de TODOS os clientes
            clientes = Cliente.objects.all()
            all_tickets = Ticket.objects.filter(cliente__isnull=False)
            
            context['cliente'] = True  # flag para template não mostrar "Acesso Restrito"
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
            
            # Top clientes por tickets
            context['top_clientes'] = Cliente.objects.annotate(
                num_tickets=Count('tickets')
            ).order_by('-num_tickets')[:10]
        else:
            # Usuário normal: buscar pelo email
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
        
        # Aplicar filtros
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
            num_tickets=Count('tickets'),
            tickets_abertos=Count('tickets', filter=Q(tickets__status='aberto')),
            tickets_andamento=Count('tickets', filter=Q(tickets__status='em_andamento')),
        ).order_by('-criado_em')
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nome__icontains=search) |
                Q(email__icontains=search) |
                Q(empresa__icontains=search) |
                Q(telefone__icontains=search)
            )
        
        empresa = self.request.GET.get('empresa')
        if empresa:
            queryset = queryset.filter(empresa__icontains=empresa)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_clientes'] = Cliente.objects.count()
        context['clientes_com_tickets'] = Cliente.objects.filter(tickets__isnull=False).distinct().count()
        context['empresas'] = Cliente.objects.exclude(empresa='').values_list('empresa', flat=True).distinct().order_by('empresa')
        context['search'] = self.request.GET.get('search', '')
        context['empresa_selected'] = self.request.GET.get('empresa', '')
        return context


from .forms import ClienteForm

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


# ========== APIs AJAX ==========

@login_required
@rate_limit(max_requests=120, window_seconds=3600)
def cliente_stats_ajax(request):
    """
    API para estatísticas do cliente em tempo real
    Retorna sempre formato v1 (flat) compatível com o template
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
            
            # Verificação de permissão: usuário deve ser staff ou agente atribuído
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
            
            # Log da alteração
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


@login_required
@rate_limit(max_requests=30, window_seconds=3600)  # 30 agent status updates per hour
@log_suspicious_activity("Agent status update")
def update_agent_status(request):
    """API para atualizar status do agente"""
    logger.debug("update_agent_status called by %s, method: %s", request.user.username, request.method)
    
    if request.method == 'POST':
        new_status = request.POST.get('status', '').lower().strip()
        logger.debug("Novo status solicitado: '%s'", new_status)
        
        # Validar status
        valid_statuses = ['online', 'ocupado', 'ausente', 'offline']
        if new_status not in valid_statuses:
            return JsonResponse({
                'success': False,
                'message': f'Status inválido. Use: {", ".join(valid_statuses)}'
            })
        
        try:
            # Criar ou atualizar perfil do agente
            perfil_agente, created = PerfilAgente.objects.get_or_create(
                user=request.user,
                defaults={'status': new_status}
            )
            if not created:
                perfil_agente.status = new_status
                perfil_agente.save()
            
            # Log da mudança de status
            logger.info('Agente %s mudou status para %s', request.user.username, new_status)
            
            return JsonResponse({
                'success': True,
                'message': f'Status alterado para {perfil_agente.get_status_display()}',
                'new_status': perfil_agente.get_status_display(),
                'status_value': new_status
            })
        except Exception as e:
            logger.error('Erro ao atualizar status do agente %s: %s', request.user.username, str(e), exc_info=True)
            
            return JsonResponse({
                'success': False,
                'message': f'Erro interno do servidor'
            })
    
    return JsonResponse({'success': False, 'message': 'Método não permitido!'})

@method_decorator(login_required, name='dispatch')
class ProfileView(TemplateView):
    template_name = 'dashboard/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Busca ou cria o perfil do usuário
        perfil, created = PerfilUsuario.objects.get_or_create(
            user=user,
            defaults={'telefone': ''}
        )
        context['perfil'] = perfil

        # Estatísticas do usuário
        from django.db.models import Q
        user_tickets = Ticket.objects.filter(
            Q(agente=user) | Q(cliente__user=user) if hasattr(user, 'cliente') else Q(agente=user)
        )
        context['user_stats'] = {
            'ocorrencias': user_tickets.filter(prioridade__in=['critica', 'alta']).count(),
            'chamados': user_tickets.count(),
            'atendimentos': user_tickets.filter(status__in=['resolvido', 'fechado']).count(),
        }

        # Atividades recentes (últimas interações do usuário)
        recent = InteracaoTicket.objects.filter(
            usuario=user
        ).select_related('ticket').order_by('-criado_em')[:5]

        activities = []
        color_map = {
            'resposta': 'info', 'nota_interna': 'warning',
            'sistema': 'secondary', 'status_change': 'success',
        }
        for interaction in recent:
            msg_preview = interaction.mensagem
            if len(msg_preview) > 80:
                msg_preview = msg_preview[:80] + '...'
            activities.append({
                'title': f'Ticket #{interaction.ticket.numero}',
                'description': msg_preview,
                'created_at': interaction.criado_em,
                'color': color_map.get(interaction.tipo, 'primary'),
            })
        context['recent_activities'] = activities

        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action', 'update_profile')

        if action == 'change_password':
            return self._handle_password_change(request)

        return self._handle_profile_update(request)

    def _handle_password_change(self, request):
        """Processa a troca de senha"""
        from django.contrib.auth import update_session_auth_hash

        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not current_password:
            messages.error(request, 'Informe sua senha atual.')
            return redirect('dashboard:profile')

        if not request.user.check_password(current_password):
            messages.error(request, 'Senha atual incorreta.')
            return redirect('dashboard:profile')

        if not new_password or len(new_password) < 8:
            messages.error(request, 'A nova senha deve ter pelo menos 8 caracteres.')
            return redirect('dashboard:profile')

        if new_password != confirm_password:
            messages.error(request, 'As senhas nao coincidem.')
            return redirect('dashboard:profile')

        # Validar senha com os validators do Django
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        try:
            validate_password(new_password, request.user)
        except ValidationError as e:
            for error in e.messages:
                messages.error(request, error)
            return redirect('dashboard:profile')

        request.user.set_password(new_password)
        request.user.save()
        update_session_auth_hash(request, request.user)
        messages.success(request, 'Senha alterada com sucesso!')
        return redirect('dashboard:profile')

    def _handle_profile_update(self, request):
        """Processa a atualização do perfil"""
        try:
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
            perfil.telefone_alternativo = request.POST.get('telefone_alternativo', '')
            perfil.endereco = request.POST.get('endereco', '')
            perfil.cidade = request.POST.get('cidade', '')
            perfil.estado = request.POST.get('estado', '')
            perfil.cep = request.POST.get('cep', '')
            perfil.cargo = request.POST.get('cargo', '')
            perfil.departamento = request.POST.get('departamento', '')
            perfil.bio = request.POST.get('bio', '')

            # Processa upload de avatar com validação
            if 'avatar' in request.FILES:
                from .security import validate_file_upload
                is_valid, error_msg = validate_file_upload(request.FILES['avatar'])
                if is_valid:
                    perfil.avatar = request.FILES['avatar']
                else:
                    messages.warning(request, f'Avatar rejeitado: {error_msg}')

            perfil.save()

            messages.success(request, 'Perfil atualizado com sucesso!')

        except Exception as e:
            logger.error(f'Erro ao atualizar perfil: {e}')
            messages.error(request, 'Erro ao atualizar perfil. Tente novamente.')

        return redirect('dashboard:profile')


# ========== VIEWS DE MÉTRICAS E AJAX ==========

@login_required
@rate_limit(max_requests=100, window_seconds=3600)  # 100 metrics requests per hour
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
                status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO]
            ).count()
            
            # Taxa de resolução
            mes_atual = hoje.replace(day=1)
            tickets_mes = Ticket.objects.filter(criado_em__gte=mes_atual)
            total_mes = tickets_mes.count()
            resolvidos_mes = tickets_mes.filter(
                status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO]
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
            logger.error(f'Erro em ajax_metrics: {e}', exc_info=True)
            return JsonResponse({'error': 'Erro interno ao processar métricas.'}, status=500)
    
    return JsonResponse({'error': 'Método não permitido'}, status=405)


@login_required
def export_tickets(request):
    """
    View para exportar dados dos tickets (somente staff).
    """
    if not request.user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('Sem permissão para exportar dados.')
    from django.http import HttpResponse
    import csv
    from datetime import datetime
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="tickets_{datetime.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Número', 'Cliente', 'Status', 'Data Criação', 'Categoria'])
    
    # Buscar tickets do banco de dados
    tickets = Ticket.objects.select_related('cliente', 'categoria').only(
        'id', 'numero', 'cliente__nome', 'status', 'criado_em', 'categoria__nome'
    )[:1000]
    
    for ticket in tickets:
        writer.writerow([
            ticket.id,
            ticket.numero,
            ticket.cliente.nome if ticket.cliente else 'N/A',
            ticket.get_status_display() if hasattr(ticket, 'get_status_display') else ticket.status,
            ticket.criado_em.strftime('%d/%m/%Y %H:%M'),
            ticket.categoria.nome if ticket.categoria else 'N/A',
        ])
    
    return response

# ========== FUNCIONALIDADES AVANÇADAS ==========

# @login_required
# def analytics_dashboard(request):
#     """Dashboard de Analytics Avançados - DESABILITADO: Integrado ao dashboard principal"""
#     from django.utils import timezone
#     from datetime import timedelta, datetime
#     from django.db.models import Count, Avg, Q
#     from django.db.models.functions import TruncDate, TruncHour
#     
#     # Obter dados dos últimos 30 dias
#     thirty_days_ago = timezone.now() - timedelta(days=30)
#     seven_days_ago = timezone.now() - timedelta(days=7)
#     
#     # Estatísticas gerais
#     total_tickets = Ticket.objects.count()
#     tickets_last_month = Ticket.objects.filter(criado_em__gte=thirty_days_ago).count()
#     active_agents = User.objects.filter(is_staff=True, is_active=True).count()
#     
#     # Tickets por status
#     tickets_por_status = {
#         'aberto': Ticket.objects.filter(status=StatusTicket.ABERTO).count(),
#         'em_andamento': Ticket.objects.filter(status=StatusTicket.EM_ANDAMENTO).count(),
#         'resolvido': Ticket.objects.filter(status=StatusTicket.RESOLVIDO).count(),
#         'fechado': Ticket.objects.filter(status=StatusTicket.FECHADO).count(),
#     }
#     
#     # Tickets ao longo do tempo (últimos 7 dias)
#     tickets_timeline = []
#     for i in range(7):
#         date = timezone.now().date() - timedelta(days=6-i)
#         count = Ticket.objects.filter(criado_em__date=date).count()
#         tickets_timeline.append({
#             'date': date.strftime('%d/%m'),
#             'count': count
#         })
#     
#     # Performance por agente
#     agentes_performance = User.objects.filter(
#         is_staff=True, 
#         tickets_agente__isnull=False
#     ).annotate(
#         tickets_resolvidos=Count('tickets_agente', filter=Q(tickets_agente__status=StatusTicket.RESOLVIDO))
#     ).values('first_name', 'last_name', 'tickets_resolvidos')[:5]
#     
#     # Horários de maior demanda (por hora do dia)
#     horarios_demanda = []
#     for hour in range(24):
#         count = Ticket.objects.filter(criado_em__hour=hour).count()
#         horarios_demanda.append({
#             'hour': f'{hour:02d}:00',
#             'count': count
#         })
#     
#     context = {
#         'title': 'Analytics Dashboard',
#         'current_page': 'analytics',
#         'total_tickets': total_tickets,
#         'active_agents': active_agents,
#         'tickets_por_status': tickets_por_status,
#         'tickets_timeline': tickets_timeline,
#         'agentes_performance': list(agentes_performance),
#         'horarios_demanda': horarios_demanda,
#     }
#     
#     return render(request, 'dashboard/analytics/dashboard.html', context)

# @login_required
# def analytics_data_view(request):
#     """Endpoint para dados do analytics - DESABILITADO: Integrado ao dashboard principal"""
#     from .views_helpers import get_dashboard_metrics
#     data = get_dashboard_metrics()
#     return JsonResponse(data)

@login_required
def notifications_center(request):
    """Centro de Notificações"""
    return render(request, 'dashboard/notifications/center.html', {
        'title': 'Central de Notificações',
        'current_page': 'notifications'
    })

@login_required
def mark_notification_read(request, notification_id):
    """Marcar notificação como lida"""
    return JsonResponse({'status': 'success'})

@login_required
def chatbot_interface(request):
    """Interface do Chatbot AI"""
    return render(request, 'dashboard/chatbot/interface.html', {
        'title': 'Chatbot AI - iConnect',
        'current_page': 'chatbot'
    })

@login_required
def chatbot_api(request):
    """API do Chatbot"""
    if request.method == 'POST':
        import json
        from .chatbot_service import ChatbotService
        
        try:
            data = json.loads(request.body)
            message = data.get('message', '')
            
            chatbot = ChatbotService()
            response = chatbot.process_message(request.user.id, message)
            
            return JsonResponse({
                'response': response.message,
                'suggestions': response.suggestions,
                'type': response.response_type
            })
        except Exception as e:
            logger.error(f'Erro no chatbot_api: {e}', exc_info=True)
            return JsonResponse({'error': 'Erro interno.'}, status=500)
    
    return JsonResponse({'error': 'Método não permitido'}, status=405)

@login_required
def chat_interface(request):
    """Interface de Chat em Tempo Real"""
    return render(request, 'dashboard/chat/interface.html', {
        'title': 'Chat - iConnect',
        'current_page': 'chat'
    })

@login_required
def automation_dashboard(request):
    """Dashboard do Sistema de Automação"""
    from .models import WorkflowRule, WorkflowExecution
    
    # Handle POST: ativar template
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            if data.get('action') == 'activate_template':
                tpl = data.get('template')
                TEMPLATE_CONFIGS = {
                    'auto_assign': {
                        'name': 'Atribuição Automática',
                        'description': 'Distribui tickets automaticamente entre agentes',
                        'trigger_event': 'ticket_created',
                        'conditions': {'has_agent': False},
                        'actions': [{'type': 'assign_agent', 'value': 'auto'}],
                        'priority': 8,
                    },
                    'sla_monitor': {
                        'name': 'Monitoramento de SLA',
                        'description': 'Alerta quando SLA está próximo de ser violado',
                        'trigger_event': 'sla_warning',
                        'conditions': {},
                        'actions': [{'type': 'send_notification', 'value': 'Alerta: SLA prestes a ser violado'}],
                        'priority': 9,
                    },
                    'escalation': {
                        'name': 'Escalação por Prioridade',
                        'description': 'Escala tickets sem resposta por tempo prolongado',
                        'trigger_event': 'ticket_updated',
                        'conditions': {'status': 'aberto', 'time_since_creation': '24h'},
                        'actions': [{'type': 'escalate', 'value': 'supervisor'}, {'type': 'change_priority', 'value': 'alta'}],
                        'priority': 7,
                    },
                    'email_notify': {
                        'name': 'Notificações por E-mail',
                        'description': 'Envia e-mails ao cliente quando há mudanças',
                        'trigger_event': 'status_changed',
                        'conditions': {},
                        'actions': [{'type': 'send_notification', 'value': 'Status do seu ticket foi atualizado'}],
                        'priority': 5,
                    },
                    'auto_resolve': {
                        'name': 'Auto-Resolução',
                        'description': 'Fecha tickets resolvidos após 72h de inatividade',
                        'trigger_event': 'status_changed',
                        'conditions': {'status': 'resolvido', 'time_since_creation': '72h'},
                        'actions': [{'type': 'change_status', 'value': 'fechado'}, {'type': 'add_comment', 'value': 'Ticket fechado automaticamente após 72h sem interação.'}],
                        'priority': 3,
                    },
                }
                if tpl in TEMPLATE_CONFIGS:
                    cfg = TEMPLATE_CONFIGS[tpl]
                    rule, created = WorkflowRule.objects.get_or_create(
                        name=cfg['name'],
                        defaults={
                            'description': cfg['description'],
                            'trigger_event': cfg['trigger_event'],
                            'conditions': cfg['conditions'],
                            'actions': cfg['actions'],
                            'priority': cfg['priority'],
                            'is_active': True,
                        }
                    )
                    if not created and not rule.is_active:
                        rule.is_active = True
                        rule.save()
                    return JsonResponse({'success': True, 'created': created})
                return JsonResponse({'success': False, 'error': 'Template não encontrado'})
        except Exception:
            logger.exception('Erro em automation_dashboard POST')
            return JsonResponse({'success': False, 'error': 'Erro interno do servidor'})
    
    # GET: dashboard data
    active_workflows = WorkflowRule.objects.filter(is_active=True).count()
    all_workflows = WorkflowRule.objects.all()
    total_executions = WorkflowExecution.objects.count()
    failed_executions = WorkflowExecution.objects.filter(success=False).count()
    success_executions = total_executions - failed_executions
    success_rate = round((success_executions / total_executions * 100) if total_executions > 0 else 0)
    recent_executions = WorkflowExecution.objects.select_related('rule', 'ticket').order_by('-created_at')[:10]
    
    # Template status checks
    tpl_names = {
        'tpl_auto_assign': 'Atribuição Automática',
        'tpl_sla_monitor': 'Monitoramento de SLA',
        'tpl_escalation': 'Escalação por Prioridade',
        'tpl_email_notify': 'Notificações por E-mail',
        'tpl_auto_resolve': 'Auto-Resolução',
    }
    tpl_status = {}
    for key, name in tpl_names.items():
        tpl_status[key] = WorkflowRule.objects.filter(name=name, is_active=True).exists()
    
    # Chart data: execuções últimos 7 dias
    from datetime import timedelta
    chart_labels = []
    chart_data = []
    for i in range(6, -1, -1):
        day = timezone.now().date() - timedelta(days=i)
        chart_labels.append(day.strftime('%d/%m'))
        chart_data.append(WorkflowExecution.objects.filter(
            created_at__date=day
        ).count())
    
    context = {
        'title': 'Motor de Automação',
        'current_page': 'automation',
        'active_workflows': active_workflows,
        'total_executions': total_executions,
        'failed_executions': failed_executions,
        'success_executions': success_executions,
        'success_rate': success_rate,
        'workflows': all_workflows,
        'recent_executions': recent_executions,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }
    context.update(tpl_status)
    
    return render(request, 'dashboard/automation/dashboard.html', context)

@login_required
def automation_rules(request):
    """Gerenciamento de Regras de Automação"""
    from .models import WorkflowRule, WorkflowExecution
    
    # POST: CRUD de regras
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'create':
                conditions = data.get('conditions', '{}')
                actions_field = data.get('actions', '[]')
                try:
                    conditions = json.loads(conditions) if isinstance(conditions, str) else conditions
                except json.JSONDecodeError:
                    conditions = {}
                try:
                    actions_field = json.loads(actions_field) if isinstance(actions_field, str) else actions_field
                except json.JSONDecodeError:
                    actions_field = []
                    
                rule = WorkflowRule.objects.create(
                    name=data.get('name', 'Nova Regra'),
                    description=data.get('description', ''),
                    trigger_event=data.get('trigger_event', 'ticket_created'),
                    conditions=conditions,
                    actions=actions_field,
                    priority=int(data.get('priority', 5)),
                    is_active=True,
                )
                return JsonResponse({'success': True, 'id': rule.id, 'message': 'Regra criada com sucesso'})
            
            elif action == 'toggle':
                rule = WorkflowRule.objects.get(id=data.get('rule_id'))
                rule.is_active = not rule.is_active
                rule.save()
                return JsonResponse({'success': True, 'is_active': rule.is_active})
            
            elif action == 'delete':
                WorkflowRule.objects.filter(id=data.get('rule_id')).delete()
                return JsonResponse({'success': True, 'message': 'Regra excluída'})
        except Exception:
            logger.exception('Erro em automation_rules POST')
            return JsonResponse({'success': False, 'error': 'Erro interno do servidor'})
    
    # GET
    rules = WorkflowRule.objects.all().order_by('-priority', 'name')
    total_rules = rules.count()
    active_rules = rules.filter(is_active=True).count()
    inactive_rules = total_rules - active_rules
    total_executions = WorkflowExecution.objects.count()
    
    return render(request, 'dashboard/automation/rules.html', {
        'title': 'Regras de Automação',
        'current_page': 'automation_rules',
        'rules': rules,
        'total_rules': total_rules,
        'active_rules': active_rules,
        'inactive_rules': inactive_rules,
        'total_executions': total_executions,
    })

@login_required
def automation_workflows(request):
    """Gerenciamento de Workflows"""
    from .models import WorkflowRule, WorkflowExecution
    
    # POST: CRUD de workflows
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'create':
                tpl = data.get('template')
                QUICK_TEMPLATES = {
                    'auto_assign_high_priority': {
                        'name': 'Auto-Atribuir Alta Prioridade',
                        'description': 'Atribui automaticamente tickets de alta prioridade ao melhor agente disponível',
                        'trigger_event': 'ticket_created',
                        'conditions': {'priority': 'alta'},
                        'actions': [{'type': 'assign_agent', 'value': 'auto'}, {'type': 'send_notification', 'value': 'Ticket de alta prioridade atribuído'}],
                        'priority': 9,
                    },
                    'escalate_old_tickets': {
                        'name': 'Escalar Tickets Antigos',
                        'description': 'Escala tickets abertos há mais de 48h sem atualização',
                        'trigger_event': 'ticket_updated',
                        'conditions': {'status': 'aberto', 'time_since_creation': '48h'},
                        'actions': [{'type': 'escalate', 'value': 'supervisor'}, {'type': 'change_priority', 'value': 'urgente'}],
                        'priority': 8,
                    },
                    'close_resolved_tickets': {
                        'name': 'Fechar Tickets Resolvidos',
                        'description': 'Fecha automaticamente tickets resolvidos após 48h de inatividade',
                        'trigger_event': 'status_changed',
                        'conditions': {'status': 'resolvido', 'time_since_creation': '48h'},
                        'actions': [{'type': 'change_status', 'value': 'fechado'}, {'type': 'add_comment', 'value': 'Ticket fechado automaticamente.'}],
                        'priority': 4,
                    },
                }
                if tpl and tpl in QUICK_TEMPLATES:
                    cfg = QUICK_TEMPLATES[tpl]
                    rule = WorkflowRule.objects.create(
                        name=cfg['name'],
                        description=cfg['description'],
                        trigger_event=cfg['trigger_event'],
                        conditions=cfg['conditions'],
                        actions=cfg['actions'],
                        priority=cfg['priority'],
                        is_active=True,
                    )
                    return JsonResponse({'success': True, 'id': rule.id, 'message': f'Workflow "{cfg["name"]}" criado'})
                else:
                    # Custom workflow
                    conditions = data.get('conditions', '{}')
                    actions_field = data.get('actions', '[]')
                    try:
                        conditions = json.loads(conditions) if isinstance(conditions, str) else conditions
                    except json.JSONDecodeError:
                        conditions = {}
                    try:
                        actions_field = json.loads(actions_field) if isinstance(actions_field, str) else actions_field
                    except json.JSONDecodeError:
                        actions_field = []
                    rule = WorkflowRule.objects.create(
                        name=data.get('name', 'Novo Workflow'),
                        description=data.get('description', ''),
                        trigger_event=data.get('trigger_event', 'ticket_created'),
                        conditions=conditions,
                        actions=actions_field,
                        priority=int(data.get('priority', 5)),
                        is_active=True,
                    )
                    return JsonResponse({'success': True, 'id': rule.id, 'message': 'Workflow criado com sucesso'})
            
            elif action == 'toggle':
                rule = WorkflowRule.objects.get(id=data.get('workflow_id'))
                rule.is_active = not rule.is_active
                rule.save()
                return JsonResponse({'success': True, 'is_active': rule.is_active})
            
            elif action == 'delete':
                WorkflowRule.objects.filter(id=data.get('workflow_id')).delete()
                return JsonResponse({'success': True, 'message': 'Workflow excluído'})
        except Exception:
            logger.exception('Erro em automation_workflows POST')
            return JsonResponse({'success': False, 'error': 'Erro interno do servidor'})
    
    # GET
    workflows = WorkflowRule.objects.all().order_by('-priority', 'name')
    total_workflows = workflows.count()
    active_workflows = workflows.filter(is_active=True).count()
    total_executions = WorkflowExecution.objects.count()
    success_execs = WorkflowExecution.objects.filter(success=True).count()
    success_rate = round((success_execs / total_executions * 100) if total_executions > 0 else 0)
    
    return render(request, 'dashboard/automation/workflows.html', {
        'title': 'Workflows Automáticos',
        'current_page': 'automation_workflows',
        'workflows': workflows,
        'total_workflows': total_workflows,
        'active_workflows': active_workflows,
        'total_executions': total_executions,
        'success_rate': success_rate,
    })

@login_required
def reports_dashboard(request):
    """Dashboard de Relatórios Avançados"""
    from .models import RelatorioFinanceiro
    
    total_reports = RelatorioFinanceiro.objects.count()
    
    # Relatórios recentes
    relatorios_recentes = RelatorioFinanceiro.objects.order_by('-gerado_em')[:10]
    
    return render(request, 'dashboard/reports/advanced.html', {
        'title': 'Relatórios Avançados',
        'current_page': 'reports',
        'total_reports': total_reports,
        'scheduled_reports': 0,
        'avg_generation_time': 0,
        'data_sources': 0,
        'relatorios_recentes': relatorios_recentes,
    })

@login_required
def generate_report(request):
    """Gerar Relatório Customizado"""
    if request.method == 'POST':
        # Lógica para gerar relatório
        return JsonResponse({'status': 'success', 'report_id': 'temp_123'})
    
    return render(request, 'dashboard/reports/generate.html', {
        'title': 'Gerar Relatório',
        'current_page': 'reports'
    })

@login_required
def download_report(request, report_id):
    """Download de Relatório"""
    from django.http import HttpResponse
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="relatorio_{report_id}.pdf"'
    response.write(b'%PDF-1.4 placeholder')
    return response

@login_required
def custom_reports(request):
    """Relatórios Customizados"""
    return render(request, 'dashboard/reports/custom.html', {
        'title': 'Relatórios Customizados',
        'current_page': 'reports'
    })

@login_required
def advanced_search(request):
    """Busca Avançada"""
    query = request.GET.get('q', '')
    results = []
    
    if query:
        # Implementar busca avançada aqui
        tickets = Ticket.objects.select_related(
            'cliente', 'agente', 'categoria'
        ).filter(
            Q(titulo__icontains=query) |
            Q(descricao__icontains=query) |
            Q(numero__icontains=query)
        )[:20]
        
        results = [
            {
                'id': t.id,
                'title': t.titulo,
                'number': t.numero,
                'type': 'ticket'
            } for t in tickets
        ]
    
    return render(request, 'dashboard/search/advanced.html', {
        'title': 'Busca Avançada',
        'query': query,
        'results': results,
        'current_page': 'search'
    })

@login_required
def search_suggestions(request):
    """Sugestões de Busca"""
    query = request.GET.get('q', '')
    suggestions = []
    
    if len(query) >= 2:
        tickets = Ticket.objects.filter(titulo__icontains=query)[:5]
        suggestions = [t.titulo for t in tickets]
    
    return JsonResponse({'suggestions': suggestions})

@login_required
def pwa_info(request):
    """Informações sobre PWA"""
    return render(request, 'dashboard/pwa/info.html', {
        'title': 'App Progressivo - PWA',
        'current_page': 'pwa'
    })

@login_required
def pwa_install_guide(request):
    """Guia de Instalação PWA"""
    return render(request, 'dashboard/pwa/install.html', {
        'title': 'Como Instalar o App',
        'current_page': 'pwa'
    })

# PWA Service Worker e Manifest
def manifest(request):
    """Manifest do PWA"""
    from django.http import JsonResponse
    
    manifest_data = {
        "name": "iConnect - Sistema de Atendimento",
        "short_name": "iConnect",
        "description": "Sistema completo de atendimento ao cliente",
        "start_url": "/dashboard/",
        "display": "standalone",
        "theme_color": "#334155",
        "background_color": "#f8fafc",
        "icons": [
            {
                "src": "/static/img/icon-192x192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/img/icon-512x512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }
    
    return JsonResponse(manifest_data)

def service_worker(request):
    """Service Worker do PWA"""
    from django.http import HttpResponse
    
    sw_content = """
const CACHE_NAME = 'iconnect-v1.0.0';
const OFFLINE_URL = '/mobile/offline/';

const urlsToCache = [
    '/dashboard/',
    '/static/css/material-dashboard.min.css',
    '/static/js/material-dashboard.min.js',
    OFFLINE_URL
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(urlsToCache))
    );
});

self.addEventListener('fetch', event => {
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request)
                .catch(() => caches.match(OFFLINE_URL))
        );
    }
});
"""
    
    response = HttpResponse(sw_content, content_type='application/javascript')
    return response

@login_required
def tickets_chart_api(request):
    """
    API para filtrar dados do gráfico de tickets por período
    """
    period = request.GET.get('period', '30days')
    
    now = timezone.now()
    
    if period == '7days':
        # Últimos 7 dias
        labels = []
        data = []
        for i in range(7):
            date = now.date() - timedelta(days=i)
            count = Ticket.objects.filter(criado_em__date=date).count()
            labels.insert(0, date.strftime('%d/%m'))
            data.insert(0, count)
            
    elif period == '30days':
        # Últimos 30 dias (agrupado por semana)
        labels = []
        data = []
        for i in range(4):  # 4 semanas
            end_date = now.date() - timedelta(days=i*7)
            start_date = end_date - timedelta(days=6)
            count = Ticket.objects.filter(
                criado_em__date__range=[start_date, end_date]
            ).count()
            labels.insert(0, f'{start_date.strftime("%d/%m")} - {end_date.strftime("%d/%m")}')
            data.insert(0, count)
            
    elif period == '90days':
        # Últimos 90 dias (agrupado por mês)
        labels = []
        data = []
        for i in range(3):  # 3 meses
            year = now.year
            month = now.month - i
            
            # Ajustar para anos anteriores se necessário
            while month <= 0:
                month += 12
                year -= 1
                
            count = Ticket.objects.filter(
                criado_em__year=year,
                criado_em__month=month
            ).count()
            
            month_names = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 
                          'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
            labels.insert(0, f'{month_names[month-1]} {year}')
            data.insert(0, count)
    
    return JsonResponse({
        'labels': labels,
        'data': data
    })


# ========== VIEWS DE API PARA NOTIFICAÇÕES ==========

@login_required
@require_http_methods(["GET"])
def api_notifications_recent(request):
    """
    API para buscar notificações recentes do usuário
    """
    try:
        # Buscar últimas 20 notificações do usuário
        notifications = Notification.objects.filter(
            user=request.user
        ).select_related('ticket').order_by('-created_at')[:20]
        
        # Converter para formato JSON
        notifications_data = []
        for notification in notifications:
            notifications_data.append({
                'id': notification.id,
                'title': notification.title,
                'message': notification.message,
                'type': notification.type,
                'is_read': notification.read,
                'created_at': notification.created_at.isoformat(),
                'ticket_id': notification.ticket.id if notification.ticket else None,
                'ticket_numero': notification.ticket.numero if notification.ticket else None
            })
        
        # Contar não lidas
        unread_count = Notification.objects.filter(
            user=request.user,
            read=False
        ).count()
        
        return JsonResponse({
            'success': True,
            'notifications': notifications_data,
            'unread_count': unread_count
        })
        
    except Exception:
        logger.exception('Erro em api_notifications_recent')
        return JsonResponse({
            'success': False,
            'error': 'Erro interno do servidor'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def api_notification_mark_read(request, notification_id):
    """
    API para marcar uma notificação como lida
    """
    try:
        notification = get_object_or_404(
            Notification, 
            id=notification_id, 
            user=request.user
        )
        
        notification.mark_as_read()
        
        return JsonResponse({
            'success': True,
            'message': 'Notificação marcada como lida'
        })
        
    except Exception:
        logger.exception('Erro em api_notification_mark_read')
        return JsonResponse({
            'success': False,
            'error': 'Erro interno do servidor'
        }, status=500)


@login_required  
@require_http_methods(["POST"])
def api_notifications_mark_all_read(request):
    """
    API para marcar todas as notificações como lidas
    """
    try:
        updated_count = Notification.objects.filter(
            user=request.user,
            read=False
        ).update(
            read=True,
            read_at=timezone.now()
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{updated_count} notificações marcadas como lidas',
            'updated_count': updated_count
        })
        
    except Exception:
        logger.exception('Erro em api_notifications_mark_all_read')
        return JsonResponse({
            'success': False,
            'error': 'Erro interno do servidor'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def api_notification_delete(request, notification_id):
    """
    API para deletar uma notificação
    """
    try:
        notification = get_object_or_404(
            Notification,
            id=notification_id,
            user=request.user
        )
        notification.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Notificação removida'
        })
    except Exception:
        logger.exception('Erro em api_notification_delete')
        return JsonResponse({
            'success': False,
            'error': 'Erro interno do servidor'
        }, status=500)


@login_required
def notifications_list(request):
    """
    Página completa de notificações
    """
    # Filtros
    filter_type = request.GET.get('type', '')
    filter_read = request.GET.get('read', '')
    filter_period = request.GET.get('period', '')
    search_query = request.GET.get('search', '')
    
    notifications = Notification.objects.filter(user=request.user)
    
    # Filtro por tipo
    if filter_type:
        notifications = notifications.filter(type=filter_type)
    
    # Filtro por status de leitura
    if filter_read == 'unread':
        notifications = notifications.filter(read=False)
    elif filter_read == 'read':
        notifications = notifications.filter(read=True)
    
    # Filtro por período
    if filter_period == 'today':
        notifications = notifications.filter(created_at__date=timezone.now().date())
    elif filter_period == 'week':
        week_ago = timezone.now() - timedelta(days=7)
        notifications = notifications.filter(created_at__gte=week_ago)
    elif filter_period == 'month':
        month_ago = timezone.now() - timedelta(days=30)
        notifications = notifications.filter(created_at__gte=month_ago)
    
    # Busca por texto
    if search_query:
        from django.db.models import Q
        notifications = notifications.filter(
            Q(title__icontains=search_query) |
            Q(message__icontains=search_query) |
            Q(type__icontains=search_query)
        )
    
    notifications = notifications.select_related('ticket').order_by('-created_at')
    
    # Paginação
    paginator = Paginator(notifications, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estatísticas
    stats = {
        'total': Notification.objects.filter(user=request.user).count(),
        'unread': Notification.objects.filter(user=request.user, read=False).count(),
        'today': Notification.objects.filter(
            user=request.user,
            created_at__date=timezone.now().date()
        ).count()
    }
    
    # Tipos disponíveis com labels (order_by() limpa o ordering padrão para distinct funcionar)
    tipos_raw = Notification.objects.filter(
        user=request.user
    ).order_by('type').values_list('type', flat=True).distinct()
    
    type_labels = dict(Notification.NOTIFICATION_TYPES)
    tipos_disponiveis = [(t, type_labels.get(t, t.replace('_', ' ').title())) for t in tipos_raw]
    tipos_disponiveis.sort(key=lambda x: x[1])
    
    context = {
        'notifications': page_obj,
        'stats': stats,
        'tipos_disponiveis': tipos_disponiveis,
        'filter_type': filter_type,
        'filter_read': filter_read,
        'filter_period': filter_period,
        'search_query': search_query,
        'page_obj': page_obj
    }
    
    return render(request, 'dashboard/notifications.html', context)

@login_required
def communication_center(request):
    """Central de Comunicação Unificada"""
    from django.db import models
    
    # Import seguro dos modelos
    try:
        from .models_chat import ChatRoom, ChatMessage, ChatBot
    except ImportError:
        ChatRoom = ChatMessage = ChatBot = None
    
    try:
        from .models_chatbot_ai import ChatbotConversation, ChatbotKnowledge
    except ImportError:
        ChatbotConversation = None
        ChatbotKnowledge = None
    
    # Dados do Chat Avançado - com tratamento de erro
    recent_conversations = []
    total_conversations = 0
    active_conversations = 0
    
    if ChatRoom:
        try:
            recent_conversations = ChatRoom.objects.filter(
                participants__user=request.user
            ).annotate(
                last_message_time=models.Max('messages__created_at')
            ).order_by('-last_message_time')[:5]
            
            total_conversations = ChatRoom.objects.filter(
                participants__user=request.user,
                created_at__date=timezone.now().date()
            ).count()
            
            active_conversations = ChatRoom.objects.filter(
                participants__user=request.user,
                status='active'
            ).count()
        except Exception as e:
            # Em caso de erro, usar valores padrão
            logger.error("Erro ao carregar dados do chat: %s", e, exc_info=True)
    
    # Dados do Chatbot IA
    chatbot = None
    if ChatBot:
        try:
            chatbot = ChatBot.objects.first()
        except Exception:
            pass
    
    # Base de conhecimento recente
    recent_knowledge = []
    if ChatbotKnowledge:
        try:
            recent_knowledge = ChatbotKnowledge.objects.order_by('-created_at')[:3]
        except Exception:
            pass
    
    # Analytics básicas
    total_messages_today = 0
    if ChatMessage:
        try:
            total_messages_today = ChatMessage.objects.filter(
                created_at__date=timezone.now().date()
            ).count()
        except Exception:
            pass
    
    # Calcular tempo médio de resposta real (em minutos)
    avg_response_time_val = 0
    if ChatMessage:
        try:
            from django.db.models import Avg, F
            avg_rt = ChatMessage.objects.filter(
                created_at__date=timezone.now().date(),
                reply_to__isnull=False,
            ).annotate(
                response_delta=F('created_at') - F('reply_to__created_at')
            ).aggregate(avg=Avg('response_delta'))['avg']
            if avg_rt:
                avg_response_time_val = round(avg_rt.total_seconds() / 60, 1)
        except Exception:
            pass

    # Taxa de satisfação real (baseada em avaliações)
    satisfaction_rate_val = 0
    try:
        from .models_satisfacao import AvaliacaoSatisfacao
        avaliacoes = AvaliacaoSatisfacao.objects.filter(
            criado_em__date=timezone.now().date()
        )
        total_aval = avaliacoes.count()
        if total_aval > 0:
            from django.db.models import Avg as AvgAval
            media = avaliacoes.aggregate(m=AvgAval('nota'))['m'] or 0
            satisfaction_rate_val = round(media / 5 * 100)  # normalizar para %
    except Exception:
        pass

    analytics_data = {
        'total_messages': total_messages_today,
        'active_conversations': active_conversations,
        'avg_response_time': avg_response_time_val,
        'satisfaction_rate': satisfaction_rate_val,
    }
    
    # Lista de usuários da equipe para nova conversa
    team_users = []
    try:
        team_users = get_user_model().objects.filter(
            is_active=True,
            groups__name__in=['Agentes', 'Supervisores', 'Gerentes']
        ).distinct()
    except Exception:
        # Fallback: todos os usuários ativos
        team_users = get_user_model().objects.filter(is_active=True)[:10]
    
    context = {
        'title': 'Central de Comunicação',
        'recent_conversations': recent_conversations,
        'total_conversations': total_conversations,
        'active_conversations': active_conversations,
        'avg_response_time': f"{avg_response_time_val}m" if avg_response_time_val else "0m",
        'chatbot': chatbot,
        'recent_knowledge': recent_knowledge,
        'analytics': analytics_data,
        'team_users': team_users,
    }
    
    return render(request, 'dashboard/communication_center.html', context)


# ========== APIs para Itens de Atendimento ==========

@login_required
def api_produtos_ativos(request):
    """API para listar produtos ativos para seleção"""
    from .models_estoque import Produto
    
    produtos = Produto.objects.filter(
        status='ativo'
    ).select_related('categoria', 'unidade_medida').order_by('nome')
    
    data = []
    for produto in produtos:
        data.append({
            'id': produto.id,
            'nome': produto.nome,
            'codigo': produto.codigo,
            'tipo': produto.tipo,
            'preco_venda': float(produto.preco_venda),
            'unidade_medida': produto.unidade_medida.sigla if produto.unidade_medida else 'un',
            'categoria': produto.categoria.nome if produto.categoria else '',
            'estoque_atual': float(produto.estoque_atual) if produto.controla_estoque else None,
        })
    
    return JsonResponse(data, safe=False)


@login_required
@require_http_methods(["POST"])
def api_add_item_atendimento(request):
    """API para adicionar item ao atendimento"""
    from .models import ItemAtendimento
    from .models_estoque import Produto
    from decimal import Decimal
    
    try:
        ticket_id = request.POST.get('ticket_id')
        produto_id = request.POST.get('produto')
        quantidade = request.POST.get('quantidade', 1)
        valor_unitario = request.POST.get('valor_unitario')
        tipo_item = request.POST.get('tipo_item', 'produto')
        desconto_percentual = request.POST.get('desconto_percentual', 0)
        observacoes = request.POST.get('observacoes', '')
        
        # Validações
        ticket = get_object_or_404(Ticket, id=ticket_id)
        produto = get_object_or_404(Produto, id=produto_id)
        
        # Verificar se o ticket está em status que permite edição
        if ticket.status not in ['aberto', 'em_andamento']:
            return JsonResponse({
                'success': False,
                'message': 'Só é possível adicionar itens em tickets abertos ou em andamento'
            })
        
        # Converter para Decimal para evitar problemas de tipo
        quantidade_decimal = Decimal(str(quantidade))
        valor_unitario_decimal = Decimal(str(valor_unitario))
        desconto_percentual_decimal = Decimal(str(desconto_percentual))
        
        # Verificar se o item já existe
        item_existente = ItemAtendimento.objects.filter(
            ticket=ticket, 
            produto=produto
        ).first()
        
        if item_existente:
            # Atualizar quantidade do item existente
            item_existente.quantidade += quantidade_decimal
            item_existente.valor_unitario = valor_unitario_decimal
            item_existente.desconto_percentual = desconto_percentual_decimal
            item_existente.observacoes = observacoes
            item_existente.save()
        else:
            # Criar novo item
            ItemAtendimento.objects.create(
                ticket=ticket,
                produto=produto,
                tipo_item=tipo_item,
                quantidade=quantidade_decimal,
                valor_unitario=valor_unitario_decimal,
                desconto_percentual=desconto_percentual_decimal,
                observacoes=observacoes,
                adicionado_por=request.user
            )
        
        return JsonResponse({'success': True, 'message': 'Item adicionado com sucesso'})
        
    except Exception:
        logger.exception('Erro em api_add_item_atendimento')
        return JsonResponse({'success': False, 'message': 'Erro interno do servidor'})


@login_required
def api_listar_itens_atendimento(request, ticket_id):
    """API para listar itens do atendimento"""
    from .models import ItemAtendimento
    from decimal import Decimal
    
    try:
        ticket = get_object_or_404(Ticket, id=ticket_id)
        itens = ItemAtendimento.objects.filter(ticket=ticket).select_related(
            'produto', 'produto__unidade_medida'
        ).order_by('adicionado_em')
        
        itens_data = []
        subtotal = Decimal('0')
        desconto_total = Decimal('0')
        
        for item in itens:
            item_data = {
                'id': item.id,
                'produto_nome': item.produto.nome,
                'produto_codigo': item.produto.codigo,
                'tipo_item': item.get_tipo_item_display(),
                'quantidade': float(item.quantidade),
                'valor_unitario': float(item.valor_unitario),
                'desconto_percentual': float(item.desconto_percentual),
                'valor_subtotal': float(item.valor_subtotal),
                'valor_desconto': float(item.valor_desconto),
                'valor_total': float(item.valor_total),
                'observacoes': item.observacoes,
                'unidade_medida': item.produto.unidade_medida.sigla if item.produto.unidade_medida else 'un',
                'adicionado_em': item.adicionado_em.strftime('%d/%m/%Y %H:%M'),
                'adicionado_por': item.adicionado_por.get_full_name() if item.adicionado_por else ''
            }
            itens_data.append(item_data)
            
            subtotal += item.valor_subtotal
            desconto_total += item.valor_desconto
        
        resumo = {
            'subtotal': float(subtotal),
            'desconto': float(desconto_total),
            'total': float(subtotal - desconto_total)
        }
        
        return JsonResponse({
            'success': True,
            'itens': itens_data,
            'resumo': resumo
        })
        
    except Exception:
        logger.exception('Erro em api_listar_itens_atendimento')
        return JsonResponse({'success': False, 'message': 'Erro interno do servidor'})


@login_required
@require_http_methods(["DELETE"])
def api_remover_item_atendimento(request, item_id):
    """API para remover item do atendimento"""
    from .models import ItemAtendimento
    
    try:
        item = get_object_or_404(ItemAtendimento, id=item_id)
        
        # Verificar se o ticket está em status que permite edição
        if item.ticket.status not in ['em_andamento']:
            return JsonResponse({
                'success': False,
                'message': 'Só é possível remover itens de tickets que estão em andamento'
            })
        
        item.delete()
        
        return JsonResponse({'success': True, 'message': 'Item removido com sucesso'})
        
    except Exception:
        logger.exception('Erro em api_remover_item_atendimento')
        return JsonResponse({'success': False, 'message': 'Erro interno do servidor'})


@login_required
def relatorio_itens_atendimento(request):
    """Relatório de produtos e serviços mais utilizados"""
    from .models import ItemAtendimento
    from django.db.models import Sum, Count, Avg, F, ExpressionWrapper, DecimalField
    
    # Expressão para valor_total calculado (quantidade * valor_unitario * (1 - desconto/100))
    valor_total_expr = ExpressionWrapper(
        F('quantidade') * F('valor_unitario') * (1 - F('desconto_percentual') / 100),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    )
    
    # Filtros
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    categoria = request.GET.get('categoria')
    agente = request.GET.get('agente')
    
    queryset = ItemAtendimento.objects.select_related(
        'produto', 'produto__categoria', 'ticket', 'ticket__agente'
    )
    
    if data_inicio:
        queryset = queryset.filter(adicionado_em__date__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(adicionado_em__date__lte=data_fim)
    if categoria:
        queryset = queryset.filter(produto__categoria_id=categoria)
    if agente:
        queryset = queryset.filter(ticket__agente_id=agente)
    
    # Produtos mais utilizados
    produtos_populares = queryset.values(
        'produto__nome', 'produto__codigo', 'tipo_item'
    ).annotate(
        total_quantidade=Sum('quantidade'),
        total_tickets=Count('ticket', distinct=True),
        valor_total=Sum(valor_total_expr),
        valor_medio=Avg(valor_total_expr)
    ).order_by('-total_quantidade')[:10]
    
    # Resumo por categoria
    resumo_categorias = queryset.values(
        'produto__categoria__nome'
    ).annotate(
        total_quantidade=Sum('quantidade'),
        total_valor=Sum(valor_total_expr),
        total_itens=Count('id')
    ).order_by('-total_valor')
    
    # Resumo por agente
    resumo_agentes = queryset.values(
        'ticket__agente__first_name', 'ticket__agente__last_name'
    ).annotate(
        total_valor=Sum(valor_total_expr),
        total_tickets=Count('ticket', distinct=True),
        valor_medio_ticket=Avg(valor_total_expr)
    ).order_by('-total_valor')
    
    # Totais gerais
    totais = queryset.aggregate(
        total_itens=Count('id'),
        total_valor=Sum(valor_total_expr),
        total_tickets=Count('ticket', distinct=True),
        valor_medio_item=Avg(valor_total_expr)
    )
    
    context = {
        'title': 'Relatório de Itens de Atendimento',
        'produtos_populares': produtos_populares,
        'resumo_categorias': resumo_categorias,
        'resumo_agentes': resumo_agentes,
        'totais': totais,
        'filtros': {
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'categoria': categoria,
            'agente': agente,
        }
    }
    
    return render(request, 'dashboard/relatorio_itens_atendimento.html', context)


@login_required
def api_estatisticas_financeiras_ticket(request, ticket_id):
    """API com estatísticas financeiras de um ticket"""
    from .models import ItemAtendimento
    from django.db.models import Sum
    
    try:
        ticket = get_object_or_404(Ticket, id=ticket_id)
        itens = ItemAtendimento.objects.filter(ticket=ticket)
        
        # Calcular estatísticas
        estatisticas = itens.aggregate(
            subtotal=Sum('valor_subtotal'),
            desconto_total=Sum('valor_desconto'),
            total=Sum('valor_total'),
            quantidade_itens=Count('id')
        )
        
        # Evitar valores None
        for key, value in estatisticas.items():
            if value is None:
                estatisticas[key] = 0 if key != 'quantidade_itens' else 0
        
        # Detalhes por tipo
        detalhes_tipos = itens.values('tipo_item').annotate(
            quantidade=Count('id'),
            valor_total=Sum('valor_total')
        )
        
        return JsonResponse({
            'success': True,
            'estatisticas': estatisticas,
            'detalhes_tipos': list(detalhes_tipos),
            'tem_itens': itens.exists()
        })
        
    except Exception:
        logger.exception('Erro em api_estatisticas_itens_atendimento')
        return JsonResponse({'success': False, 'message': 'Erro interno do servidor'})
