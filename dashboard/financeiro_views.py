from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.db import models
from datetime import datetime, timedelta
from django.db.models import Sum, Count, Q
from decimal import Decimal

# Import dos modelos financeiros
from .models import (
    CategoriaFinanceira, FormaPagamento, Contrato, 
    Fatura, Pagamento, MovimentacaoFinanceira, RelatorioFinanceiro, CentroCusto
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


# ========== VIEWS CENTRO DE CUSTOS ==========

@login_required
def centros_custo_lista(request):
    """Lista de centros de custo"""
    centros_custo = CentroCusto.objects.select_related(
        'responsavel', 'gerente', 'centro_pai'
    ).prefetch_related('subcentros').all()
    
    context = {
        'title': 'Centros de Custo',
        'page': 'centros_custo',
        'centros_custo': centros_custo,
    }
    return render(request, 'financeiro/centros_custo_lista.html', context)


@login_required
def centro_custo_create(request):
    """Criar novo centro de custo"""
    if request.method == 'POST':
        try:
            # Processar dados do formulário
            centro_custo = CentroCusto.objects.create(
                codigo=request.POST.get('codigo'),
                nome=request.POST.get('nome'),
                descricao=request.POST.get('descricao', ''),
                departamento=request.POST.get('departamento'),
                orcamento_mensal=request.POST.get('orcamento_mensal', 0),
                orcamento_anual=request.POST.get('orcamento_anual', 0),
                status=request.POST.get('status', 'ativo'),
                criado_por=request.user
            )
            
            # Campos opcionais
            if request.POST.get('responsavel_id'):
                from django.contrib.auth.models import User
                centro_custo.responsavel = User.objects.get(id=request.POST.get('responsavel_id'))
            
            if request.POST.get('gerente_id'):
                from django.contrib.auth.models import User
                centro_custo.gerente = User.objects.get(id=request.POST.get('gerente_id'))
                
            if request.POST.get('centro_pai_id'):
                centro_custo.centro_pai = CentroCusto.objects.get(id=request.POST.get('centro_pai_id'))
            
            centro_custo.save()
            
            messages.success(request, f'Centro de custo "{centro_custo.nome}" criado com sucesso!')
            return redirect('financeiro:centros_custo_lista')
            
        except Exception as e:
            messages.error(request, f'Erro ao criar centro de custo: {str(e)}')
    
    # Dados para o formulário
    from django.contrib.auth.models import User
    usuarios = User.objects.filter(is_active=True).order_by('first_name', 'username')
    centros_pai = CentroCusto.objects.filter(status='ativo').order_by('codigo')
    
    context = {
        'title': 'Novo Centro de Custo',
        'page': 'centro_custo_create',
        'usuarios': usuarios,
        'centros_pai': centros_pai,
    }
    return render(request, 'financeiro/centro_custo_form.html', context)


@login_required
def centro_custo_detail(request, centro_id):
    """Detalhes do centro de custo"""
    from django.shortcuts import get_object_or_404
    from django.db.models import Sum, Count
    from datetime import datetime, timedelta
    
    centro_custo = get_object_or_404(CentroCusto, id=centro_id)
    
    # Estatísticas do mês atual
    mes_atual = datetime.now().month
    ano_atual = datetime.now().year
    
    movimentacoes_mes = centro_custo.movimentacoes.filter(
        data_movimentacao__month=mes_atual,
        data_movimentacao__year=ano_atual
    )
    
    total_despesas_mes = movimentacoes_mes.filter(tipo='despesa').aggregate(
        total=Sum('valor')
    )['total'] or 0
    
    total_receitas_mes = movimentacoes_mes.filter(tipo='receita').aggregate(
        total=Sum('valor')
    )['total'] or 0
    
    # Movimentações recentes
    movimentacoes_recentes = centro_custo.movimentacoes.order_by('-data_movimentacao')[:10]
    
    # Subcentros
    subcentros = centro_custo.subcentros.filter(status='ativo')
    
    context = {
        'title': f'Centro de Custo: {centro_custo.nome}',
        'page': 'centro_custo_detail',
        'centro_custo': centro_custo,
        'total_despesas_mes': total_despesas_mes,
        'total_receitas_mes': total_receitas_mes,
        'movimentacoes_recentes': movimentacoes_recentes,
        'subcentros': subcentros,
    }
    return render(request, 'financeiro/centro_custo_detail.html', context)


@login_required
def centro_custo_edit(request, centro_id):
    """Editar centro de custo"""
    from django.shortcuts import get_object_or_404, redirect
    
    centro_custo = get_object_or_404(CentroCusto, id=centro_id)
    
    if request.method == 'POST':
        try:
            # Atualizar dados
            centro_custo.codigo = request.POST.get('codigo')
            centro_custo.nome = request.POST.get('nome')
            centro_custo.descricao = request.POST.get('descricao', '')
            centro_custo.departamento = request.POST.get('departamento')
            centro_custo.orcamento_mensal = request.POST.get('orcamento_mensal', 0)
            centro_custo.orcamento_anual = request.POST.get('orcamento_anual', 0)
            centro_custo.status = request.POST.get('status')
            
            # Campos opcionais
            if request.POST.get('responsavel_id'):
                from django.contrib.auth.models import User
                centro_custo.responsavel = User.objects.get(id=request.POST.get('responsavel_id'))
            else:
                centro_custo.responsavel = None
            
            if request.POST.get('gerente_id'):
                from django.contrib.auth.models import User
                centro_custo.gerente = User.objects.get(id=request.POST.get('gerente_id'))
            else:
                centro_custo.gerente = None
                
            if request.POST.get('centro_pai_id'):
                centro_custo.centro_pai = CentroCusto.objects.get(id=request.POST.get('centro_pai_id'))
            else:
                centro_custo.centro_pai = None
            
            centro_custo.save()
            
            messages.success(request, f'Centro de custo "{centro_custo.nome}" atualizado com sucesso!')
            return redirect('financeiro:centro_custo_detail', centro_id=centro_custo.id)
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar centro de custo: {str(e)}')
    
    # Dados para o formulário
    from django.contrib.auth.models import User
    usuarios = User.objects.filter(is_active=True).order_by('first_name', 'username')
    centros_pai = CentroCusto.objects.filter(status='ativo').exclude(id=centro_custo.id).order_by('codigo')
    
    context = {
        'title': f'Editar Centro de Custo: {centro_custo.nome}',
        'page': 'centro_custo_edit',
        'centro_custo': centro_custo,
        'usuarios': usuarios,
        'centros_pai': centros_pai,
    }
    return render(request, 'financeiro/centro_custo_form.html', context)


@login_required
def centros_custo_dashboard(request):
    """Dashboard dos centros de custo"""
    from django.db.models import Sum, Count, Q
    from datetime import datetime, timedelta
    
    # Estatísticas gerais
    total_centros = CentroCusto.objects.filter(status='ativo').count()
    centros_com_alerta = CentroCusto.objects.filter(
        status='ativo',
        orcamento_mensal__gt=0
    ).annotate(
        percentual_usado=Sum('movimentacoes__valor', filter=Q(
            movimentacoes__tipo='despesa',
            movimentacoes__data_movimentacao__month=datetime.now().month,
            movimentacoes__data_movimentacao__year=datetime.now().year
        )) * 100 / models.F('orcamento_mensal')
    ).filter(percentual_usado__gte=models.F('alerta_percentual')).count()
    
    # Top 5 centros por gasto no mês
    mes_atual = datetime.now().month
    ano_atual = datetime.now().year
    
    top_gastos = CentroCusto.objects.filter(
        status='ativo'
    ).annotate(
        total_gasto=Sum('movimentacoes__valor', filter=Q(
            movimentacoes__tipo='despesa',
            movimentacoes__data_movimentacao__month=mes_atual,
            movimentacoes__data_movimentacao__year=ano_atual
        ))
    ).order_by('-total_gasto')[:5]
    
    # Centros por departamento
    departamentos = CentroCusto.objects.filter(
        status='ativo'
    ).values('departamento').annotate(
        total_centros=Count('id'),
        total_orcamento=Sum('orcamento_mensal')
    ).order_by('departamento')
    
    # Calcular orçamento total
    total_orcamento = CentroCusto.objects.filter(
        status='ativo'
    ).aggregate(
        total=Sum('orcamento_mensal')
    )['total'] or 0
    
    # Calcular gastos do mês atual
    total_gastos = CentroCusto.objects.filter(
        status='ativo'
    ).aggregate(
        total=Sum('movimentacoes__valor', filter=Q(
            movimentacoes__tipo='despesa',
            movimentacoes__data_movimentacao__month=mes_atual,
            movimentacoes__data_movimentacao__year=ano_atual
        ))
    )['total'] or 0
    
    # Calcular saldo disponível e percentual utilizado
    saldo_disponivel = total_orcamento - total_gastos
    percentual_utilizado = (total_gastos / total_orcamento * 100) if total_orcamento > 0 else 0
    
    # Contar centros por status
    centros_ativos = total_centros
    centros_suspensos = CentroCusto.objects.filter(status='suspenso').count()
    centros_inativos = CentroCusto.objects.filter(status='inativo').count()
    
    context = {
        'title': 'Dashboard Centros de Custo',
        'page': 'centros_custo_dashboard',
        'total_centros': total_centros,
        'centros_com_alerta': centros_com_alerta,
        'top_gastos': top_gastos,
        'departamentos': departamentos,
        'total_orcamento': total_orcamento,
        'total_gastos': total_gastos,
        'saldo_disponivel': saldo_disponivel,
        'percentual_utilizado': percentual_utilizado,
        'centros_ativos': centros_ativos,
        'centros_suspensos': centros_suspensos,
        'centros_inativos': centros_inativos,
    }
    return render(request, 'financeiro/centros_custo_dashboard.html', context)


# ========== APIs CENTRO DE CUSTOS ==========

@login_required
def api_centros_custo_stats(request):
    """API para estatísticas dos centros de custo"""
    from django.db.models import Sum, Count, Q
    from datetime import datetime
    
    if request.method == 'GET':
        try:
            mes_atual = datetime.now().month
            ano_atual = datetime.now().year
            
            # Dados por departamento
            stats_departamentos = []
            departamentos = CentroCusto.objects.filter(
                status='ativo'
            ).values_list('departamento', flat=True).distinct()
            
            for dept in departamentos:
                centros_dept = CentroCusto.objects.filter(
                    departamento=dept,
                    status='ativo'
                )
                
                total_orcamento = centros_dept.aggregate(
                    total=Sum('orcamento_mensal')
                )['total'] or 0
                
                total_gasto = MovimentacaoFinanceira.objects.filter(
                    centro_custo__in=centros_dept,
                    tipo='despesa',
                    data_movimentacao__month=mes_atual,
                    data_movimentacao__year=ano_atual
                ).aggregate(total=Sum('valor'))['total'] or 0
                
                stats_departamentos.append({
                    'departamento': dept,
                    'total_orcamento': float(total_orcamento),
                    'total_gasto': float(total_gasto),
                    'percentual_usado': (float(total_gasto) / float(total_orcamento) * 100) if total_orcamento > 0 else 0
                })
            
            return JsonResponse({
                'departamentos': stats_departamentos,
                'status': 'success'
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Método não permitido'}, status=405)