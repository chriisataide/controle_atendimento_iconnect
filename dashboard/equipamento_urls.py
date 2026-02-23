"""
URLs para Gestão de Equipamentos / Ativos (Asset Management).
"""
from django.urls import path
from . import equipamento_views

app_name = 'equipamentos'

urlpatterns = [
    # Dashboard principal
    path('', equipamento_views.equipamento_dashboard, name='dashboard'),

    # ========== EQUIPAMENTOS ==========
    path('lista/', equipamento_views.EquipamentoListView.as_view(), name='equipamento_list'),
    path('novo/', equipamento_views.equipamento_create, name='equipamento_create'),
    path('<int:pk>/', equipamento_views.EquipamentoDetailView.as_view(), name='equipamento_detail'),
    path('<int:pk>/editar/', equipamento_views.equipamento_update, name='equipamento_update'),

    # ========== MOVIMENTAÇÕES ==========
    path('<int:pk>/movimentacao/', equipamento_views.registrar_movimentacao, name='registrar_movimentacao'),

    # ========== ALERTAS ==========
    path('alertas/', equipamento_views.alerta_list, name='alerta_list'),
    path('alertas/<int:pk>/resolver/', equipamento_views.alerta_resolver, name='alerta_resolver'),

    # ========== RELATÓRIO POR CLIENTE ==========
    path('cliente/<int:cliente_id>/', equipamento_views.equipamentos_por_cliente, name='equipamentos_cliente'),

    # ========== APIs AJAX ==========
    path('api/cliente/<int:cliente_id>/', equipamento_views.api_equipamentos_cliente, name='api_equipamentos_cliente'),
    path('api/stats/', equipamento_views.api_dashboard_stats, name='api_dashboard_stats'),
]
