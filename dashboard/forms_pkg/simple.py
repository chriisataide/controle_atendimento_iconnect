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

class ClienteForm(forms.ModelForm):
    """Formulário simples para cadastro de clientes (instituições)"""

    class Meta:
        model = Cliente
        fields = ['nome', 'segmento', 'email', 'telefone', 'observacoes', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome da instituição'}),
            'segmento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Bancário, Varejo...'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@empresa.com'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(11) 1234-5678'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Observações...'}),
        }
