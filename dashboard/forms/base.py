from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from ..models import Ticket, Cliente, CategoriaTicket
from ..utils.rbac import UserRole, ALL_ROLES, ROLE_ADMIN, ROLE_AGENTE, assign_role

User = get_user_model()


class DashboardUserCreationForm(UserCreationForm):
    """Formulário seguro para criação de usuários com seleção de nível de acesso.
    SEGURANÇA: is_staff e is_superuser são definidos automaticamente pelo RBAC.
    """
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}))
    first_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Primeiro nome'}))
    last_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Último nome'}))
    is_active = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput())
    role = forms.ChoiceField(
        choices=UserRole.ROLE_CHOICES,
        initial=ROLE_AGENTE,
        required=True,
        label='Nível de Acesso',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_active')

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Senha'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirme a senha'})
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Nome de usuário'})

        # Apenas admin pode atribuir role de admin
        if self.request_user and not self.request_user.is_superuser:
            self.fields['role'].choices = [
                (val, label) for val, label in UserRole.ROLE_CHOICES
                if val != ROLE_ADMIN
            ]

    def clean_role(self):
        role = self.cleaned_data.get('role')
        if role not in ALL_ROLES:
            raise forms.ValidationError('Nível de acesso inválido.')
        # Apenas superuser pode criar admin
        if role == ROLE_ADMIN and self.request_user and not self.request_user.is_superuser:
            raise forms.ValidationError('Apenas administradores podem criar outros administradores.')
        return role

    def save(self, commit=True):
        user = super().save(commit=False)
        # Flags serão definidos pelo assign_role — não confiar em dados do formulário
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
            # Atribuir nível de acesso via RBAC
            role = self.cleaned_data.get('role', ROLE_AGENTE)
            assign_role(user, role)
        return user
"""
Formulários para iConnect
Formulários otimizados para web e mobile
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from ..models import Ticket, Cliente

class CustomLoginForm(AuthenticationForm):
    """
    Formulário de login customizado com styling
    """
    username = forms.CharField(
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nome de usuário',
            'id': 'username',
            'required': True,
            'autocomplete': 'username'
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Senha',
            'id': 'password',
            'required': True,
            'autocomplete': 'current-password'
        })
    )
    
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'rememberMe'
        })
    )

class QuickTicketForm(forms.Form):
    """Formulário rápido para criação de tickets (mobile)"""
    
    PRIORITY_CHOICES = [
        ('baixa', 'Baixa'),
        ('media', 'Média'),
        ('alta', 'Alta'),
        ('critica', 'Crítica'),
    ]
    
    title = forms.CharField(
        max_length=200,
        label='Título do problema',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Descreva o problema brevemente',
            'autocomplete': 'off'
        })
    )
    
    description = forms.CharField(
        label='Descrição detalhada',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Descreva o problema com mais detalhes...'
        })
    )
    
    priority = forms.ChoiceField(
        choices=PRIORITY_CHOICES,
        initial='MEDIA',
        label='Prioridade',
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )

class MobileCommentForm(forms.Form):
    """Formulário para comentários mobile"""
    
    comment = forms.CharField(
        label='Adicionar comentário',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Digite seu comentário...'
        })
    )
    
    private = forms.BooleanField(
        required=False,
        label='Comentário interno (apenas equipe)',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

class TicketForm(forms.ModelForm):
    """Formulário principal para tickets"""
    
    class Meta:
        model = Ticket
        fields = ['titulo', 'descricao', 'prioridade', 'categoria']
        widgets = {
            'titulo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Título do ticket'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Descrição detalhada do problema'
            }),
            'prioridade': forms.Select(attrs={
                'class': 'form-select'
            }),
            'categoria': forms.Select(attrs={
                'class': 'form-select'
            })
        }


class TicketCreateForm(forms.ModelForm):
    """Formulário para criação de tickets com cliente e ponto de venda"""
    
    class Meta:
        model = Ticket
        fields = ['cliente', 'ponto_de_venda', 'categoria', 'tipo', 'titulo', 'descricao', 'prioridade', 'tags']
        widgets = {
            'cliente': forms.Select(attrs={
                'class': 'form-control',
                'id': 'clienteSelect'
            }),
            'ponto_de_venda': forms.Select(attrs={
                'class': 'form-control',
                'id': 'pdvSelect'
            }),
            'categoria': forms.Select(attrs={
                'class': 'form-control',
                'id': 'categoriaSelect'
            }),
            'tipo': forms.Select(attrs={
                'class': 'form-control',
                'id': 'tipoSelect'
            }),
            'titulo': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'tituloInput',
                'placeholder': 'Título do ticket'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Descrição detalhada do problema'
            }),
            'prioridade': forms.Select(attrs={
                'class': 'form-control',
                'id': 'prioridadeSelect'
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'tagsInput',
                'placeholder': 'Tags separadas por vírgula'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from ..models import PontoDeVenda
        self.fields['cliente'].queryset = Cliente.objects.all().order_by('nome')
        self.fields['ponto_de_venda'].queryset = PontoDeVenda.objects.select_related('cliente').all().order_by('nome_fantasia')
        self.fields['categoria'].queryset = CategoriaTicket.objects.all()
        self.fields['cliente'].empty_label = "Selecione um cliente..."
        self.fields['ponto_de_venda'].empty_label = "Selecione um ponto de venda..."
        self.fields['categoria'].empty_label = "Selecione uma categoria..."
        self.fields['prioridade'].empty_label = "Selecione a prioridade..."

class ClienteForm(forms.ModelForm):
    """Formulário simples para cadastro de clientes (instituições).
    Endereço, CNPJ e responsável ficam no Ponto de Venda."""

    class Meta:
        model = Cliente
        fields = ['nome', 'segmento', 'email', 'telefone', 'observacoes', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': ' '
            }),
            'segmento': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': ' '
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control', 'placeholder': ' '
            }),
            'telefone': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': ' '
            }),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control', 'placeholder': ' ', 'rows': 3
            }),
            'ativo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
