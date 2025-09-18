from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()


class DashboardUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}))
    first_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Primeiro nome'}))
    last_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Último nome'}))
    is_staff = forms.BooleanField(required=False, initial=False, widget=forms.CheckboxInput())
    is_superuser = forms.BooleanField(required=False, initial=False, widget=forms.CheckboxInput())
    is_active = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput())

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_superuser', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add bootstrap classes to password inputs
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Senha'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirme a senha'})
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Nome de usuário'})
"""
Formulários para iConnect
Formulários otimizados para web e mobile
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import Ticket, Cliente

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
        ('BAIXA', 'Baixa'),
        ('MEDIA', 'Média'),
        ('ALTA', 'Alta'),
        ('CRITICA', 'Crítica'),
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

class ClienteForm(forms.ModelForm):
    """Formulário para cadastro de clientes"""
    
    class Meta:
        model = Cliente
        fields = ['nome', 'email', 'telefone', 'empresa']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome completo'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@exemplo.com'
            }),
            'telefone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(11) 99999-9999'
            }),
            'empresa': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome da empresa'
            })
        }
