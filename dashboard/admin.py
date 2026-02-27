from django.contrib import admin
from .models import Cliente, CategoriaTicket, Ticket, InteracaoTicket, PerfilAgente, PerfilUsuario
from .models import (
    Equipamento, HistoricoEquipamento, AlertaEquipamento,
    ConfiguracaoAlertaEquipamento
)

# Importar os admin do WhatsApp
from .whatsapp_admin import *


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'segmento', 'email', 'telefone', 'ativo', 'criado_em')
    list_filter = ('ativo', 'segmento', 'criado_em')
    search_fields = ('nome', 'email', 'telefone', 'segmento')
    readonly_fields = ('criado_em', 'atualizado_em')
    list_editable = ('ativo',)


@admin.register(CategoriaTicket)
class CategoriaTicketAdmin(admin.ModelAdmin):
    list_display = ('nome', 'descricao', 'cor')
    search_fields = ('nome',)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('numero', 'titulo', 'cliente', 'agente', 'categoria', 'status', 'prioridade', 'criado_em')
    list_filter = ('status', 'prioridade', 'categoria', 'criado_em', 'agente')
    search_fields = ('numero', 'titulo', 'cliente__nome', 'cliente__email')
    readonly_fields = ('numero', 'criado_em', 'atualizado_em', 'resolvido_em', 'fechado_em')
    
    fieldsets = (
        (None, {
            'fields': ('numero', 'titulo', 'descricao', 'cliente', 'categoria')
        }),
        ('Atribuição', {
            'fields': ('agente', 'status', 'prioridade')
        }),
        ('Timestamps', {
            'fields': ('criado_em', 'atualizado_em', 'resolvido_em', 'fechado_em'),
            'classes': ('collapse',)
        })
    )


@admin.register(InteracaoTicket)
class InteracaoTicketAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'usuario', 'eh_publico', 'criado_em')
    list_filter = ('eh_publico', 'criado_em', 'usuario')
    search_fields = ('ticket__numero', 'usuario__username', 'mensagem')
    readonly_fields = ('criado_em',)


@admin.register(PerfilAgente)
class PerfilAgenteAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'max_tickets_simultaneos', 'tickets_ativos')
    list_filter = ('status',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    filter_horizontal = ('especialidades',)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'telefone', 'cidade', 'estado', 'cargo', 'departamento', 'perfil_completo_percentual')
    list_filter = ('departamento', 'estado', 'criado_em')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email', 'telefone', 'cargo')
    readonly_fields = ('criado_em', 'atualizado_em', 'perfil_completo_percentual')
    
    fieldsets = (
        ('Usuário', {
            'fields': ('user',)
        }),
        ('Informações de Contato', {
            'fields': ('telefone', 'telefone_alternativo')
        }),
        ('Endereço', {
            'fields': ('endereco', 'cidade', 'estado', 'cep')
        }),
        ('Informações Profissionais', {
            'fields': ('cargo', 'departamento', 'bio')
        }),
        ('Avatar', {
            'fields': ('avatar',)
        }),
        ('Metadados', {
            'fields': ('perfil_completo_percentual', 'criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        })
    )


# =========================================================================
# EQUIPAMENTOS / ATIVOS
# =========================================================================

class HistoricoEquipamentoInline(admin.TabularInline):
    model = HistoricoEquipamento
    fk_name = 'equipamento'
    extra = 0
    readonly_fields = ('realizado_em', 'realizado_por')
    fields = (
        'tipo_movimentacao', 'pdv_anterior', 'pdv_novo',
        'equipamento_substituido', 'ticket', 'motivo', 'realizado_em', 'realizado_por'
    )


class AlertaEquipamentoInline(admin.TabularInline):
    model = AlertaEquipamento
    extra = 0
    readonly_fields = ('criado_em', 'resolvido_em', 'resolvido_por')
    fields = ('tipo', 'severidade', 'titulo', 'valor_atual', 'limiar', 'resolvido', 'criado_em')


@admin.register(Equipamento)
class EquipamentoAdmin(admin.ModelAdmin):
    list_display = (
        'numero_serie', 'tipo', 'marca', 'modelo', 'ponto_de_venda',
        'status', 'total_chamados', 'total_trocas', 'data_instalacao'
    )
    list_filter = ('status', 'tipo', 'criado_em')
    search_fields = ('numero_serie', 'modelo', 'marca', 'tipo', 'patrimonio', 'ponto_de_venda__nome_fantasia')
    readonly_fields = ('criado_em', 'atualizado_em', 'total_chamados', 'total_trocas')
    list_select_related = ('ponto_de_venda', 'ponto_de_venda__cliente')
    inlines = [HistoricoEquipamentoInline, AlertaEquipamentoInline]

    fieldsets = (
        ('Identificação', {
            'fields': ('numero_serie', 'tipo', 'marca', 'modelo', 'patrimonio', 'descricao')
        }),
        ('Localização', {
            'fields': ('ponto_de_venda', 'local_instalacao')
        }),
        ('Status e Datas', {
            'fields': ('status', 'data_instalacao', 'data_garantia', 'data_desativacao')
        }),
        ('Contadores', {
            'fields': ('total_chamados', 'total_trocas'),
            'classes': ('collapse',)
        }),
        ('Observações', {
            'fields': ('observacoes',)
        }),
        ('Auditoria', {
            'fields': ('criado_por', 'criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )


@admin.register(HistoricoEquipamento)
class HistoricoEquipamentoAdmin(admin.ModelAdmin):
    list_display = ('equipamento', 'tipo_movimentacao', 'pdv_anterior', 'pdv_novo', 'realizado_em', 'realizado_por')
    list_filter = ('tipo_movimentacao', 'realizado_em')
    search_fields = ('equipamento__numero_serie', 'equipamento__modelo', 'motivo')
    readonly_fields = ('realizado_em',)
    list_select_related = ('equipamento', 'pdv_anterior', 'pdv_novo', 'realizado_por')


@admin.register(AlertaEquipamento)
class AlertaEquipamentoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'equipamento', 'tipo', 'severidade', 'valor_atual', 'limiar', 'resolvido', 'criado_em')
    list_filter = ('tipo', 'severidade', 'resolvido', 'criado_em')
    search_fields = ('titulo', 'descricao', 'equipamento__numero_serie')
    readonly_fields = ('criado_em', 'resolvido_em', 'resolvido_por')
    list_select_related = ('equipamento',)


@admin.register(ConfiguracaoAlertaEquipamento)
class ConfiguracaoAlertaEquipamentoAdmin(admin.ModelAdmin):
    list_display = (
        'chamados_limiar', 'chamados_periodo_dias',
        'trocas_limiar', 'trocas_periodo_dias',
        'garantia_dias_aviso', 'ativo', 'atualizado_em'
    )
    readonly_fields = ('atualizado_em',)
