"""
Views de autenticação, perfil de usuário, gestão de usuários e pontos de venda.
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, ListView, CreateView, DetailView, UpdateView
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse_lazy
from django import forms
import logging

from ..models import (
    Ticket, PerfilUsuario, InteracaoTicket, PerfilAgente, PontoDeVenda,
)
from ..forms import DashboardUserCreationForm
from ..utils.security import rate_limit, log_suspicious_activity
from ..api.versioning import api_version, APIResponseTransformer

logger = logging.getLogger('dashboard')
User = get_user_model()


# ========== PONTO DE VENDA ==========

class PontoDeVendaForm(forms.ModelForm):
    class Meta:
        model = PontoDeVenda
        fields = '__all__'
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select', 'id': 'clienteSelect'}),
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from ..models import Cliente
        self.fields['cliente'].queryset = Cliente.objects.all().order_by('nome')
        self.fields['cliente'].empty_label = "Selecione um cliente..."
        self.fields['cliente'].required = False


@method_decorator([login_required], name='dispatch')
class PontoDeVendaListView(ListView):
    model = PontoDeVenda
    template_name = 'dashboard/pontodevenda_list.html'
    context_object_name = 'pontosdevenda'
    paginate_by = 50

    def get_queryset(self):
        qs = PontoDeVenda.objects.select_related('cliente').all()

        # Busca textual
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(nome_fantasia__icontains=q) |
                Q(razao_social__icontains=q) |
                Q(cnpj__icontains=q) |
                Q(cidade__icontains=q) |
                Q(bairro__icontains=q) |
                Q(logradouro__icontains=q)
            )

        # Filtro por UF
        uf = self.request.GET.get('uf', '').strip().upper()
        if uf:
            qs = qs.filter(estado=uf)

        # Filtro por cliente
        cliente_id = self.request.GET.get('cliente', '').strip()
        if cliente_id:
            qs = qs.filter(cliente_id=cliente_id)

        # Ordenação
        sort = self.request.GET.get('sort', '-criado_em')
        allowed_sorts = [
            'nome_fantasia', '-nome_fantasia',
            'cidade', '-cidade',
            'estado', '-estado',
            'cnpj', '-cnpj',
            'criado_em', '-criado_em',
            'cliente__nome', '-cliente__nome',
        ]
        if sort in allowed_sorts:
            qs = qs.order_by(sort)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from django.db.models import Count
        from ..models import Cliente

        all_pdvs = PontoDeVenda.objects.all()
        ctx['total_pdvs'] = all_pdvs.count()
        ctx['total_estados'] = all_pdvs.values('estado').distinct().count()
        ctx['total_cidades'] = all_pdvs.values('cidade').distinct().count()
        ctx['total_clientes'] = all_pdvs.values('cliente').distinct().count()

        # Top 5 estados por quantidade
        ctx['top_estados'] = (
            all_pdvs.values('estado')
            .annotate(total=Count('id'))
            .order_by('-total')[:5]
        )

        # UFs disponíveis para filtro
        ctx['ufs_disponiveis'] = (
            all_pdvs.values_list('estado', flat=True)
            .distinct()
            .order_by('estado')
        )

        # Clientes disponíveis para filtro
        ctx['clientes_disponiveis'] = (
            Cliente.objects.filter(
                pontos_de_venda__isnull=False
            ).distinct().order_by('nome')
        )

        # Preservar filtros na UI
        ctx['current_q'] = self.request.GET.get('q', '')
        ctx['current_uf'] = self.request.GET.get('uf', '')
        ctx['current_cliente'] = self.request.GET.get('cliente', '')
        ctx['current_sort'] = self.request.GET.get('sort', '-criado_em')

        return ctx

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


@login_required
def api_pontos_de_venda_por_cliente(request):
    """API AJAX para retornar pontos de venda filtrados por cliente"""
    cliente_id = request.GET.get('cliente_id')
    uniorg = request.GET.get('uniorg', '').strip()
    if cliente_id:
        pdvs = PontoDeVenda.objects.filter(cliente_id=cliente_id).order_by('nome_fantasia')
    else:
        pdvs = PontoDeVenda.objects.all().order_by('nome_fantasia')
    if uniorg:
        pdvs = pdvs.filter(inscricao_estadual__icontains=uniorg)
    data = [{
        'id': p.id,
        'nome_fantasia': p.nome_fantasia,
        'cidade': p.cidade or '',
        'estado': p.estado or '',
        'uniorg': p.inscricao_estadual or '',
        'cnpj': p.cnpj or '',
    } for p in pdvs]
    return JsonResponse(data, safe=False)


# ========== GESTÃO DE USUÁRIOS ==========

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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request_user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = form.save()
        role_display = dict(form.fields['role'].choices).get(form.cleaned_data['role'], '')
        messages.success(self.request, f'Usuário {user.username} criado com sucesso como {role_display}.')
        return super().form_valid(form)


# ========== VIEWS DE AUTENTICAÇÃO ==========

def custom_login(request):
    """View personalizada para login com template customizado"""
    from ..forms import CustomLoginForm

    if request.user.is_authenticated:
        return redirect('dashboard:index')

    form = CustomLoginForm()

    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Bem-vindo, {user.get_full_name() or user.username}!')

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
    """View personalizada para logout"""
    if request.user.is_authenticated:
        username = request.user.get_full_name() or request.user.username
        logout(request)
        messages.success(request, f'Até logo, {username}! Logout realizado com sucesso.')
    else:
        logout(request)
    return redirect('login')


@login_required
@rate_limit(max_requests=60, window_seconds=3600)
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

    version = getattr(request, 'api_version', 'v2')
    transformed_data = APIResponseTransformer.transform_user_data(user_data, version)

    return JsonResponse(transformed_data)


# ========== PERFIL DO USUÁRIO ==========

@method_decorator(login_required, name='dispatch')
class ProfileView(TemplateView):
    template_name = 'dashboard/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        perfil, created = PerfilUsuario.objects.get_or_create(
            user=user,
            defaults={'telefone': ''}
        )
        context['perfil'] = perfil

        user_tickets = Ticket.objects.filter(
            Q(agente=user) | Q(cliente__user=user) if hasattr(user, 'cliente') else Q(agente=user)
        )
        context['user_stats'] = {
            'ocorrencias': user_tickets.filter(prioridade__in=['critica', 'alta']).count(),
            'chamados': user_tickets.count(),
            'atendimentos': user_tickets.filter(status__in=['resolvido', 'fechado']).count(),
        }

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

            user = request.user
            user.first_name = request.POST.get('first_name', '')
            user.last_name = request.POST.get('last_name', '')
            user.email = request.POST.get('email', '')
            user.save()

            perfil.telefone = request.POST.get('telefone', '')
            perfil.telefone_alternativo = request.POST.get('telefone_alternativo', '')
            perfil.endereco = request.POST.get('endereco', '')
            perfil.cidade = request.POST.get('cidade', '')
            perfil.estado = request.POST.get('estado', '')
            perfil.cep = request.POST.get('cep', '')
            perfil.cargo = request.POST.get('cargo', '')
            perfil.departamento = request.POST.get('departamento', '')
            perfil.bio = request.POST.get('bio', '')

            if 'avatar' in request.FILES:
                from ..utils.security import validate_file_upload
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


# ========== STATUS DO AGENTE ==========

@login_required
@rate_limit(max_requests=30, window_seconds=3600)
@log_suspicious_activity("Agent status update")
def update_agent_status(request):
    """API para atualizar status do agente"""
    logger.debug("update_agent_status called by %s, method: %s", request.user.username, request.method)

    if request.method == 'POST':
        new_status = request.POST.get('status', '').lower().strip()
        logger.debug("Novo status solicitado: '%s'", new_status)

        valid_statuses = ['online', 'ocupado', 'ausente', 'offline']
        if new_status not in valid_statuses:
            return JsonResponse({
                'success': False,
                'message': f'Status inválido. Use: {", ".join(valid_statuses)}'
            })

        try:
            perfil_agente, created = PerfilAgente.objects.get_or_create(
                user=request.user,
                defaults={'status': new_status}
            )
            if not created:
                perfil_agente.status = new_status
                perfil_agente.save()

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
                'message': 'Erro interno do servidor'
            })

    return JsonResponse({'success': False, 'message': 'Método não permitido!'})
