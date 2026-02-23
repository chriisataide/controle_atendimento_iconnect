"""
Views para Gestão de Equipamentos / Ativos (Asset Management).
Controle de equipamentos instalados, histórico de trocas e alertas.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.http import JsonResponse
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Count, F
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import json
import logging

from .models_equipamento import (
    Equipamento, HistoricoEquipamento, AlertaEquipamento,
    ConfiguracaoAlertaEquipamento
)
from .models import Cliente, Ticket

logger = logging.getLogger('dashboard')


# ========== DASHBOARD DE EQUIPAMENTOS ==========

@login_required
def equipamento_dashboard(request):
    """Dashboard principal do módulo de equipamentos."""
    agora = timezone.now()
    limite_30d = agora - timedelta(days=30)

    # Métricas principais
    total_equipamentos = Equipamento.objects.count()
    equipamentos_ativos = Equipamento.objects.filter(status='ativo').count()
    equipamentos_manutencao = Equipamento.objects.filter(status='em_manutencao').count()
    equipamentos_estoque = Equipamento.objects.filter(status='em_estoque').count()

    # Alertas pendentes
    alertas_pendentes = AlertaEquipamento.objects.filter(resolvido=False).count()

    # Trocas no mês
    trocas_mes = HistoricoEquipamento.objects.filter(
        tipo_movimentacao='troca',
        realizado_em__gte=limite_30d
    ).count()

    # Equipamentos problemáticos (3+ chamados em 30 dias)
    config = ConfiguracaoAlertaEquipamento.get_config()
    equipamentos_problematicos = Equipamento.objects.filter(
        status='ativo',
        tickets__criado_em__gte=limite_30d
    ).annotate(
        chamados_recentes=Count('tickets')
    ).filter(
        chamados_recentes__gte=config.chamados_limiar
    ).order_by('-chamados_recentes')[:10]

    # Top 10 tipos de equipamento mais problemáticos
    tipos_problematicos = Equipamento.objects.filter(
        status='ativo',
        tickets__criado_em__gte=limite_30d
    ).values('tipo').annotate(
        total_chamados=Count('tickets')
    ).order_by('-total_chamados')[:10]

    # Movimentações recentes
    movimentacoes_recentes = HistoricoEquipamento.objects.select_related(
        'equipamento', 'cliente_novo', 'realizado_por', 'ticket'
    )[:10]

    # Equipamentos por tipo (para gráfico)
    equipamentos_por_tipo = Equipamento.objects.values('tipo').annotate(
        total=Count('id')
    ).order_by('-total')[:8]

    # Equipamentos por status (para gráfico)
    equipamentos_por_status = {
        'ativos': equipamentos_ativos,
        'manutencao': equipamentos_manutencao,
        'estoque': equipamentos_estoque,
        'desativados': Equipamento.objects.filter(status='desativado').count(),
    }

    # Trocas por mês (últimos 6 meses)
    trocas_por_mes = []
    for i in range(6):
        mes_inicio = (agora - timedelta(days=30 * i)).replace(day=1)
        if i == 0:
            mes_fim = agora
        else:
            mes_fim = (agora - timedelta(days=30 * (i - 1))).replace(day=1)
        count = HistoricoEquipamento.objects.filter(
            tipo_movimentacao='troca',
            realizado_em__gte=mes_inicio,
            realizado_em__lt=mes_fim
        ).count()
        trocas_por_mes.append({
            'mes': mes_inicio.strftime('%b/%y'),
            'total': count
        })
    trocas_por_mes.reverse()

    context = {
        'total_equipamentos': total_equipamentos,
        'equipamentos_ativos': equipamentos_ativos,
        'equipamentos_manutencao': equipamentos_manutencao,
        'equipamentos_estoque': equipamentos_estoque,
        'alertas_pendentes': alertas_pendentes,
        'trocas_mes': trocas_mes,
        'equipamentos_problematicos': equipamentos_problematicos,
        'tipos_problematicos': tipos_problematicos,
        'movimentacoes_recentes': movimentacoes_recentes,
        'equipamentos_por_tipo': json.dumps(list(equipamentos_por_tipo)),
        'equipamentos_por_status': json.dumps(equipamentos_por_status),
        'trocas_por_mes': json.dumps(trocas_por_mes),
        'config': config,
    }
    return render(request, 'equipamentos/dashboard.html', context)


# ========== CRUD DE EQUIPAMENTOS ==========

@method_decorator(login_required, name='dispatch')
class EquipamentoListView(ListView):
    """Listagem de equipamentos com filtros."""
    model = Equipamento
    template_name = 'equipamentos/equipamento_list.html'
    context_object_name = 'equipamentos'
    paginate_by = 20

    def get_queryset(self):
        qs = Equipamento.objects.select_related('cliente', 'criado_por')

        # Filtros
        search = self.request.GET.get('q', '').strip()
        if search:
            qs = qs.filter(
                Q(numero_serie__icontains=search) |
                Q(modelo__icontains=search) |
                Q(marca__icontains=search) |
                Q(tipo__icontains=search) |
                Q(patrimonio__icontains=search) |
                Q(cliente__nome__icontains=search)
            )

        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        tipo = self.request.GET.get('tipo')
        if tipo:
            qs = qs.filter(tipo=tipo)

        cliente_id = self.request.GET.get('cliente')
        if cliente_id:
            qs = qs.filter(cliente_id=cliente_id)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Equipamento.StatusEquipamento.choices
        ctx['tipos'] = (
            Equipamento.objects.values_list('tipo', flat=True)
            .distinct().order_by('tipo')
        )
        ctx['clientes'] = Cliente.objects.all().order_by('nome')
        ctx['filtros'] = {
            'q': self.request.GET.get('q', ''),
            'status': self.request.GET.get('status', ''),
            'tipo': self.request.GET.get('tipo', ''),
            'cliente': self.request.GET.get('cliente', ''),
        }
        ctx['alertas_pendentes'] = AlertaEquipamento.objects.filter(resolvido=False).count()
        return ctx


@method_decorator(login_required, name='dispatch')
class EquipamentoDetailView(DetailView):
    """Detalhe de um equipamento com histórico e chamados."""
    model = Equipamento
    template_name = 'equipamentos/equipamento_detail.html'
    context_object_name = 'equipamento'

    def get_queryset(self):
        return Equipamento.objects.select_related('cliente', 'criado_por')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        equip = self.object
        agora = timezone.now()
        limite_30d = agora - timedelta(days=30)

        # Histórico de movimentações
        ctx['historico'] = equip.historico.select_related(
            'cliente_anterior', 'cliente_novo', 'equipamento_substituido',
            'ticket', 'realizado_por'
        )[:20]

        # Chamados vinculados
        ctx['tickets'] = equip.tickets.select_related(
            'cliente', 'agente', 'categoria'
        ).order_by('-criado_em')[:15]

        # Chamados nos últimos 30 dias
        ctx['chamados_30d'] = equip.tickets.filter(
            criado_em__gte=limite_30d
        ).count()

        # Alertas deste equipamento
        ctx['alertas'] = equip.alertas.filter(resolvido=False)

        # Estatísticas
        ctx['total_chamados'] = equip.tickets.count()
        ctx['total_trocas'] = equip.historico.filter(
            tipo_movimentacao='troca'
        ).count()
        ctx['total_manutencoes'] = equip.historico.filter(
            tipo_movimentacao='manutencao'
        ).count()

        return ctx


@login_required
def equipamento_create(request):
    """Criar novo equipamento."""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                equip = Equipamento(
                    numero_serie=request.POST['numero_serie'].strip(),
                    modelo=request.POST['modelo'].strip(),
                    marca=request.POST.get('marca', '').strip(),
                    tipo=request.POST['tipo'].strip(),
                    descricao=request.POST.get('descricao', '').strip(),
                    patrimonio=request.POST.get('patrimonio', '').strip(),
                    local_instalacao=request.POST.get('local_instalacao', '').strip(),
                    status=request.POST.get('status', 'em_estoque'),
                    observacoes=request.POST.get('observacoes', '').strip(),
                    criado_por=request.user,
                )

                cliente_id = request.POST.get('cliente')
                if cliente_id:
                    equip.cliente_id = int(cliente_id)

                data_instalacao = request.POST.get('data_instalacao')
                if data_instalacao:
                    equip.data_instalacao = data_instalacao

                data_garantia = request.POST.get('data_garantia')
                if data_garantia:
                    equip.data_garantia = data_garantia

                equip.save()

                # Se está instalado em cliente, registrar no histórico
                if equip.cliente and equip.status == 'ativo':
                    HistoricoEquipamento.objects.create(
                        equipamento=equip,
                        tipo_movimentacao='instalacao',
                        cliente_novo=equip.cliente,
                        motivo='Cadastro inicial — equipamento já instalado',
                        realizado_por=request.user,
                    )

                messages.success(request, f'Equipamento {equip.numero_serie} cadastrado com sucesso!')
                return redirect('equipamentos:equipamento_detail', pk=equip.pk)

        except Exception as e:
            logger.error(f'Erro ao criar equipamento: {e}')
            messages.error(request, f'Erro ao cadastrar equipamento: {e}')

    clientes = Cliente.objects.all().order_by('nome')
    status_choices = Equipamento.StatusEquipamento.choices
    # Sugerir tipos já existentes
    tipos_existentes = list(
        Equipamento.objects.values_list('tipo', flat=True).distinct().order_by('tipo')
    )

    return render(request, 'equipamentos/equipamento_form.html', {
        'clientes': clientes,
        'status_choices': status_choices,
        'tipos_existentes': tipos_existentes,
        'modo': 'criar',
    })


@login_required
def equipamento_update(request, pk):
    """Editar equipamento existente."""
    equip = get_object_or_404(Equipamento, pk=pk)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                equip.numero_serie = request.POST['numero_serie'].strip()
                equip.modelo = request.POST['modelo'].strip()
                equip.marca = request.POST.get('marca', '').strip()
                equip.tipo = request.POST['tipo'].strip()
                equip.descricao = request.POST.get('descricao', '').strip()
                equip.patrimonio = request.POST.get('patrimonio', '').strip()
                equip.local_instalacao = request.POST.get('local_instalacao', '').strip()
                equip.status = request.POST.get('status', equip.status)
                equip.observacoes = request.POST.get('observacoes', '').strip()

                cliente_id = request.POST.get('cliente')
                equip.cliente_id = int(cliente_id) if cliente_id else None

                data_instalacao = request.POST.get('data_instalacao')
                equip.data_instalacao = data_instalacao if data_instalacao else None

                data_garantia = request.POST.get('data_garantia')
                equip.data_garantia = data_garantia if data_garantia else None

                equip.save()
                messages.success(request, f'Equipamento {equip.numero_serie} atualizado!')
                return redirect('equipamentos:equipamento_detail', pk=equip.pk)

        except Exception as e:
            logger.error(f'Erro ao atualizar equipamento {pk}: {e}')
            messages.error(request, f'Erro ao atualizar: {e}')

    clientes = Cliente.objects.all().order_by('nome')
    status_choices = Equipamento.StatusEquipamento.choices
    tipos_existentes = list(
        Equipamento.objects.values_list('tipo', flat=True).distinct().order_by('tipo')
    )

    return render(request, 'equipamentos/equipamento_form.html', {
        'equipamento': equip,
        'clientes': clientes,
        'status_choices': status_choices,
        'tipos_existentes': tipos_existentes,
        'modo': 'editar',
    })


# ========== MOVIMENTAÇÕES / HISTÓRICO ==========

@login_required
def registrar_movimentacao(request, pk):
    """Registrar instalação, troca, retirada ou manutenção."""
    equip = get_object_or_404(Equipamento, pk=pk)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                tipo_mov = request.POST['tipo_movimentacao']
                cliente_anterior = equip.cliente

                mov = HistoricoEquipamento(
                    equipamento=equip,
                    tipo_movimentacao=tipo_mov,
                    cliente_anterior=cliente_anterior,
                    motivo=request.POST.get('motivo', '').strip(),
                    observacoes=request.POST.get('observacoes', '').strip(),
                    realizado_por=request.user,
                )

                # Data personalizada ou agora
                data_str = request.POST.get('data_realizacao')
                if data_str:
                    mov.realizado_em = timezone.datetime.fromisoformat(data_str)

                # Ticket vinculado
                ticket_id = request.POST.get('ticket')
                if ticket_id:
                    mov.ticket_id = int(ticket_id)

                # Novo cliente (para instalação/troca)
                novo_cliente_id = request.POST.get('novo_cliente')
                if novo_cliente_id:
                    mov.cliente_novo_id = int(novo_cliente_id)

                # Equipamento substituído (para troca)
                substituido_id = request.POST.get('equipamento_substituido')
                if substituido_id:
                    mov.equipamento_substituido_id = int(substituido_id)
                    # Desativar equipamento antigo
                    equip_antigo = Equipamento.objects.get(pk=substituido_id)
                    equip_antigo.status = 'desativado'
                    equip_antigo.data_desativacao = timezone.now().date()
                    equip_antigo.save(update_fields=['status', 'data_desativacao'])

                mov.save()

                # Atualizar o equipamento com base no tipo de movimentação
                if tipo_mov == 'instalacao':
                    equip.status = 'ativo'
                    if novo_cliente_id:
                        equip.cliente_id = int(novo_cliente_id)
                    equip.data_instalacao = timezone.now().date()
                elif tipo_mov == 'troca':
                    equip.status = 'ativo'
                    if novo_cliente_id:
                        equip.cliente_id = int(novo_cliente_id)
                elif tipo_mov == 'retirada' or tipo_mov == 'devolucao':
                    equip.status = 'em_estoque'
                    equip.cliente = None
                elif tipo_mov == 'manutencao':
                    equip.status = 'em_manutencao'

                equip.save()
                equip.atualizar_contadores()

                messages.success(
                    request,
                    f'{mov.get_tipo_movimentacao_display()} registrada com sucesso!'
                )
                return redirect('equipamentos:equipamento_detail', pk=equip.pk)

        except Exception as e:
            logger.error(f'Erro ao registrar movimentação: {e}')
            messages.error(request, f'Erro: {e}')

    # Buscar tickets do cliente para vincular
    tickets_cliente = []
    if equip.cliente:
        tickets_cliente = Ticket.objects.filter(
            cliente=equip.cliente
        ).order_by('-criado_em')[:20]

    # Equipamentos do mesmo cliente (para troca)
    equipamentos_cliente = []
    if equip.cliente:
        equipamentos_cliente = Equipamento.objects.filter(
            cliente=equip.cliente, status='ativo'
        ).exclude(pk=equip.pk)

    clientes = Cliente.objects.all().order_by('nome')
    tipo_choices = HistoricoEquipamento.TipoMovimentacao.choices

    return render(request, 'equipamentos/registrar_movimentacao.html', {
        'equipamento': equip,
        'tipo_choices': tipo_choices,
        'clientes': clientes,
        'tickets_cliente': tickets_cliente,
        'equipamentos_cliente': equipamentos_cliente,
    })


# ========== ALERTAS ==========

@login_required
def alerta_list(request):
    """Lista de alertas de equipamentos."""
    filtro = request.GET.get('filtro', 'pendentes')

    if filtro == 'todos':
        alertas = AlertaEquipamento.objects.all()
    elif filtro == 'resolvidos':
        alertas = AlertaEquipamento.objects.filter(resolvido=True)
    else:
        alertas = AlertaEquipamento.objects.filter(resolvido=False)

    alertas = alertas.select_related(
        'equipamento', 'equipamento__cliente', 'resolvido_por'
    ).order_by('-criado_em')

    # Paginação
    from django.core.paginator import Paginator
    paginator = Paginator(alertas, 20)
    page = request.GET.get('page')
    alertas_page = paginator.get_page(page)

    return render(request, 'equipamentos/alerta_list.html', {
        'alertas': alertas_page,
        'filtro': filtro,
        'total_pendentes': AlertaEquipamento.objects.filter(resolvido=False).count(),
    })


@login_required
def alerta_resolver(request, pk):
    """Resolver um alerta de equipamento."""
    alerta = get_object_or_404(AlertaEquipamento, pk=pk)

    if request.method == 'POST':
        acao = request.POST.get('acao_tomada', '').strip()
        alerta.resolver(usuario=request.user, acao=acao)
        messages.success(request, 'Alerta resolvido!')
        return redirect('equipamentos:alerta_list')

    return render(request, 'equipamentos/alerta_resolver.html', {
        'alerta': alerta,
    })


# ========== RELATÓRIO POR CLIENTE ==========

@login_required
def equipamentos_por_cliente(request, cliente_id):
    """Equipamentos instalados em um cliente específico."""
    cliente = get_object_or_404(Cliente, pk=cliente_id)
    equipamentos = Equipamento.objects.filter(
        cliente=cliente
    ).order_by('tipo', 'modelo')

    limite_30d = timezone.now() - timedelta(days=30)

    # Métricas do cliente
    total_equipamentos = equipamentos.count()
    total_chamados_equip = 0
    total_trocas = 0

    for equip in equipamentos:
        total_chamados_equip += equip.tickets.filter(criado_em__gte=limite_30d).count()
        total_trocas += equip.historico.filter(tipo_movimentacao='troca').count()

    return render(request, 'equipamentos/equipamentos_cliente.html', {
        'cliente': cliente,
        'equipamentos': equipamentos,
        'total_equipamentos': total_equipamentos,
        'total_chamados_equip': total_chamados_equip,
        'total_trocas': total_trocas,
    })


# ========== APIs AJAX ==========

@login_required
def api_equipamentos_cliente(request, cliente_id):
    """API ajax: retorna equipamentos de um cliente (para selects dinâmicos)."""
    equipamentos = Equipamento.objects.filter(
        cliente_id=cliente_id, status='ativo'
    ).values('id', 'numero_serie', 'tipo', 'modelo', 'marca')

    return JsonResponse({'equipamentos': list(equipamentos)})


@login_required
def api_dashboard_stats(request):
    """API ajax: métricas resumidas para badges e cards dinâmicos."""
    alertas = AlertaEquipamento.objects.filter(resolvido=False).count()
    problematicos = Equipamento.objects.filter(
        status='ativo',
        total_chamados__gte=3
    ).count()

    return JsonResponse({
        'alertas_pendentes': alertas,
        'equipamentos_problematicos': problematicos,
    })
