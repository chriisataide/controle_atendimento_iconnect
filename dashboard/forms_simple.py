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
    """Formulário para cadastro de clientes (empresa)"""
    
    class Meta:
        model = Cliente
        fields = [
            'nome', 'nome_fantasia', 'cnpj', 'inscricao_estadual', 'segmento',
            'email', 'telefone', 'celular', 'website',
            'cep', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'estado',
            'responsavel_nome', 'responsavel_cargo', 'responsavel_telefone', 'responsavel_email',
            'observacoes', 'ativo'
        ]
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Razão Social'}),
            'nome_fantasia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome Fantasia'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00.000.000/0000-00'}),
            'inscricao_estadual': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Inscrição Estadual'}),
            'segmento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Bancário, Varejo...'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@empresa.com'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(11) 1234-5678'}),
            'celular': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(11) 91234-5678'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'cep': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00000-000'}),
            'logradouro': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Rua, Avenida...'}),
            'numero': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nº'}),
            'complemento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Sala, Andar...'}),
            'bairro': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Bairro'}),
            'cidade': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cidade'}),
            'estado': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'UF'}),
            'responsavel_nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do responsável'}),
            'responsavel_cargo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cargo / Função'}),
            'responsavel_telefone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(11) 91234-5678'}),
            'responsavel_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@empresa.com'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Observações...'}),
        }
