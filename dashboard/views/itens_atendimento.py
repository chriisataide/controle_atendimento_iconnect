"""
Views de itens de atendimento: APIs de produtos, itens e relatório financeiro.
"""
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg, F, ExpressionWrapper, DecimalField
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from decimal import Decimal
import logging

from ..models import Ticket

logger = logging.getLogger('dashboard')


@login_required
def api_produtos_ativos(request):
    """API para listar produtos ativos para seleção"""
    from ..models_estoque import Produto

    produtos = Produto.objects.filter(
        status='ativo'
    ).select_related('categoria', 'unidade_medida').order_by('nome')

    data = []
    for produto in produtos:
        data.append({
            'id': produto.id,
            'nome': produto.nome,
            'codigo': produto.codigo,
            'tipo': produto.tipo,
            'preco_venda': float(produto.preco_venda),
            'unidade_medida': produto.unidade_medida.sigla if produto.unidade_medida else 'un',
            'categoria': produto.categoria.nome if produto.categoria else '',
            'estoque_atual': float(produto.estoque_atual) if produto.controla_estoque else None,
        })

    return JsonResponse(data, safe=False)


@login_required
@require_http_methods(["POST"])
def api_add_item_atendimento(request):
    """API para adicionar item ao atendimento"""
    from ..models import ItemAtendimento
    from ..models_estoque import Produto

    try:
        ticket_id = request.POST.get('ticket_id')
        produto_id = request.POST.get('produto')
        quantidade = request.POST.get('quantidade', 1)
        valor_unitario = request.POST.get('valor_unitario')
        tipo_item = request.POST.get('tipo_item', 'produto')
        desconto_percentual = request.POST.get('desconto_percentual', 0)
        observacoes = request.POST.get('observacoes', '')

        ticket = get_object_or_404(Ticket, id=ticket_id)
        produto = get_object_or_404(Produto, id=produto_id)

        if ticket.status not in ['aberto', 'em_andamento']:
            return JsonResponse({
                'success': False,
                'message': 'Só é possível adicionar itens em tickets abertos ou em andamento'
            })

        quantidade_decimal = Decimal(str(quantidade))
        valor_unitario_decimal = Decimal(str(valor_unitario))
        desconto_percentual_decimal = Decimal(str(desconto_percentual))

        item_existente = ItemAtendimento.objects.filter(
            ticket=ticket,
            produto=produto
        ).first()

        if item_existente:
            item_existente.quantidade += quantidade_decimal
            item_existente.valor_unitario = valor_unitario_decimal
            item_existente.desconto_percentual = desconto_percentual_decimal
            item_existente.observacoes = observacoes
            item_existente.save()
        else:
            ItemAtendimento.objects.create(
                ticket=ticket,
                produto=produto,
                tipo_item=tipo_item,
                quantidade=quantidade_decimal,
                valor_unitario=valor_unitario_decimal,
                desconto_percentual=desconto_percentual_decimal,
                observacoes=observacoes,
                adicionado_por=request.user
            )

        return JsonResponse({'success': True, 'message': 'Item adicionado com sucesso'})

    except Exception:
        logger.exception('Erro em api_add_item_atendimento')
        return JsonResponse({'success': False, 'message': 'Erro interno do servidor'})


@login_required
def api_listar_itens_atendimento(request, ticket_id):
    """API para listar itens do atendimento"""
    from ..models import ItemAtendimento

    try:
        ticket = get_object_or_404(Ticket, id=ticket_id)
        itens = ItemAtendimento.objects.filter(ticket=ticket).select_related(
            'produto', 'produto__unidade_medida'
        ).order_by('adicionado_em')

        itens_data = []
        subtotal = Decimal('0')
        desconto_total = Decimal('0')

        for item in itens:
            item_data = {
                'id': item.id,
                'produto_nome': item.produto.nome,
                'produto_codigo': item.produto.codigo,
                'tipo_item': item.get_tipo_item_display(),
                'quantidade': float(item.quantidade),
                'valor_unitario': float(item.valor_unitario),
                'desconto_percentual': float(item.desconto_percentual),
                'valor_subtotal': float(item.valor_subtotal),
                'valor_desconto': float(item.valor_desconto),
                'valor_total': float(item.valor_total),
                'observacoes': item.observacoes,
                'unidade_medida': item.produto.unidade_medida.sigla if item.produto.unidade_medida else 'un',
                'adicionado_em': item.adicionado_em.strftime('%d/%m/%Y %H:%M'),
                'adicionado_por': item.adicionado_por.get_full_name() if item.adicionado_por else ''
            }
            itens_data.append(item_data)

            subtotal += item.valor_subtotal
            desconto_total += item.valor_desconto

        resumo = {
            'subtotal': float(subtotal),
            'desconto': float(desconto_total),
            'total': float(subtotal - desconto_total)
        }

        return JsonResponse({
            'success': True,
            'itens': itens_data,
            'resumo': resumo
        })

    except Exception:
        logger.exception('Erro em api_listar_itens_atendimento')
        return JsonResponse({'success': False, 'message': 'Erro interno do servidor'})


@login_required
@require_http_methods(["DELETE"])
def api_remover_item_atendimento(request, item_id):
    """API para remover item do atendimento"""
    from ..models import ItemAtendimento

    try:
        item = get_object_or_404(ItemAtendimento, id=item_id)

        if item.ticket.status not in ['em_andamento']:
            return JsonResponse({
                'success': False,
                'message': 'Só é possível remover itens de tickets que estão em andamento'
            })

        item.delete()

        return JsonResponse({'success': True, 'message': 'Item removido com sucesso'})

    except Exception:
        logger.exception('Erro em api_remover_item_atendimento')
        return JsonResponse({'success': False, 'message': 'Erro interno do servidor'})


@login_required
def relatorio_itens_atendimento(request):
    """Relatório de produtos e serviços mais utilizados"""
    from ..models import ItemAtendimento

    valor_total_expr = ExpressionWrapper(
        F('quantidade') * F('valor_unitario') * (1 - F('desconto_percentual') / 100),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    )

    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    categoria = request.GET.get('categoria')
    agente = request.GET.get('agente')

    queryset = ItemAtendimento.objects.select_related(
        'produto', 'produto__categoria', 'ticket', 'ticket__agente'
    )

    if data_inicio:
        queryset = queryset.filter(adicionado_em__date__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(adicionado_em__date__lte=data_fim)
    if categoria:
        queryset = queryset.filter(produto__categoria_id=categoria)
    if agente:
        queryset = queryset.filter(ticket__agente_id=agente)

    produtos_populares = queryset.values(
        'produto__nome', 'produto__codigo', 'tipo_item'
    ).annotate(
        total_quantidade=Sum('quantidade'),
        total_tickets=Count('ticket', distinct=True),
        valor_total=Sum(valor_total_expr),
        valor_medio=Avg(valor_total_expr)
    ).order_by('-total_quantidade')[:10]

    resumo_categorias = queryset.values(
        'produto__categoria__nome'
    ).annotate(
        total_quantidade=Sum('quantidade'),
        total_valor=Sum(valor_total_expr),
        total_itens=Count('id')
    ).order_by('-total_valor')

    resumo_agentes = queryset.values(
        'ticket__agente__first_name', 'ticket__agente__last_name'
    ).annotate(
        total_valor=Sum(valor_total_expr),
        total_tickets=Count('ticket', distinct=True),
        valor_medio_ticket=Avg(valor_total_expr)
    ).order_by('-total_valor')

    totais = queryset.aggregate(
        total_itens=Count('id'),
        total_valor=Sum(valor_total_expr),
        total_tickets=Count('ticket', distinct=True),
        valor_medio_item=Avg(valor_total_expr)
    )

    context = {
        'title': 'Relatório de Itens de Atendimento',
        'produtos_populares': produtos_populares,
        'resumo_categorias': resumo_categorias,
        'resumo_agentes': resumo_agentes,
        'totais': totais,
        'filtros': {
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'categoria': categoria,
            'agente': agente,
        }
    }

    return render(request, 'dashboard/relatorio_itens_atendimento.html', context)


@login_required
def api_estatisticas_financeiras_ticket(request, ticket_id):
    """API com estatísticas financeiras de um ticket"""
    from ..models import ItemAtendimento

    try:
        ticket = get_object_or_404(Ticket, id=ticket_id)
        itens = ItemAtendimento.objects.filter(ticket=ticket)

        estatisticas = itens.aggregate(
            subtotal=Sum('valor_subtotal'),
            desconto_total=Sum('valor_desconto'),
            total=Sum('valor_total'),
            quantidade_itens=Count('id')
        )

        for key, value in estatisticas.items():
            if value is None:
                estatisticas[key] = 0 if key != 'quantidade_itens' else 0

        detalhes_tipos = itens.values('tipo_item').annotate(
            quantidade=Count('id'),
            valor_total=Sum('valor_total')
        )

        return JsonResponse({
            'success': True,
            'estatisticas': estatisticas,
            'detalhes_tipos': list(detalhes_tipos),
            'tem_itens': itens.exists()
        })

    except Exception:
        logger.exception('Erro em api_estatisticas_itens_atendimento')
        return JsonResponse({'success': False, 'message': 'Erro interno do servidor'})
