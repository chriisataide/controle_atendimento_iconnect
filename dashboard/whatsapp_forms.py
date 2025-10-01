from django import forms
from django.contrib.auth.models import User
from .models_whatsapp import (
    WhatsAppBusinessAccount, WhatsAppTemplate, WhatsAppAutoResponse,
    WhatsAppContact
)


class WhatsAppAccountForm(forms.ModelForm):
    """Formulário para conta do WhatsApp Business"""
    
    class Meta:
        model = WhatsAppBusinessAccount
        fields = [
            'nome', 'phone_number_id', 'business_account_id',
            'access_token', 'webhook_verify_token', 'webhook_url', 'ativo'
        ]
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome da conta'
            }),
            'phone_number_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone Number ID do WhatsApp'
            }),
            'business_account_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Business Account ID'
            }),
            'access_token': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Access Token da API'
            }),
            'webhook_verify_token': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Token de verificação do webhook'
            }),
            'webhook_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'URL do webhook'
            }),
            'ativo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }


class WhatsAppTemplateForm(forms.ModelForm):
    """Formulário para templates do WhatsApp"""
    
    class Meta:
        model = WhatsAppTemplate
        fields = [
            'account', 'nome', 'categoria', 'idioma', 'conteudo',
            'descricao', 'ativo'
        ]
        widgets = {
            'account': forms.Select(attrs={
                'class': 'form-select'
            }),
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome do template'
            }),
            'categoria': forms.Select(attrs={
                'class': 'form-select'
            }),
            'idioma': forms.TextInput(attrs={
                'class': 'form-control',
                'value': 'pt_BR'
            }),
            'conteudo': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Conteúdo do template em JSON'
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descrição do template'
            }),
            'ativo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }


class WhatsAppAutoResponseForm(forms.ModelForm):
    """Formulário para respostas automáticas"""
    
    class Meta:
        model = WhatsAppAutoResponse
        fields = [
            'account', 'nome', 'tipo_trigger', 'trigger_value',
            'template', 'mensagem_texto', 'ativo', 'prioridade'
        ]
        widgets = {
            'account': forms.Select(attrs={
                'class': 'form-select'
            }),
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome da resposta automática'
            }),
            'tipo_trigger': forms.Select(attrs={
                'class': 'form-select'
            }),
            'trigger_value': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Valor do gatilho (ex: palavra-chave)'
            }),
            'template': forms.Select(attrs={
                'class': 'form-select'
            }),
            'mensagem_texto': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Mensagem de texto (se não usar template)'
            }),
            'ativo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'prioridade': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 100
            }),
        }


class WhatsAppContactForm(forms.ModelForm):
    """Formulário para editar contatos"""
    
    class Meta:
        model = WhatsAppContact
        fields = ['nome', 'usuario', 'tags', 'bloqueado']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome do contato'
            }),
            'usuario': forms.Select(attrs={
                'class': 'form-select'
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tags separadas por vírgula'
            }),
            'bloqueado': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }


class WhatsAppMessageForm(forms.Form):
    """Formulário para enviar mensagens"""
    
    TIPOS_MENSAGEM = [
        ('text', 'Texto'),
        ('template', 'Template'),
        ('interactive', 'Interativo'),
    ]
    
    tipo = forms.ChoiceField(
        choices=TIPOS_MENSAGEM,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    mensagem = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Digite sua mensagem...'
        }),
        required=False
    )
    
    template = forms.ModelChoiceField(
        queryset=WhatsAppTemplate.objects.filter(ativo=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        empty_label="Selecione um template"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get('tipo')
        mensagem = cleaned_data.get('mensagem')
        template = cleaned_data.get('template')
        
        if tipo == 'text' and not mensagem:
            raise forms.ValidationError('Mensagem de texto é obrigatória para tipo "texto"')
        
        if tipo == 'template' and not template:
            raise forms.ValidationError('Template é obrigatório para tipo "template"')
        
        return cleaned_data


class WhatsAppBulkMessageForm(forms.Form):
    """Formulário para envio em massa"""
    
    contacts = forms.ModelMultipleChoiceField(
        queryset=WhatsAppContact.objects.filter(bloqueado=False),
        widget=forms.CheckboxSelectMultiple,
        label="Contatos"
    )
    
    template = forms.ModelChoiceField(
        queryset=WhatsAppTemplate.objects.filter(ativo=True, status='approved'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Selecione um template aprovado"
    )
    
    agendamento = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        }),
        required=False,
        label="Agendar envio (opcional)"
    )


class WhatsAppAnalyticsFilterForm(forms.Form):
    """Formulário para filtros de analytics"""
    
    PERIOD_CHOICES = [
        (7, 'Últimos 7 dias'),
        (30, 'Últimos 30 dias'),
        (90, 'Últimos 90 dias'),
    ]
    
    account = forms.ModelChoiceField(
        queryset=WhatsAppBusinessAccount.objects.filter(ativo=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        empty_label="Todas as contas"
    )
    
    period = forms.ChoiceField(
        choices=PERIOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial=30
    )
    
    data_inicio = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        required=False
    )
    
    data_fim = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        required=False
    )