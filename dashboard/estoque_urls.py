"""
URLs para Sistema de Controle de Estoque
"""
from django.urls import path
from . import estoque_views

app_name = 'estoque'

urlpatterns = [
    # Dashboard principal
    path('', estoque_views.estoque_dashboard, name='dashboard'),
    
    # ========== PRODUTOS ==========
    path('produtos/', estoque_views.ProdutoListView.as_view(), name='produto_list'),
    path('produtos/novo/', estoque_views.ProdutoCreateView.as_view(), name='produto_create'),
    path('produtos/<int:pk>/', estoque_views.ProdutoDetailView.as_view(), name='produto_detail'),
    path('produtos/<int:pk>/editar/', estoque_views.ProdutoUpdateView.as_view(), name='produto_update'),
    
    # ========== MOVIMENTAÇÕES ==========
    path('movimentacoes/', estoque_views.MovimentacaoListView.as_view(), name='movimentacao_list'),
    path('movimentacoes/nova/', estoque_views.movimentacao_create, name='movimentacao_create'),
    
    # ========== RELATÓRIOS ==========
    path('relatorios/', estoque_views.relatorios_index, name='relatorios'),
    path('relatorios/estoque/', estoque_views.relatorio_estoque, name='relatorio_estoque'),
    path('relatorios/movimentacoes/', estoque_views.relatorio_movimentacoes, name='relatorio_movimentacoes'),
    
    # ========== APIs AJAX ==========
    path('api/produto/<int:produto_id>/', estoque_views.api_produto_info, name='api_produto_info'),
    path('api/alertas/', estoque_views.api_alertas_estoque, name='api_alertas_estoque'),
    path('api/alertas/<int:alerta_id>/resolver/', estoque_views.api_resolver_alerta, name='api_resolver_alerta'),
]