from django.urls import path
from . import financeiro_views

app_name = 'financeiro'

urlpatterns = [
    # Dashboard Financeiro
    path('', financeiro_views.dashboard_financeiro, name='dashboard_financeiro'),
    
    # Contratos
    path('contratos/', financeiro_views.contratos_lista, name='contratos_lista'),
    
    # Faturas
    path('faturas/', financeiro_views.faturas_lista, name='faturas_lista'),
    
    # Movimentações
    path('movimentacoes/', financeiro_views.movimentacoes_lista, name='movimentacoes_lista'),
    
    # Centros de Custo
    path('centros-custo/', financeiro_views.centros_custo_lista, name='centros_custo_lista'),
    path('centros-custo/dashboard/', financeiro_views.centros_custo_dashboard, name='centros_custo_dashboard'),
    path('centros-custo/novo/', financeiro_views.centro_custo_create, name='centro_custo_create'),
    path('centros-custo/<int:centro_id>/', financeiro_views.centro_custo_detail, name='centro_custo_detail'),
    path('centros-custo/<int:centro_id>/editar/', financeiro_views.centro_custo_edit, name='centro_custo_edit'),
    
    # Relatórios
    path('relatorios/', financeiro_views.relatorios_financeiros, name='relatorios_financeiros'),
    
    # APIs
    path('api/movimentacoes/', financeiro_views.api_movimentacoes, name='api_movimentacoes'),
    path('api/relatorio/', financeiro_views.api_gerar_relatorio, name='api_gerar_relatorio'),
    path('api/centros-custo/stats/', financeiro_views.api_centros_custo_stats, name='api_centros_custo_stats'),
]