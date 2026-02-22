from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
import json


class WhatsAppBusinessAccount(models.Model):
    """Conta do WhatsApp Business"""
    nome = models.CharField(max_length=100, verbose_name='Nome da Conta')
    phone_number_id = models.CharField(max_length=50, unique=True, verbose_name='Phone Number ID')
    business_account_id = models.CharField(max_length=50, verbose_name='Business Account ID')
    access_token = models.TextField(verbose_name='Access Token', help_text='Armazenado criptografado')
    webhook_verify_token = models.CharField(max_length=500, verbose_name='Webhook Verify Token', help_text='Armazenado criptografado')
    webhook_url = models.URLField(verbose_name='Webhook URL')
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        verbose_name = 'Conta WhatsApp Business'
        verbose_name_plural = 'Contas WhatsApp Business'
        ordering = ['-criado_em']
    
    def save(self, *args, **kwargs):
        from dashboard.crypto import encrypt_value
        if self.access_token and not self.access_token.startswith('enc::'):
            self.access_token = encrypt_value(self.access_token)
        if self.webhook_verify_token and not self.webhook_verify_token.startswith('enc::'):
            self.webhook_verify_token = encrypt_value(self.webhook_verify_token)
        super().save(*args, **kwargs)

    def get_access_token(self):
        """Retorna o access token descriptografado."""
        from dashboard.crypto import decrypt_value
        return decrypt_value(self.access_token)

    def get_webhook_verify_token(self):
        """Retorna o webhook verify token descriptografado."""
        from dashboard.crypto import decrypt_value
        return decrypt_value(self.webhook_verify_token)

    def __str__(self):
        return f"{self.nome} ({self.phone_number_id})"


class WhatsAppContact(models.Model):
    """Contatos do WhatsApp"""
    whatsapp_id = models.CharField(max_length=50, unique=True, verbose_name='WhatsApp ID')
    phone_number = models.CharField(max_length=20, verbose_name='Número de Telefone')
    nome = models.CharField(max_length=100, blank=True, verbose_name='Nome')
    profile_name = models.CharField(max_length=100, blank=True, verbose_name='Nome do Perfil')
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Usuário Vinculado')
    bloqueado = models.BooleanField(default=False, verbose_name='Bloqueado')
    tags = models.CharField(max_length=200, blank=True, verbose_name='Tags')
    metadados = models.JSONField(default=dict, verbose_name='Metadados')
    primeiro_contato = models.DateTimeField(auto_now_add=True, verbose_name='Primeiro Contato')
    ultimo_contato = models.DateTimeField(auto_now=True, verbose_name='Último Contato')
    
    class Meta:
        verbose_name = 'Contato WhatsApp'
        verbose_name_plural = 'Contatos WhatsApp'
        ordering = ['-ultimo_contato']
        indexes = [
            models.Index(fields=['whatsapp_id']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['-ultimo_contato']),
        ]
    
    def __str__(self):
        return f"{self.nome or self.profile_name or self.phone_number}"


class WhatsAppConversation(models.Model):
    """Conversas do WhatsApp"""
    ESTADOS = [
        ('ativa', 'Ativa'),
        ('pausada', 'Pausada'),
        ('encerrada', 'Encerrada'),
        ('transferida', 'Transferida'),
    ]
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    account = models.ForeignKey(WhatsAppBusinessAccount, on_delete=models.CASCADE, verbose_name='Conta')
    contact = models.ForeignKey(WhatsAppContact, on_delete=models.CASCADE, verbose_name='Contato')
    agente = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Agente Responsável')
    ticket = models.ForeignKey('Ticket', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Ticket Vinculado')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='ativa', verbose_name='Estado')
    titulo = models.CharField(max_length=200, blank=True, verbose_name='Título')
    iniciada_em = models.DateTimeField(auto_now_add=True, verbose_name='Iniciada em')
    encerrada_em = models.DateTimeField(null=True, blank=True, verbose_name='Encerrada em')
    contexto = models.JSONField(default=dict, verbose_name='Contexto')
    
    class Meta:
        verbose_name = 'Conversa WhatsApp'
        verbose_name_plural = 'Conversas WhatsApp'
        ordering = ['-iniciada_em']
        indexes = [
            models.Index(fields=['account', 'contact', '-iniciada_em']),
            models.Index(fields=['estado', '-iniciada_em']),
            models.Index(fields=['agente', '-iniciada_em']),
        ]
    
    def __str__(self):
        return f"Conversa com {self.contact} - {self.estado}"


class WhatsAppMessage(models.Model):
    """Mensagens do WhatsApp"""
    TIPOS_MENSAGEM = [
        ('text', 'Texto'),
        ('image', 'Imagem'),
        ('audio', 'Áudio'),
        ('video', 'Vídeo'),
        ('document', 'Documento'),
        ('location', 'Localização'),
        ('contact', 'Contato'),
        ('interactive', 'Interativo'),
        ('template', 'Template'),
        ('system', 'Sistema'),
    ]
    
    DIREÇÃO = [
        ('inbound', 'Recebida'),
        ('outbound', 'Enviada'),
    ]
    
    STATUS_MENSAGEM = [
        ('sent', 'Enviada'),
        ('delivered', 'Entregue'),
        ('read', 'Lida'),
        ('failed', 'Falhou'),
    ]
    
    whatsapp_message_id = models.CharField(max_length=100, unique=True, verbose_name='WhatsApp Message ID')
    conversation = models.ForeignKey(WhatsAppConversation, on_delete=models.CASCADE, related_name='mensagens', verbose_name='Conversa')
    contact = models.ForeignKey(WhatsAppContact, on_delete=models.CASCADE, verbose_name='Contato')
    agente = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Agente')
    direcao = models.CharField(max_length=10, choices=DIREÇÃO, verbose_name='Direção')
    tipo = models.CharField(max_length=20, choices=TIPOS_MENSAGEM, verbose_name='Tipo')
    conteudo = models.TextField(verbose_name='Conteúdo')
    media_url = models.URLField(blank=True, verbose_name='URL da Mídia')
    media_mime_type = models.CharField(max_length=100, blank=True, verbose_name='MIME Type da Mídia')
    metadata = models.JSONField(default=dict, verbose_name='Metadados')
    status = models.CharField(max_length=20, choices=STATUS_MENSAGEM, default='sent', verbose_name='Status')
    timestamp = models.DateTimeField(verbose_name='Timestamp')
    processada = models.BooleanField(default=False, verbose_name='Processada')
    erro = models.TextField(blank=True, verbose_name='Erro')
    
    class Meta:
        verbose_name = 'Mensagem WhatsApp'
        verbose_name_plural = 'Mensagens WhatsApp'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['conversation', 'timestamp']),
            models.Index(fields=['contact', '-timestamp']),
            models.Index(fields=['direcao', 'status']),
            models.Index(fields=['processada', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.get_direcao_display()} - {self.tipo} - {self.timestamp.strftime('%d/%m/%Y %H:%M')}"


class WhatsAppTemplate(models.Model):
    """Templates de mensagem do WhatsApp"""
    CATEGORIAS = [
        ('marketing', 'Marketing'),
        ('utility', 'Utilidade'),
        ('authentication', 'Autenticação'),
    ]
    
    STATUS_TEMPLATE = [
        ('approved', 'Aprovado'),
        ('pending', 'Pendente'),
        ('rejected', 'Rejeitado'),
        ('disabled', 'Desabilitado'),
    ]
    
    account = models.ForeignKey(WhatsAppBusinessAccount, on_delete=models.CASCADE, verbose_name='Conta')
    nome = models.CharField(max_length=100, verbose_name='Nome')
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, verbose_name='Categoria')
    idioma = models.CharField(max_length=10, default='pt_BR', verbose_name='Idioma')
    status = models.CharField(max_length=20, choices=STATUS_TEMPLATE, default='pending', verbose_name='Status')
    conteudo = models.JSONField(verbose_name='Conteúdo do Template')
    descricao = models.TextField(blank=True, verbose_name='Descrição')
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        verbose_name = 'Template WhatsApp'
        verbose_name_plural = 'Templates WhatsApp'
        unique_together = ['account', 'nome']
        ordering = ['-criado_em']
    
    def __str__(self):
        return f"{self.nome} ({self.categoria})"


class WhatsAppAutoResponse(models.Model):
    """Respostas automáticas do WhatsApp"""
    TIPOS_TRIGGER = [
        ('keyword', 'Palavra-chave'),
        ('first_message', 'Primeira mensagem'),
        ('business_hours', 'Fora do horário'),
        ('agent_unavailable', 'Agente indisponível'),
    ]
    
    account = models.ForeignKey(WhatsAppBusinessAccount, on_delete=models.CASCADE, verbose_name='Conta')
    nome = models.CharField(max_length=100, verbose_name='Nome')
    tipo_trigger = models.CharField(max_length=20, choices=TIPOS_TRIGGER, verbose_name='Tipo de Gatilho')
    trigger_value = models.CharField(max_length=200, blank=True, verbose_name='Valor do Gatilho')
    template = models.ForeignKey(WhatsAppTemplate, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Template')
    mensagem_texto = models.TextField(blank=True, verbose_name='Mensagem de Texto')
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    prioridade = models.IntegerField(default=0, verbose_name='Prioridade')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    
    class Meta:
        verbose_name = 'Resposta Automática WhatsApp'
        verbose_name_plural = 'Respostas Automáticas WhatsApp'
        ordering = ['-prioridade', '-criado_em']
    
    def __str__(self):
        return f"{self.nome} - {self.get_tipo_trigger_display()}"


class WhatsAppAnalytics(models.Model):
    """Analytics do WhatsApp"""
    account = models.ForeignKey(WhatsAppBusinessAccount, on_delete=models.CASCADE, verbose_name='Conta')
    data = models.DateField(verbose_name='Data')
    mensagens_enviadas = models.IntegerField(default=0, verbose_name='Mensagens Enviadas')
    mensagens_recebidas = models.IntegerField(default=0, verbose_name='Mensagens Recebidas')
    mensagens_entregues = models.IntegerField(default=0, verbose_name='Mensagens Entregues')
    mensagens_lidas = models.IntegerField(default=0, verbose_name='Mensagens Lidas')
    conversas_iniciadas = models.IntegerField(default=0, verbose_name='Conversas Iniciadas')
    conversas_encerradas = models.IntegerField(default=0, verbose_name='Conversas Encerradas')
    tickets_criados = models.IntegerField(default=0, verbose_name='Tickets Criados')
    tempo_resposta_medio = models.FloatField(null=True, blank=True, verbose_name='Tempo Resposta Médio (min)')
    
    class Meta:
        verbose_name = 'Analytics WhatsApp'
        verbose_name_plural = 'Analytics WhatsApp'
        unique_together = ['account', 'data']
        ordering = ['-data']
        indexes = [
            models.Index(fields=['account', '-data']),
        ]
    
    def __str__(self):
        return f"{self.account.nome} - {self.data}"


class WhatsAppWebhookLog(models.Model):
    """Log dos webhooks do WhatsApp"""
    TIPOS_EVENTO = [
        ('message', 'Mensagem'),
        ('status', 'Status'),
        ('notification', 'Notificação'),
        ('error', 'Erro'),
    ]
    
    account = models.ForeignKey(WhatsAppBusinessAccount, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Conta')
    tipo_evento = models.CharField(max_length=20, choices=TIPOS_EVENTO, verbose_name='Tipo de Evento')
    payload = models.JSONField(verbose_name='Payload')
    processado = models.BooleanField(default=False, verbose_name='Processado')
    erro = models.TextField(blank=True, verbose_name='Erro')
    ip_origem = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP de Origem')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Timestamp')
    
    class Meta:
        verbose_name = 'Log Webhook WhatsApp'
        verbose_name_plural = 'Logs Webhook WhatsApp'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['account', '-timestamp']),
            models.Index(fields=['processado', 'timestamp']),
            models.Index(fields=['tipo_evento', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.get_tipo_evento_display()} - {self.timestamp.strftime('%d/%m/%Y %H:%M:%S')}"