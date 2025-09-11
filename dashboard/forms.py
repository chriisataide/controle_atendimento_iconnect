"""
Formulários para iConnect
Formulários otimizados para web e mobile
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Ticket, Customer, Agent

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
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Digite seu comentário...',
            'maxlength': 1000
        }),
        max_length=1000,
        label=''
    )

class TicketForm(forms.ModelForm):
    """Formulário completo para tickets"""
    
    class Meta:
        model = Ticket
        fields = ['title', 'description', 'priority', 'category']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Título do ticket'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Descreva o problema ou solicitação...'
            }),
            'priority': forms.Select(attrs={
                'class': 'form-select'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select'
            })
        }

class CustomerForm(forms.ModelForm):
    """Formulário para cadastro/edição de clientes"""
    
    class Meta:
        model = Customer
        fields = ['name', 'email', 'phone', 'company']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome completo'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@exemplo.com'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(11) 99999-9999'
            }),
            'company': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome da empresa (opcional)'
            })
        }

class AgentRegistrationForm(UserCreationForm):
    """Formulário para registro de agentes"""
    
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nome'
        })
    )
    
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Sobrenome'
        })
    )
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'email@exemplo.com'
        })
    )
    
    department = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Departamento'
        })
    )
    
    skills = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Habilidades e especialidades (uma por linha)'
        }),
        help_text='Lista de habilidades, uma por linha'
    )
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome de usuário'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplicar classes CSS aos campos de senha
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            
            # Criar perfil de agente
            Agent.objects.create(
                user=user,
                department=self.cleaned_data.get('department', ''),
                skills=self.cleaned_data.get('skills', ''),
                is_active=True
            )
        
        return user

class TicketFilterForm(forms.Form):
    """Formulário para filtros de tickets"""
    
    STATUS_CHOICES = [
        ('', 'Todos os status'),
        ('NOVO', 'Novo'),
        ('ABERTO', 'Aberto'),
        ('EM_ANDAMENTO', 'Em Andamento'),
        ('PENDENTE', 'Pendente'),
        ('RESOLVIDO', 'Resolvido'),
        ('FECHADO', 'Fechado')
    ]
    
    PRIORITY_CHOICES = [
        ('', 'Todas as prioridades'),
        ('BAIXA', 'Baixa'),
        ('MEDIA', 'Média'),
        ('ALTA', 'Alta'),
        ('CRITICA', 'Crítica')
    ]
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar tickets...',
            'autocomplete': 'off'
        })
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    priority = forms.ChoiceField(
        choices=PRIORITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    assigned_to = forms.ModelChoiceField(
        queryset=Agent.objects.filter(is_active=True),
        required=False,
        empty_label="Todos os agentes",
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

class BulkActionForm(forms.Form):
    """Formulário para ações em massa"""
    
    ACTION_CHOICES = [
        ('', 'Selecionar ação'),
        ('assign', 'Atribuir agente'),
        ('change_status', 'Alterar status'),
        ('change_priority', 'Alterar prioridade'),
        ('add_tag', 'Adicionar tag'),
        ('export', 'Exportar selecionados')
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    agent = forms.ModelChoiceField(
        queryset=Agent.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    status = forms.ChoiceField(
        choices=TicketFilterForm.STATUS_CHOICES[1:],  # Sem opção vazia
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    priority = forms.ChoiceField(
        choices=TicketFilterForm.PRIORITY_CHOICES[1:],  # Sem opção vazia
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )

class ReportForm(forms.Form):
    """Formulário para geração de relatórios"""
    
    REPORT_CHOICES = [
        ('performance_agent', 'Performance dos Agentes'),
        ('tickets_summary', 'Resumo de Tickets'),
        ('sla_analysis', 'Análise de SLA'),
        ('customer_satisfaction', 'Satisfação do Cliente'),
        ('workload_distribution', 'Distribuição de Carga'),
    ]
    
    FORMAT_CHOICES = [
        ('json', 'Visualizar no sistema'),
        ('excel', 'Exportar Excel'),
        ('csv', 'Exportar CSV'),
        ('pdf', 'Exportar PDF')
    ]
    
    report_type = forms.ChoiceField(
        choices=REPORT_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    format = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        initial='json',
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    agents = forms.ModelMultipleChoiceField(
        queryset=Agent.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple()
    )

class ChatMessageForm(forms.Form):
    """Formulário para mensagens do chat/chatbot"""
    
    message = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Digite sua mensagem...',
            'autocomplete': 'off',
            'maxlength': 500
        }),
        max_length=500
    )

class ContactForm(forms.Form):
    """Formulário de contato público"""
    
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Seu nome completo'
        })
    )
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'seu@email.com'
        })
    )
    
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '(11) 99999-9999'
        })
    )
    
    subject = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Assunto da mensagem'
        })
    )
    
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Descreva sua solicitação ou problema...'
        })
    )
    
    def save(self):
        """Cria ticket a partir do formulário de contato"""
        
        # Buscar ou criar customer
        customer, created = Customer.objects.get_or_create(
            email=self.cleaned_data['email'],
            defaults={
                'name': self.cleaned_data['name'],
                'phone': self.cleaned_data.get('phone', '')
            }
        )
        
        # Criar ticket
        ticket = Ticket.objects.create(
            customer=customer,
            title=self.cleaned_data['subject'],
            description=self.cleaned_data['message'],
            priority='MEDIA',
            status='NOVO',
            source='WEBSITE'
        )
        
        return ticket
