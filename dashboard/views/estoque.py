"""
Views para Sistema de Controle de Estoque
Integrado ao Sistema iConnect
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from ..utils.rbac import role_required
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count, F, Avg
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import json
import logging

from ..models.estoque import (
    Produto, CategoriaEstoque, Fornecedor, UnidadeMedida,
    MovimentacaoEstoque, TipoMovimentacao, EstoqueAlerta
)
from ..models import Ticket

logger = logging.getLogger('dashboard')


# ========== DASHBOARD PRINCIPAL DE ESTOQUE ==========

@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def estoque_dashboard(request):
    """Dashboard principal do módulo de estoque"""
    from ..models import ItemAtendimento
    
    # Métricas principais
    total_produtos = Produto.objects.filter(status='ativo').count()
    produtos_criticos = Produto.objects.filter(
        controla_estoque=True,
        estoque_atual__lte=F('estoque_minimo')
    ).count()
    valor_total_estoque = Produto.objects.filter(
        status='ativo',
        controla_estoque=True
    ).aggregate(
        total=Sum(F('estoque_atual') * F('preco_custo'))
    )['total'] or 0
    
    # Movimentações hoje
    hoje = timezone.now().date()
    movimentacoes_hoje = MovimentacaoEstoque.objects.filter(
        data_movimentacao__date=hoje
    ).count()
    
    # Produtos mais movimentados (últimos 30 dias)
    data_inicio = timezone.now() - timedelta(days=30)
    produtos_mais_movimentados = MovimentacaoEstoque.objects.filter(
        data_movimentacao__gte=data_inicio
    ).values(
        'produto__nome', 'produto__codigo'
    ).annotate(
        total_movimentacoes=Count('id'),
        quantidade_total=Sum('quantidade')
    ).order_by('-total_movimentacoes')[:5]
    
    # Alertas não resolvidos
    alertas_pendentes = EstoqueAlerta.objects.filter(resolvido=False).count()
    
    # Gráfico de movimentações por dia (últimos 7 dias)
    movimentacoes_por_dia = []
    for i in range(7):
        data = timezone.now().date() - timedelta(days=i)
        entradas = MovimentacaoEstoque.objects.filter(
            data_movimentacao__date=data,
            tipo_operacao='entrada'
        ).count()
        saidas = MovimentacaoEstoque.objects.filter(
            data_movimentacao__date=data,
            tipo_operacao='saida'
        ).count()
        movimentacoes_por_dia.append({
            'data': data.strftime('%d/%m'),
            'entradas': entradas,
            'saidas': saidas
        })
    
    movimentacoes_por_dia.reverse()
    
    # ── Dados de consumo via atendimentos ──
    from django.db.models import ExpressionWrapper, DecimalField
    from django.db.models.functions import TruncMonth
    from datetime import date
    
    mes_atual = hoje.month
    ano_atual = hoje.year
    
    # Consumo de estoque em atendimentos (mês)
    consumo_atendimentos_mes = ItemAtendimento.objects.filter(
        tipo_item='produto',
        adicionado_em__month=mes_atual,
        adicionado_em__year=ano_atual,
    ).aggregate(
        total_itens=Count('id'),
        total_quantidade=Sum('quantidade'),
    )
    
    # Top 10 produtos consumidos em atendimentos (mês)
    top_consumo_atendimentos = ItemAtendimento.objects.filter(
        tipo_item='produto',
        adicionado_em__month=mes_atual,
        adicionado_em__year=ano_atual,
    ).values(
        'produto__nome', 'produto__codigo', 'produto__estoque_atual',
        'produto__unidade_medida__sigla'
    ).annotate(
        qtd_consumida=Sum('quantidade'),
        qtd_chamados=Count('ticket', distinct=True),
    ).order_by('-qtd_consumida')[:10]
    
    # Últimas movimentações de atendimento
    ultimas_mov_atendimento = MovimentacaoEstoque.objects.filter(
        ticket_relacionado__isnull=False,
    ).select_related(
        'produto', 'ticket_relacionado', 'usuario'
    ).order_by('-data_movimentacao')[:10]
    
    # Produtos com estoque crítico (lista)
    lista_criticos = Produto.objects.filter(
        controla_estoque=True,
        estoque_atual__lte=F('estoque_minimo'),
        status='ativo'
    ).select_related('categoria', 'unidade_medida').order_by('estoque_atual')[:10]
    
    context = {
        'title': 'Dashboard de Estoque',
        'current_page': 'estoque_dashboard',
        'total_produtos': total_produtos,
        'produtos_criticos': produtos_criticos,
        'valor_total_estoque': valor_total_estoque,
        'movimentacoes_hoje': movimentacoes_hoje,
        'produtos_mais_movimentados': produtos_mais_movimentados,
        'alertas_pendentes': alertas_pendentes,
        'movimentacoes_por_dia': json.dumps(movimentacoes_por_dia),
        # Novos dados de atendimentos
        'consumo_atendimentos_mes': consumo_atendimentos_mes,
        'top_consumo_atendimentos': top_consumo_atendimentos,
        'ultimas_mov_atendimento': ultimas_mov_atendimento,
        'lista_criticos': lista_criticos,
    }
    
    return render(request, 'estoque/dashboard.html', context)


# ========== PRODUTOS ==========

@method_decorator([login_required, role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')], name='dispatch')
class ProdutoListView(ListView):
    model = Produto
    template_name = 'estoque/produto_list.html'
    context_object_name = 'produtos'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Produto.objects.select_related('categoria', 'fornecedor_principal', 'unidade_medida')
        
        # Filtros
        search = self.request.GET.get('search')
        categoria = self.request.GET.get('categoria')
        status = self.request.GET.get('status')
        estoque_critico = self.request.GET.get('estoque_critico')
        
        if search:
            queryset = queryset.filter(
                Q(nome__icontains=search) |
                Q(codigo__icontains=search) |
                Q(codigo_barras__icontains=search)
            )
        
        if categoria:
            queryset = queryset.filter(categoria_id=categoria)
        
        if status:
            queryset = queryset.filter(status=status)
        
        if estoque_critico == 'true':
            queryset = queryset.filter(
                controla_estoque=True,
                estoque_atual__lte=F('estoque_minimo')
            )
        
        return queryset.order_by('nome')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Produtos'
        context['current_page'] = 'estoque_produtos'
        context['categorias'] = CategoriaEstoque.objects.filter(ativo=True)
        context['search'] = self.request.GET.get('search', '')
        context['categoria_selected'] = self.request.GET.get('categoria', '')
        context['status_selected'] = self.request.GET.get('status', '')
        context['estoque_critico'] = self.request.GET.get('estoque_critico', '')
        return context


@method_decorator([login_required, role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')], name='dispatch')
class ProdutoDetailView(DetailView):
    model = Produto
    template_name = 'estoque/produto_detail.html'
    context_object_name = 'produto'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Produto: {self.object.nome}'
        context['current_page'] = 'estoque_produtos'
        
        # Últimas movimentações
        context['movimentacoes'] = MovimentacaoEstoque.objects.filter(
            produto=self.object
        ).select_related('usuario', 'fornecedor', 'tipo_movimentacao').order_by('-data_movimentacao')[:10]
        
        # Tickets relacionados
        context['tickets_relacionados'] = Ticket.objects.filter(
            movimentacaoestoque__produto=self.object
        ).distinct()[:5]
        
        return context


@method_decorator([login_required, role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')], name='dispatch')
class ProdutoCreateView(CreateView):
    model = Produto
    template_name = 'estoque/produto_form.html'
    fields = [
        'nome', 'descricao', 'categoria', 'fornecedor_principal', 'unidade_medida',
        'preco_custo', 'preco_venda', 'controla_estoque', 'estoque_minimo', 'estoque_maximo',
        'localizacao', 'peso', 'altura', 'largura', 'profundidade', 'observacoes'
    ]
    success_url = reverse_lazy('estoque:produto_list')
    
    def form_valid(self, form):
        form.instance.criado_por = self.request.user
        messages.success(self.request, 'Produto criado com sucesso!')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Novo Produto'
        context['current_page'] = 'estoque_produtos'
        return context


@method_decorator([login_required, role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')], name='dispatch')
class ProdutoUpdateView(UpdateView):
    model = Produto
    template_name = 'estoque/produto_form.html'
    fields = [
        'nome', 'descricao', 'categoria', 'fornecedor_principal', 'unidade_medida',
        'preco_custo', 'preco_venda', 'controla_estoque', 'estoque_minimo', 'estoque_maximo',
        'localizacao', 'status', 'peso', 'altura', 'largura', 'profundidade', 'observacoes'
    ]
    
    def get_success_url(self):
        return reverse_lazy('estoque:produto_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, 'Produto atualizado com sucesso!')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Editar: {self.object.nome}'
        context['current_page'] = 'estoque_produtos'
        return context


# ========== MOVIMENTAÇÕES ==========

@method_decorator([login_required, role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')], name='dispatch')
class MovimentacaoListView(ListView):
    model = MovimentacaoEstoque
    template_name = 'estoque/movimentacao_list.html'
    context_object_name = 'movimentacoes'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = MovimentacaoEstoque.objects.select_related(
            'produto', 'usuario', 'fornecedor', 'tipo_movimentacao'
        )
        
        # Filtros
        produto = self.request.GET.get('produto')
        tipo_operacao = self.request.GET.get('tipo_operacao')
        data_inicio = self.request.GET.get('data_inicio')
        data_fim = self.request.GET.get('data_fim')
        
        if produto:
            queryset = queryset.filter(produto_id=produto)
        
        if tipo_operacao:
            queryset = queryset.filter(tipo_operacao=tipo_operacao)
        
        if data_inicio:
            queryset = queryset.filter(data_movimentacao__date__gte=data_inicio)
        
        if data_fim:
            queryset = queryset.filter(data_movimentacao__date__lte=data_fim)
        
        return queryset.order_by('-data_movimentacao')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Movimentações de Estoque'
        context['current_page'] = 'estoque_movimentacoes'
        context['produtos'] = Produto.objects.filter(status='ativo').order_by('nome')
        
        # Totais para KPIs
        qs = self.get_queryset()
        context['total_entradas'] = qs.filter(tipo_operacao='entrada').aggregate(
            total=Count('id'), valor=Sum('valor_total'))
        context['total_saidas'] = qs.filter(tipo_operacao='saida').aggregate(
            total=Count('id'), valor=Sum('valor_total'))
        context['total_movimentacoes'] = qs.count()
        context['movimentacoes_hoje'] = qs.filter(
            data_movimentacao__date=timezone.now().date()).count()
        return context


@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def movimentacao_create(request):
    """Criar nova movimentação de estoque"""
    if request.method == 'POST':
        produto_id = request.POST.get('produto')
        tipo_movimentacao_id = request.POST.get('tipo_movimentacao')
        fornecedor_id = request.POST.get('fornecedor') or None
        observacoes = request.POST.get('observacoes', '')
        numero_documento = request.POST.get('numero_documento', '')
        
        try:
            quantidade = Decimal(request.POST.get('quantidade', '0'))
            valor_unitario = Decimal(request.POST.get('valor_unitario', '0'))
        except (InvalidOperation, ValueError):
            messages.error(request, 'Valores numéricos inválidos.')
            return redirect('estoque:movimentacao_create')
        
        if quantidade <= 0:
            messages.error(request, 'A quantidade deve ser maior que zero.')
            return redirect('estoque:movimentacao_create')
        
        try:
            with transaction.atomic():
                # Lock do produto para evitar race condition
                produto = Produto.objects.select_for_update().get(id=produto_id)
                tipo_movimentacao = TipoMovimentacao.objects.get(id=tipo_movimentacao_id)
                
                # Validar estoque para saídas — DENTRO da transação com lock
                if tipo_movimentacao.tipo_operacao == 'saida':
                    if produto.estoque_atual < quantidade and not produto.categoria.permite_estoque_negativo:
                        messages.error(request, 'Estoque insuficiente para esta saída!')
                        return redirect('estoque:movimentacao_create')
                
                movimentacao = MovimentacaoEstoque.objects.create(
                    produto=produto,
                    tipo_movimentacao=tipo_movimentacao,
                    tipo_operacao=tipo_movimentacao.tipo_operacao,
                    quantidade=quantidade,
                    valor_unitario=valor_unitario,
                    fornecedor_id=fornecedor_id,
                    observacoes=observacoes,
                    numero_documento=numero_documento,
                    usuario=request.user
                )
            
            messages.success(request, f'Movimentação {movimentacao.numero} criada com sucesso!')
            return redirect('estoque:movimentacao_list')
            
        except Produto.DoesNotExist:
            messages.error(request, 'Produto não encontrado.')
        except TipoMovimentacao.DoesNotExist:
            messages.error(request, 'Tipo de movimentação não encontrado.')
        except ValueError as e:
            messages.error(request, str(e))
        except Exception:
            logger.exception('Erro ao criar movimentação de estoque')
            messages.error(request, 'Erro interno ao criar movimentação. Tente novamente.')
    
    context = {
        'title': 'Nova Movimentação',
        'current_page': 'estoque_movimentacoes',
        'produtos': Produto.objects.filter(status='ativo', controla_estoque=True).order_by('nome'),
        'tipos_movimentacao': TipoMovimentacao.objects.filter(ativo=True).order_by('nome'),
        'fornecedores': Fornecedor.objects.filter(ativo=True).order_by('nome'),
    }
    
    return render(request, 'estoque/movimentacao_form.html', context)


# ========== RELATÓRIOS ==========

@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def relatorios_index(request):
    """Página unificada de relatórios"""
    
    tipo_relatorio = request.GET.get('tipo', 'estoque')
    
    context = {
        'title': 'Relatórios de Estoque',
        'current_page': 'estoque_relatorios',
        'tipo_relatorio': tipo_relatorio,
    }
    
    # Dados para relatório de estoque
    if tipo_relatorio == 'estoque':
        # Filtros
        categoria = request.GET.get('categoria')
        apenas_criticos = request.GET.get('apenas_criticos') == 'true'
        
        queryset = Produto.objects.filter(
            status='ativo',
            controla_estoque=True
        ).select_related('categoria', 'unidade_medida')
        
        if categoria:
            queryset = queryset.filter(categoria_id=categoria)
        
        if apenas_criticos:
            queryset = queryset.filter(estoque_atual__lte=F('estoque_minimo'))
        
        produtos = queryset.order_by('categoria__nome', 'nome')
        
        # Totais
        total_valor_estoque = sum(p.valor_estoque for p in produtos)
        total_produtos_criticos = sum(1 for p in produtos if p.estoque_critico)
        
        context.update({
            'produtos': produtos,
            'categorias': CategoriaEstoque.objects.filter(ativo=True),
            'total_valor_estoque': total_valor_estoque,
            'total_produtos_criticos': total_produtos_criticos,
            'categoria_selected': categoria,
            'apenas_criticos': apenas_criticos,
        })
    
    # Dados para relatório de movimentações
    elif tipo_relatorio == 'movimentacoes':
        # Filtros
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        tipo_operacao = request.GET.get('tipo_operacao')
        
        # Definir período padrão (últimos 30 dias)
        if not data_inicio:
            data_inicio = (timezone.now() - timedelta(days=30)).date()
        else:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        
        if not data_fim:
            data_fim = timezone.now().date()
        else:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        queryset = MovimentacaoEstoque.objects.filter(
            data_movimentacao__date__range=[data_inicio, data_fim]
        ).select_related('produto', 'tipo_movimentacao', 'usuario')
        
        if tipo_operacao:
            queryset = queryset.filter(tipo_operacao=tipo_operacao)
        
        movimentacoes = queryset.order_by('-data_movimentacao')
        
        # Resumo por tipo
        resumo_tipos = queryset.values('tipo_operacao').annotate(
            total_movimentacoes=Count('id'),
            valor_total=Sum('valor_total')
        )
        
        context.update({
            'movimentacoes': movimentacoes,
            'resumo_tipos': resumo_tipos,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'tipo_operacao': tipo_operacao,
        })
    
    return render(request, 'estoque/relatorios.html', context)

@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def relatorio_estoque(request):
    """Relatório de posição de estoque"""
    
    # Filtros
    categoria = request.GET.get('categoria')
    apenas_criticos = request.GET.get('apenas_criticos') == 'true'
    
    queryset = Produto.objects.filter(
        status='ativo',
        controla_estoque=True
    ).select_related('categoria', 'unidade_medida')
    
    if categoria:
        queryset = queryset.filter(categoria_id=categoria)
    
    if apenas_criticos:
        queryset = queryset.filter(estoque_atual__lte=F('estoque_minimo'))
    
    produtos = queryset.order_by('categoria__nome', 'nome')
    
    # Totais
    total_valor_estoque = sum(p.valor_estoque for p in produtos)
    total_produtos_criticos = sum(1 for p in produtos if p.estoque_critico)
    
    context = {
        'title': 'Relatório de Estoque',
        'current_page': 'estoque_relatorios',
        'produtos': produtos,
        'categorias': CategoriaEstoque.objects.filter(ativo=True),
        'total_valor_estoque': total_valor_estoque,
        'total_produtos_criticos': total_produtos_criticos,
        'categoria_selected': categoria,
        'apenas_criticos': apenas_criticos,
    }
    
    return render(request, 'estoque/relatorio_estoque.html', context)


@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def relatorio_movimentacoes(request):
    """Relatório de movimentações por período"""
    
    # Filtros
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    tipo_operacao = request.GET.get('tipo_operacao')
    
    # Definir período padrão (últimos 30 dias)
    if not data_inicio:
        data_inicio = (timezone.now() - timedelta(days=30)).date()
    else:
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    
    if not data_fim:
        data_fim = timezone.now().date()
    else:
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    
    queryset = MovimentacaoEstoque.objects.filter(
        data_movimentacao__date__range=[data_inicio, data_fim]
    ).select_related('produto', 'tipo_movimentacao', 'usuario')
    
    if tipo_operacao:
        queryset = queryset.filter(tipo_operacao=tipo_operacao)
    
    movimentacoes = queryset.order_by('-data_movimentacao')
    
    # Resumo por tipo
    resumo_tipos = queryset.values('tipo_operacao').annotate(
        total_movimentacoes=Count('id'),
        valor_total=Sum('valor_total')
    )
    
    context = {
        'title': 'Relatório de Movimentações',
        'current_page': 'estoque_relatorios',
        'movimentacoes': movimentacoes,
        'resumo_tipos': resumo_tipos,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'tipo_operacao': tipo_operacao,
    }
    
    return render(request, 'estoque/relatorio_movimentacoes.html', context)


# ========== APIS AJAX ==========

@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def api_produto_info(request, produto_id):
    """API para obter informações de um produto"""
    try:
        produto = Produto.objects.get(id=produto_id)
        data = {
            'nome': produto.nome,
            'codigo': produto.codigo,
            'estoque_atual': float(produto.estoque_atual),
            'estoque_minimo': float(produto.estoque_minimo),
            'preco_custo': float(produto.preco_custo),
            'preco_venda': float(produto.preco_venda),
            'unidade_medida': produto.unidade_medida.sigla,
            'estoque_critico': produto.estoque_critico,
        }
        return JsonResponse(data)
    except Produto.DoesNotExist:
        return JsonResponse({'error': 'Produto não encontrado'}, status=404)


@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def api_alertas_estoque(request):
    """API para obter alertas de estoque não resolvidos"""
    alertas = EstoqueAlerta.objects.filter(resolvido=False).select_related('produto')
    
    data = [{
        'id': alerta.id,
        'produto_nome': alerta.produto.nome,
        'produto_codigo': alerta.produto.codigo,
        'tipo_alerta': alerta.get_tipo_alerta_display(),
        'mensagem': alerta.mensagem,
        'data_alerta': alerta.data_alerta.strftime('%d/%m/%Y %H:%M'),
    } for alerta in alertas]
    
    return JsonResponse({'alertas': data})


@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def api_resolver_alerta(request, alerta_id):
    """API para resolver um alerta de estoque"""
    if request.method == 'POST':
        try:
            alerta = EstoqueAlerta.objects.get(id=alerta_id)
            alerta.resolvido = True
            alerta.data_resolucao = timezone.now()
            alerta.resolvido_por = request.user
            alerta.save()
            
            return JsonResponse({'success': True})
        except EstoqueAlerta.DoesNotExist:
            return JsonResponse({'error': 'Alerta não encontrado'}, status=404)
    
    return JsonResponse({'error': 'Método não permitido'}, status=405)