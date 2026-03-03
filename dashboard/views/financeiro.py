from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from ..utils.rbac import role_required
from django.http import JsonResponse
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.db import models, transaction
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Q
from decimal import Decimal
import logging

logger = logging.getLogger('dashboard')

# Import dos modelos financeiros
from ..models import (
    CategoriaFinanceira, FormaPagamento, Contrato, 
    Fatura, Pagamento, MovimentacaoFinanceira, RelatorioFinanceiro, CentroCusto
)


@login_required
@role_required('admin', 'gerente', 'financeiro')
def dashboard_financeiro(request):
    """Dashboard principal do módulo financeiro - integrado com chamados"""
    from datetime import date
    from django.db.models import Sum, Count, Avg, F, Q, ExpressionWrapper, DecimalField
    from django.db.models.functions import TruncMonth, TruncDate
    import json as _json

    from ..models import Ticket, ItemAtendimento

    hoje = date.today()
    mes_atual = hoje.month
    ano_atual = hoje.year

    # ── Expressão para valor_total de ItemAtendimento (property → DB expression) ──
    valor_total_expr = ExpressionWrapper(
        F('quantidade') * F('valor_unitario') * (1 - F('desconto_percentual') / 100),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    )

    # ── KPIs de Receita (baseado em chamados finalizados com itens) ──
    itens_mes = ItemAtendimento.objects.filter(
        ticket__fechado_em__month=mes_atual,
        ticket__fechado_em__year=ano_atual,
        ticket__status__in=['resolvido', 'fechado'],
    )
    receita_chamados_mes = itens_mes.aggregate(
        total=Sum(valor_total_expr)
    )['total'] or Decimal('0.00')

    itens_mes_anterior = ItemAtendimento.objects.filter(
        ticket__fechado_em__month=mes_atual - 1 if mes_atual > 1 else 12,
        ticket__fechado_em__year=ano_atual if mes_atual > 1 else ano_atual - 1,
        ticket__status__in=['resolvido', 'fechado'],
    )
    receita_mes_anterior = itens_mes_anterior.aggregate(
        total=Sum(valor_total_expr)
    )['total'] or Decimal('0.00')

    variacao_receita = ((receita_chamados_mes - receita_mes_anterior) / receita_mes_anterior * 100) if receita_mes_anterior else Decimal('0.00')

    # ── Chamados finalizados no mês ──
    tickets_finalizados_mes = Ticket.objects.filter(
        status__in=['resolvido', 'fechado'],
        fechado_em__month=mes_atual,
        fechado_em__year=ano_atual,
    ).count()

    # ── Ticket médio (valor médio por chamado finalizado) ──
    ticket_medio_valor = Ticket.objects.filter(
        status__in=['resolvido', 'fechado'],
        fechado_em__month=mes_atual,
        fechado_em__year=ano_atual,
    ).annotate(
        valor_ticket=Sum(
            ExpressionWrapper(
                F('itens_atendimento__quantidade') * F('itens_atendimento__valor_unitario') * (1 - F('itens_atendimento__desconto_percentual') / 100),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
    ).aggregate(media=Avg('valor_ticket'))['media'] or Decimal('0.00')

    # ── Total de produtos/serviços utilizados no mês ──
    total_itens_mes = itens_mes.count()

    # ── Valor em aberto (tickets abertos/em andamento com itens) ──
    valor_em_aberto = ItemAtendimento.objects.filter(
        ticket__status__in=['aberto', 'em_andamento', 'aguardando_cliente'],
    ).aggregate(total=Sum(valor_total_expr))['total'] or Decimal('0.00')

    # ── Contratos e Faturas ──
    contratos_ativos = Contrato.objects.filter(status='ativo').count()
    faturas_vencidas = Fatura.objects.filter(status='vencido').count()
    faturas_pendentes = Fatura.objects.filter(status='pendente').count()
    total_pendente = Fatura.objects.filter(
        status__in=['pendente', 'vencido'],
    ).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

    # ── Receita por categoria de chamado (últimos 3 meses) ──
    from django.utils import timezone
    tres_meses_atras = hoje - timezone.timedelta(days=90)
    receita_por_categoria = ItemAtendimento.objects.filter(
        ticket__status__in=['resolvido', 'fechado'],
        ticket__fechado_em__date__gte=tres_meses_atras,
    ).values(
        'ticket__categoria__nome'
    ).annotate(
        total=Sum(valor_total_expr)
    ).order_by('-total')[:6]
    cat_labels = [r['ticket__categoria__nome'] or 'Sem Categoria' for r in receita_por_categoria]
    cat_values = [float(r['total'] or 0) for r in receita_por_categoria]

    # ── Evolução mensal de receita de chamados (últimos 6 meses) ──
    seis_meses_atras = hoje.replace(day=1) - timezone.timedelta(days=180)
    evolucao_mensal = ItemAtendimento.objects.filter(
        ticket__status__in=['resolvido', 'fechado'],
        ticket__fechado_em__date__gte=seis_meses_atras,
    ).annotate(
        mes=TruncMonth('ticket__fechado_em')
    ).values('mes').annotate(
        total=Sum(valor_total_expr),
        qtd_tickets=Count('ticket', distinct=True)
    ).order_by('mes')
    evolucao_labels = [e['mes'].strftime('%b/%y') for e in evolucao_mensal] if evolucao_mensal else ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun']
    evolucao_valores = [float(e['total'] or 0) for e in evolucao_mensal] if evolucao_mensal else [0]*6
    evolucao_tickets = [e['qtd_tickets'] for e in evolucao_mensal] if evolucao_mensal else [0]*6

    # ── Top 10 produtos/serviços mais faturados ──
    top_produtos = ItemAtendimento.objects.filter(
        ticket__status__in=['resolvido', 'fechado'],
        ticket__fechado_em__month=mes_atual,
        ticket__fechado_em__year=ano_atual,
    ).values(
        'produto__nome', 'produto__codigo', 'tipo_item'
    ).annotate(
        total_faturado=Sum(valor_total_expr),
        quantidade_total=Sum('quantidade'),
        qtd_chamados=Count('ticket', distinct=True),
    ).order_by('-total_faturado')[:10]

    # ── Últimos chamados finalizados com valor ──
    ultimos_chamados = Ticket.objects.filter(
        status__in=['resolvido', 'fechado'],
    ).annotate(
        valor_total=Sum(
            ExpressionWrapper(
                F('itens_atendimento__quantidade') * F('itens_atendimento__valor_unitario') * (1 - F('itens_atendimento__desconto_percentual') / 100),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
    ).filter(valor_total__isnull=False).select_related(
        'cliente', 'agente', 'categoria'
    ).order_by('-fechado_em')[:10]

    # ── Top 5 clientes por faturamento ──
    top_clientes = ItemAtendimento.objects.filter(
        ticket__status__in=['resolvido', 'fechado'],
        ticket__fechado_em__month=mes_atual,
        ticket__fechado_em__year=ano_atual,
    ).values(
        'ticket__cliente__nome', 'ticket__cliente__empresa'
    ).annotate(
        total_faturado=Sum(valor_total_expr),
        qtd_chamados=Count('ticket', distinct=True),
    ).order_by('-total_faturado')[:5]

    context = {
        'title': 'Dashboard Financeiro',
        'page': 'financeiro_dashboard',
        # KPIs
        'receita_chamados_mes': receita_chamados_mes,
        'variacao_receita': variacao_receita,
        'tickets_finalizados_mes': tickets_finalizados_mes,
        'ticket_medio_valor': ticket_medio_valor,
        'total_itens_mes': total_itens_mes,
        'valor_em_aberto': valor_em_aberto,
        # Contratos/Faturas
        'contratos_ativos': contratos_ativos,
        'faturas_vencidas': faturas_vencidas,
        'faturas_pendentes': faturas_pendentes,
        'total_pendente': total_pendente,
        # Gráficos JSON
        'cat_labels_json': _json.dumps(cat_labels),
        'cat_values_json': _json.dumps(cat_values),
        'evolucao_labels_json': _json.dumps(evolucao_labels),
        'evolucao_valores_json': _json.dumps(evolucao_valores),
        'evolucao_tickets_json': _json.dumps(evolucao_tickets),
        # Tabelas
        'top_produtos': top_produtos,
        'ultimos_chamados': ultimos_chamados,
        'top_clientes': top_clientes,
    }
    return render(request, 'financeiro/dashboard.html', context)


@login_required
@role_required('admin', 'gerente', 'financeiro')
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
@role_required('admin', 'gerente', 'financeiro')
def faturas_lista(request):
    """Lista de faturas"""
    # Buscar faturas reais do banco
    faturas = Fatura.objects.select_related('contrato__cliente').all()

    # Agregar totais por status
    totais = Fatura.objects.aggregate(
        pagas=Sum('valor', filter=Q(status='pago')),
        pendentes=Sum('valor', filter=Q(status='pendente')),
        vencidas=Sum('valor', filter=Q(status='vencido')),
        total=Sum('valor'),
    )

    context = {
        'title': 'Faturas',
        'page': 'faturas',
        'faturas': faturas,
        'faturas_pagas_total': totais['pagas'] or Decimal('0.00'),
        'faturas_pendentes_total': totais['pendentes'] or Decimal('0.00'),
        'faturas_vencidas_total': totais['vencidas'] or Decimal('0.00'),
        'faturas_total': totais['total'] or Decimal('0.00'),
    }
    return render(request, 'financeiro/faturas_lista.html', context)


@login_required
@role_required('admin', 'gerente', 'financeiro')
def movimentacoes_lista(request):
    """Lista de movimentações financeiras"""
    import json as _json
    from django.db.models.functions import TruncMonth

    # Buscar movimentações reais do banco
    movimentacoes = MovimentacaoFinanceira.objects.select_related('categoria', 'usuario').all()

    # Agregar totais
    totais = MovimentacaoFinanceira.objects.aggregate(
        receitas=Sum('valor', filter=Q(tipo='receita')),
        despesas=Sum('valor', filter=Q(tipo='despesa')),
    )
    total_receitas = totais['receitas'] or Decimal('0.00')
    total_despesas = totais['despesas'] or Decimal('0.00')
    saldo = total_receitas - total_despesas
    resultado_pct = ((total_receitas - total_despesas) / total_despesas * 100) if total_despesas else Decimal('0.00')

    # Dados de fluxo de caixa mensal (últimos 6 meses)
    from datetime import date
    hoje = date.today()
    seis_meses_atras = hoje.replace(day=1) - timedelta(days=180)
    fluxo_mensal = (
        MovimentacaoFinanceira.objects
        .filter(data_movimentacao__gte=seis_meses_atras)
        .annotate(mes=TruncMonth('data_movimentacao'))
        .values('mes', 'tipo')
        .annotate(total=Sum('valor'))
        .order_by('mes')
    )
    meses_labels = []
    receitas_mensal = []
    despesas_mensal = []
    meses_map = {}
    for item in fluxo_mensal:
        mes_key = item['mes'].strftime('%b')
        if mes_key not in meses_map:
            meses_map[mes_key] = {'receita': 0, 'despesa': 0}
        meses_map[mes_key][item['tipo']] = float(item['total'])
    for mes_key, vals in meses_map.items():
        meses_labels.append(mes_key)
        receitas_mensal.append(vals['receita'])
        despesas_mensal.append(vals['despesa'])

    # Distribuição por categoria
    cat_data = (
        MovimentacaoFinanceira.objects
        .values('categoria__nome')
        .annotate(total=Sum('valor'))
        .order_by('-total')[:6]
    )
    cat_labels = [c['categoria__nome'] or 'Sem Categoria' for c in cat_data]
    cat_values = [float(c['total']) for c in cat_data]

    context = {
        'title': 'Movimentações',
        'page': 'movimentacoes',
        'movimentacoes': movimentacoes,
        'total_receitas': total_receitas,
        'total_despesas': total_despesas,
        'saldo': saldo,
        'resultado_pct': resultado_pct,
        'fluxo_labels_json': _json.dumps(meses_labels if meses_labels else ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun']),
        'fluxo_receitas_json': _json.dumps(receitas_mensal if receitas_mensal else [0, 0, 0, 0, 0, 0]),
        'fluxo_despesas_json': _json.dumps(despesas_mensal if despesas_mensal else [0, 0, 0, 0, 0, 0]),
        'cat_labels_json': _json.dumps(cat_labels if cat_labels else []),
        'cat_values_json': _json.dumps(cat_values if cat_values else []),
    }
    return render(request, 'financeiro/movimentacoes_lista.html', context)


@login_required
@role_required('admin', 'gerente', 'financeiro')
def relatorios_financeiros(request):
    """Página de relatórios financeiros"""
    import json as _json
    from django.db.models import Avg
    from django.db.models.functions import TruncMonth
    from datetime import date

    hoje = date.today()

    # Resumo executivo
    receita_total = MovimentacaoFinanceira.objects.filter(
        tipo='receita'
    ).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

    despesa_total = MovimentacaoFinanceira.objects.filter(
        tipo='despesa'
    ).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

    lucro_liquido = receita_total - despesa_total
    margem = (lucro_liquido / receita_total * 100) if receita_total else Decimal('0.00')

    valor_atraso = Fatura.objects.filter(
        status='vencido'
    ).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    pct_atraso = (valor_atraso / receita_total * 100) if receita_total else Decimal('0.00')

    # KPIs
    ticket_medio = Fatura.objects.filter(
        status='pago'
    ).aggregate(media=Avg('valor'))['media'] or Decimal('0.00')

    total_faturas = Fatura.objects.count()
    faturas_vencidas = Fatura.objects.filter(status='vencido').count()
    taxa_inadimplencia = (faturas_vencidas / total_faturas * 100) if total_faturas else 0

    # Top clientes por receita (baseado em faturas pagas)
    from ..models import Cliente
    top_clientes = (
        Fatura.objects
        .filter(status='pago')
        .values('contrato__cliente__nome')
        .annotate(receita=Sum('valor'))
        .order_by('-receita')[:10]
    )

    # Principais despesas por categoria
    top_despesas = (
        MovimentacaoFinanceira.objects
        .filter(tipo='despesa')
        .values('categoria__nome')
        .annotate(total=Sum('valor'))
        .order_by('-total')[:5]
    )

    # Dados para gráficos - evolução mensal (últimos 6 meses)
    seis_meses_atras = hoje.replace(day=1) - timedelta(days=180)
    evolucao = (
        MovimentacaoFinanceira.objects
        .filter(data_movimentacao__gte=seis_meses_atras)
        .annotate(mes=TruncMonth('data_movimentacao'))
        .values('mes', 'tipo')
        .annotate(total=Sum('valor'))
        .order_by('mes')
    )
    meses_map = {}
    for item in evolucao:
        mes_key = item['mes'].strftime('%b')
        if mes_key not in meses_map:
            meses_map[mes_key] = {'receita': 0, 'despesa': 0}
        meses_map[mes_key][item['tipo']] = float(item['total'])
    evolucao_labels = list(meses_map.keys()) if meses_map else ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun']
    evolucao_receitas = [meses_map[m]['receita'] for m in evolucao_labels] if meses_map else [0]*6
    evolucao_despesas = [meses_map[m]['despesa'] for m in evolucao_labels] if meses_map else [0]*6
    evolucao_lucro = [r - d for r, d in zip(evolucao_receitas, evolucao_despesas)]

    # Distribuição receitas por categoria
    dist_receitas = (
        MovimentacaoFinanceira.objects
        .filter(tipo='receita')
        .values('categoria__nome')
        .annotate(total=Sum('valor'))
        .order_by('-total')[:5]
    )
    dist_labels = [d['categoria__nome'] or 'Outros' for d in dist_receitas]
    dist_values = [float(d['total']) for d in dist_receitas]

    context = {
        'title': 'Relatórios Financeiros',
        'page': 'relatorios',
        'receita_total': receita_total,
        'despesa_total': despesa_total,
        'lucro_liquido': lucro_liquido,
        'margem': margem,
        'valor_atraso': valor_atraso,
        'pct_atraso': pct_atraso,
        'ticket_medio': ticket_medio,
        'taxa_inadimplencia': taxa_inadimplencia,
        'top_clientes': top_clientes,
        'top_despesas': top_despesas,
        'evolucao_labels_json': _json.dumps(evolucao_labels),
        'evolucao_receitas_json': _json.dumps(evolucao_receitas),
        'evolucao_despesas_json': _json.dumps(evolucao_despesas),
        'evolucao_lucro_json': _json.dumps(evolucao_lucro),
        'dist_labels_json': _json.dumps(dist_labels if dist_labels else []),
        'dist_values_json': _json.dumps(dist_values if dist_values else []),
    }
    return render(request, 'financeiro/relatorios.html', context)


@login_required
@role_required('admin', 'gerente', 'financeiro')
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
@role_required('admin', 'gerente', 'financeiro')
def api_gerar_relatorio(request):
    """API para gerar relatórios personalizados"""
    if request.method == 'POST':
        try:
            import json as _json
            from datetime import date, timedelta

            body = _json.loads(request.body) if request.content_type == 'application/json' else request.POST
            data_inicio_str = body.get('data_inicio')
            data_fim_str = body.get('data_fim')

            # Default: mês corrente
            hoje = date.today()
            if data_inicio_str:
                data_inicio = date.fromisoformat(data_inicio_str)
            else:
                data_inicio = hoje.replace(day=1)
            if data_fim_str:
                data_fim = date.fromisoformat(data_fim_str)
            else:
                data_fim = hoje

            movs = MovimentacaoFinanceira.objects.filter(
                data_movimentacao__range=[data_inicio, data_fim]
            )

            total_receitas = movs.filter(tipo='receita').aggregate(
                t=Sum('valor'))['t'] or Decimal('0.00')
            total_despesas = movs.filter(tipo='despesa').aggregate(
                t=Sum('valor'))['t'] or Decimal('0.00')
            saldo = total_receitas - total_despesas

            relatorio_data = {
                'periodo': f'{data_inicio.strftime("%d/%m/%Y")} - {data_fim.strftime("%d/%m/%Y")}',
                'total_receitas': str(total_receitas),
                'total_despesas': str(total_despesas),
                'saldo': str(saldo),
                'transacoes': movs.count(),
                'status': 'success'
            }

            return JsonResponse(relatorio_data)

        except Exception:
            logger.exception('Erro ao gerar relatório financeiro')
            return JsonResponse({'error': 'Erro ao gerar relatório'}, status=400)

    return JsonResponse({'error': 'Método não permitido'}, status=405)


# ========== VIEWS CENTRO DE CUSTOS ==========

@login_required
@role_required('admin', 'gerente', 'financeiro')
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
@role_required('admin', 'gerente', 'financeiro')
def centro_custo_create(request):
    """Criar novo centro de custo"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
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
            
        except Exception:
            logger.exception('Erro ao criar centro de custo')
            messages.error(request, 'Erro ao criar centro de custo. Verifique os dados e tente novamente.')
    
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
@role_required('admin', 'gerente', 'financeiro')
def centro_custo_detail(request, centro_id):
    """Detalhes do centro de custo"""
    from django.shortcuts import get_object_or_404
    from django.db.models import Sum, Count
    from datetime import datetime, timedelta
    
    centro_custo = get_object_or_404(CentroCusto, id=centro_id)
    
    # Estatísticas do mês atual
    _now = timezone.now()
    mes_atual = _now.month
    ano_atual = _now.year
    
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
@role_required('admin', 'gerente', 'financeiro')
def centro_custo_edit(request, centro_id):
    """Editar centro de custo"""
    from django.shortcuts import get_object_or_404, redirect
    
    centro_custo = get_object_or_404(CentroCusto, id=centro_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Re-fetch com lock dentro da transação
                centro_custo = CentroCusto.objects.select_for_update().get(id=centro_id)
                
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
            
        except Exception:
            logger.exception('Erro ao atualizar centro de custo')
            messages.error(request, 'Erro ao atualizar centro de custo. Verifique os dados e tente novamente.')
    
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
@role_required('admin', 'gerente', 'financeiro')
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
            movimentacoes__data_movimentacao__month=timezone.now().month,
            movimentacoes__data_movimentacao__year=timezone.now().year
        )) * 100 / models.F('orcamento_mensal')
    ).filter(percentual_usado__gte=models.F('alerta_percentual')).count()
    
    # Top 5 centros por gasto no mês
    _now2 = timezone.now()
    mes_atual = _now2.month
    ano_atual = _now2.year
    
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
@role_required('admin', 'gerente', 'financeiro')
def api_centros_custo_stats(request):
    """API para estatísticas dos centros de custo"""
    from django.db.models import Sum, Count, Q
    
    if request.method == 'GET':
        try:
            _now = timezone.now()
            mes_atual = _now.month
            ano_atual = _now.year
            
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
            
        except Exception:
            logger.exception('Erro ao gerar stats de centros de custo')
            return JsonResponse({'error': 'Erro ao processar dados'}, status=400)
    
    return JsonResponse({'error': 'Método não permitido'}, status=405)