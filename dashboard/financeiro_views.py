from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from datetime import datetime, timedelta
from django.db.models import Sum, Count
from decimal import Decimal

# Import dos modelos financeiros
from .models import (
    CategoriaFinanceira, FormaPagamento, Contrato, 
    Fatura, Pagamento, MovimentacaoFinanceira, RelatorioFinanceiro
)


@login_required
def dashboard_financeiro(request):
    """Dashboard principal do módulo financeiro"""
    context = {
        'title': 'Dashboard Financeiro',
        'page': 'financeiro_dashboard',
        # Dados placeholder - substituir por dados reais
        'total_receitas': Decimal('15750.00'),
        'total_despesas': Decimal('8230.00'),
        'total_pendente': Decimal('3420.00'),
        'contratos_ativos': 25,
        'faturas_vencidas': 5,
        'ticket_medio': Decimal('630.00'),
    }
    return render(request, 'financeiro/dashboard.html', context)


@login_required
def contratos_lista(request):
    """Lista de contratos"""
    # Buscar contratos reais do banco
    contratos = Contrato.objects.select_related('cliente').all()
    
    context = {
        'title': 'Contratos',
        'page': 'contratos',
        'contratos': contratos,
    }
    return render(request, 'financeiro/contratos_lista.html', context)


@login_required
def faturas_lista(request):
    """Lista de faturas"""
    # Buscar faturas reais do banco
    faturas = Fatura.objects.select_related('contrato__cliente').all()
    
    context = {
        'title': 'Faturas',
        'page': 'faturas',
        'faturas': faturas,
    }
    return render(request, 'financeiro/faturas_lista.html', context)


@login_required
def movimentacoes_lista(request):
    """Lista de movimentações financeiras"""
    # Buscar movimentações reais do banco
    movimentacoes = MovimentacaoFinanceira.objects.select_related('categoria', 'usuario').all()
    
    context = {
        'title': 'Movimentações',
        'page': 'movimentacoes',
        'movimentacoes': movimentacoes,
    }
    return render(request, 'financeiro/movimentacoes_lista.html', context)


@login_required
def relatorios_financeiros(request):
    """Página de relatórios financeiros"""
    context = {
        'title': 'Relatórios Financeiros',
        'page': 'relatorios',
    }
    return render(request, 'financeiro/relatorios.html', context)


@login_required
def api_movimentacoes(request):
    """API para retornar movimentações em JSON"""
    if request.method == 'GET':
        movimentacoes = MovimentacaoFinanceira.objects.select_related('categoria', 'usuario')
        
        data = []
        for mov in movimentacoes:
            data.append({
                'id': mov.id,
                'descricao': mov.descricao,
                'tipo': mov.get_tipo_display(),
                'valor': str(mov.valor),
                'data': mov.data_movimentacao.strftime('%d/%m/%Y'),
                'categoria': mov.categoria.nome,
                'usuario': mov.usuario.get_full_name() or mov.usuario.username,
            })
        
        return JsonResponse({'movimentacoes': data})
    
    return JsonResponse({'error': 'Método não permitido'}, status=405)


@login_required
def api_gerar_relatorio(request):
    """API para gerar relatórios personalizados"""
    if request.method == 'POST':
        try:
            # Aqui implementar a lógica de geração de relatórios
            # Por enquanto retorna dados placeholder
            
            relatorio_data = {
                'periodo': '01/09/2025 - 17/09/2025',
                'total_receitas': '15750.00',
                'total_despesas': '8230.00',
                'saldo': '7520.00',
                'transacoes': 47,
                'status': 'success'
            }
            
            return JsonResponse(relatorio_data)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Método não permitido'}, status=405)