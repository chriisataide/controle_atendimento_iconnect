from django.contrib import admin
from .models import (
    WhatsAppBusinessAccount, WhatsAppContact, WhatsAppConversation,
    WhatsAppMessage, WhatsAppTemplate, WhatsAppAutoResponse,
    WhatsAppAnalytics, WhatsAppWebhookLog
)


@admin.register(WhatsAppBusinessAccount)
class WhatsAppBusinessAccountAdmin(admin.ModelAdmin):
    list_display = ['nome', 'phone_number_id', 'ativo', 'criado_em']
    list_filter = ['ativo', 'criado_em']
    search_fields = ['nome', 'phone_number_id', 'business_account_id']
    readonly_fields = ['criado_em', 'atualizado_em']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'phone_number_id', 'business_account_id', 'ativo')
        }),
        ('Configurações de API', {
            'fields': ('access_token', 'webhook_verify_token', 'webhook_url'),
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ['collapse']
        }),
    )


@admin.register(WhatsAppContact)
class WhatsAppContactAdmin(admin.ModelAdmin):
    list_display = ['nome', 'phone_number', 'usuario', 'bloqueado', 'ultimo_contato']
    list_filter = ['bloqueado', 'primeiro_contato', 'ultimo_contato']
    search_fields = ['nome', 'profile_name', 'phone_number', 'whatsapp_id']
    list_editable = ['bloqueado']
    readonly_fields = ['whatsapp_id', 'primeiro_contato', 'ultimo_contato', 'metadados']
    
    fieldsets = (
        ('Informações do Contato', {
            'fields': ('whatsapp_id', 'phone_number', 'nome', 'profile_name')
        }),
        ('Vinculação', {
            'fields': ('usuario', 'tags', 'bloqueado')
        }),
        ('Metadados', {
            'fields': ('metadados',),
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ('primeiro_contato', 'ultimo_contato'),
            'classes': ['collapse']
        }),
    )


@admin.register(WhatsAppConversation)
class WhatsAppConversationAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'contact', 'account', 'agente', 'estado', 'iniciada_em']
    list_filter = ['estado', 'account', 'iniciada_em']
    search_fields = ['titulo', 'contact__nome', 'contact__phone_number']
    list_editable = ['estado', 'agente']
    readonly_fields = ['uuid', 'iniciada_em', 'contexto']
    
    fieldsets = (
        ('Informações da Conversa', {
            'fields': ('uuid', 'account', 'contact', 'titulo', 'estado')
        }),
        ('Atribuição', {
            'fields': ('agente', 'ticket')
        }),
        ('Contexto', {
            'fields': ('contexto',),
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ('iniciada_em', 'encerrada_em'),
            'classes': ['collapse']
        }),
    )


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ['whatsapp_message_id', 'conversation', 'direcao', 'tipo', 'status', 'timestamp', 'processada']
    list_filter = ['direcao', 'tipo', 'status', 'processada', 'timestamp']
    search_fields = ['whatsapp_message_id', 'conteudo', 'conversation__titulo']
    list_editable = ['processada']
    readonly_fields = ['whatsapp_message_id', 'timestamp', 'metadata']
    
    fieldsets = (
        ('Informações da Mensagem', {
            'fields': ('whatsapp_message_id', 'conversation', 'contact', 'agente')
        }),
        ('Conteúdo', {
            'fields': ('direcao', 'tipo', 'conteudo', 'media_url', 'media_mime_type')
        }),
        ('Status', {
            'fields': ('status', 'processada', 'erro')
        }),
        ('Metadados', {
            'fields': ('metadata', 'timestamp'),
            'classes': ['collapse']
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('conversation', 'contact', 'agente')


@admin.register(WhatsAppTemplate)
class WhatsAppTemplateAdmin(admin.ModelAdmin):
    list_display = ['nome', 'account', 'categoria', 'status', 'ativo', 'criado_em']
    list_filter = ['categoria', 'status', 'ativo', 'criado_em']
    search_fields = ['nome', 'descricao']
    list_editable = ['ativo']
    readonly_fields = ['criado_em', 'atualizado_em']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('account', 'nome', 'categoria', 'idioma', 'status', 'ativo')
        }),
        ('Conteúdo', {
            'fields': ('descricao', 'conteudo')
        }),
        ('Timestamps', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ['collapse']
        }),
    )


@admin.register(WhatsAppAutoResponse)
class WhatsAppAutoResponseAdmin(admin.ModelAdmin):
    list_display = ['nome', 'account', 'tipo_trigger', 'ativo', 'prioridade', 'criado_em']
    list_filter = ['tipo_trigger', 'ativo', 'criado_em']
    search_fields = ['nome', 'trigger_value', 'mensagem_texto']
    list_editable = ['ativo', 'prioridade']
    readonly_fields = ['criado_em']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('account', 'nome', 'ativo', 'prioridade')
        }),
        ('Configuração do Gatilho', {
            'fields': ('tipo_trigger', 'trigger_value')
        }),
        ('Resposta', {
            'fields': ('template', 'mensagem_texto')
        }),
        ('Timestamp', {
            'fields': ('criado_em',),
            'classes': ['collapse']
        }),
    )


@admin.register(WhatsAppAnalytics)
class WhatsAppAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['account', 'data', 'mensagens_enviadas', 'mensagens_recebidas', 'conversas_iniciadas', 'tickets_criados']
    list_filter = ['account', 'data']
    search_fields = ['account__nome']
    readonly_fields = ['data']
    
    fieldsets = (
        ('Informações', {
            'fields': ('account', 'data')
        }),
        ('Métricas de Mensagens', {
            'fields': ('mensagens_enviadas', 'mensagens_recebidas', 'mensagens_entregues', 'mensagens_lidas')
        }),
        ('Métricas de Conversas', {
            'fields': ('conversas_iniciadas', 'conversas_encerradas', 'tickets_criados', 'tempo_resposta_medio')
        }),
    )


@admin.register(WhatsAppWebhookLog)
class WhatsAppWebhookLogAdmin(admin.ModelAdmin):
    list_display = ['tipo_evento', 'account', 'processado', 'timestamp']
    list_filter = ['tipo_evento', 'processado', 'timestamp']
    search_fields = ['tipo_evento', 'account__nome']
    readonly_fields = ['timestamp', 'payload', 'ip_origem', 'user_agent']
    
    fieldsets = (
        ('Informações do Webhook', {
            'fields': ('account', 'tipo_evento', 'processado')
        }),
        ('Dados da Requisição', {
            'fields': ('payload', 'ip_origem', 'user_agent'),
            'classes': ['collapse']
        }),
        ('Erro', {
            'fields': ('erro',),
            'classes': ['collapse']
        }),
        ('Timestamp', {
            'fields': ('timestamp',),
            'classes': ['collapse']
        }),
    )
    
    def has_add_permission(self, request):
        return False  # Logs são criados automaticamente
    
    def has_change_permission(self, request, obj=None):
        return False  # Logs são readonly