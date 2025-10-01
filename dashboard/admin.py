from django.contrib import admin
from .models import Cliente, CategoriaTicket, Ticket, InteracaoTicket, PerfilAgente, PerfilUsuario

# Importar os admin do WhatsApp
from .whatsapp_admin import *


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'email', 'telefone', 'empresa', 'criado_em')
    list_filter = ('criado_em', 'empresa')
    search_fields = ('nome', 'email', 'telefone', 'empresa')
    readonly_fields = ('criado_em',)


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
