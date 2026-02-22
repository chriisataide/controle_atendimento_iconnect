# 🔴 RELATÓRIO DE AUDITORIA DE PERFORMANCE - iConnect

**Data:** 22 de fevereiro de 2026  
**Auditor:** Performance Engineering Team  
**Classificação:** Sistema de Alto Tráfego (Financeiro/Governamental)  
**Severidade geral:** CRÍTICA — 47 problemas identificados  

---

## RESUMO EXECUTIVO

| Categoria | Crítico | Alto | Médio | Baixo |
|-----------|---------|------|-------|-------|
| N+1 Queries | 5 | 6 | 3 | — |
| Unbounded Queries | 3 | 5 | 2 | — |
| Bottlenecks Síncronos | 2 | 4 | 2 | — |
| Índices Ausentes | 1 (composto) | 7 | 4 | — |
| Caching Ausente | — | 5 | 3 | — |
| Memória | 2 | 3 | 1 | — |
| Bug Crítico | 1 | — | — | — |

---

## 🚨 BUG CRÍTICO: RECURSÃO INFINITA

### PERF-000 — `_safe_group_send` chama a si mesma (CRASH DO SERVIDOR)

**Arquivo:** `dashboard/signals.py` linhas 27-31  
**Severidade:** 🔴 CRASH — RecursionError em produção

```python
# CÓDIGO ATUAL (BUGADO)
def _safe_group_send(group, message):
    """Send to channel group only when layer is available."""
    if channel_layer is not None:
        try:
            _safe_group_send(group, message)  # ← CHAMA A SI MESMA!
        except Exception:
            logger.debug("Channel layer send failed (no backend?)")
```

**Impacto:** Toda vez que um ticket é criado/atualizado, o signal handler chama `_safe_group_send`, que entra em recursão infinita até `RecursionError`. Isso bloqueia a criação de tickets.

**Correção:**
```python
def _safe_group_send(group, message):
    """Send to channel group only when layer is available."""
    if channel_layer is not None:
        try:
            async_to_sync(channel_layer.group_send)(group, message)
        except Exception:
            logger.debug("Channel layer send failed (no backend?)")
```

---

## A) N+1 QUERY PATTERNS

### PERF-001 — Loop de 30 queries individuais para tendência (analytics_views.py)

**Arquivo:** `dashboard/analytics_views.py` linhas 79-84  
**Severidade:** 🔴 CRÍTICO

```python
# CÓDIGO ATUAL
tendencia_dados = []
for i in range(30):
    data = hoje - timedelta(days=i)
    tickets_dia = Ticket.objects.filter(criado_em__date=data).count()  # ← 30 queries!
    tendencia_dados.append({
        'data': data.strftime('%d/%m'),
        'tickets': tickets_dia
    })
```

**Impacto:** 30 queries SQL por request. Com 100 requests/min = 3.000 queries/min desnecessárias.

**Correção:**
```python
from django.db.models.functions import TruncDate

trinta_dias_atras = hoje - timedelta(days=30)
tendencia_qs = (
    Ticket.objects.filter(criado_em__date__gte=trinta_dias_atras)
    .annotate(data=TruncDate('criado_em'))
    .values('data')
    .annotate(tickets=Count('id'))
    .order_by('data')
)
tendencia_dict = {item['data']: item['tickets'] for item in tendencia_qs}

tendencia_dados = []
for i in range(29, -1, -1):
    data = hoje - timedelta(days=i)
    tendencia_dados.append({
        'data': data.strftime('%d/%m'),
        'tickets': tendencia_dict.get(data, 0)
    })
```

---

### PERF-002 — Loop sobre TODOS resolved tickets para calcular média (executive_views.py)

**Arquivo:** `dashboard/executive_views.py` linhas 112-131  
**Severidade:** 🔴 CRÍTICO — O(N) em memória

```python
# CÓDIGO ATUAL
resolved_tickets = Ticket.objects.filter(
    status='fechado',
    resolvido_em__isnull=False
)

avg_resolution_time = 0
if resolved_tickets.exists():
    total_time = sum([
        (ticket.resolvido_em - ticket.criado_em).total_seconds() / 3600
        for ticket in resolved_tickets  # ← CARREGA TODOS NA MEMÓRIA
        if ticket.resolvido_em and ticket.criado_em
    ])
    avg_resolution_time = total_time / resolved_tickets.count()
```

**Impacto:** Com 100.000 tickets resolvidos, carrega ~100K objetos na memória (~200MB). A query roda 2x (list comprehension + count). Em sistema financeiro/governamental com anos de dados, isso pode derrubar o servidor.

**Correção:**
```python
from django.db.models import Avg, F, ExpressionWrapper, DurationField

avg_delta = Ticket.objects.filter(
    status='fechado',
    resolvido_em__isnull=False,
).aggregate(
    avg=Avg(ExpressionWrapper(
        F('resolvido_em') - F('criado_em'),
        output_field=DurationField()
    ))
)['avg']

avg_resolution_time = round(avg_delta.total_seconds() / 3600, 1) if avg_delta else 0
```

---

### PERF-003 — Criação de N notificações por ticket (signals.py)

**Arquivo:** `dashboard/signals.py` linhas 57-68  
**Severidade:** 🟠 ALTO

```python
# CÓDIGO ATUAL
agents = User.objects.filter(perfilagente__isnull=False, is_active=True)
for agent in agents:  # ← N inserts, um por agente
    Notification.objects.create(
        user=agent,
        title='Novo Ticket Criado',
        message=f'Ticket #{instance.numero}: {instance.titulo}',
        type='new_ticket',
        ticket=instance
    )
```

**Impacto:** Se há 50 agentes, cada ticket novo gera 50 INSERTs individuais no banco. Dentro de um signal `post_save`, isso bloqueia o request do usuário.

**Correção:**
```python
agents = User.objects.filter(perfilagente__isnull=False, is_active=True)
notifications = [
    Notification(
        user=agent,
        title='Novo Ticket Criado',
        message=f'Ticket #{instance.numero}: {instance.titulo}',
        type='new_ticket',
        ticket=instance,
    )
    for agent in agents
]
Notification.objects.bulk_create(notifications)
```

---

### PERF-004 — Loop de 14 queries na tendência do admin_dashboard (views.py)

**Arquivo:** `dashboard/views.py` linhas 208-219  
**Severidade:** 🟠 ALTO

```python
# CÓDIGO ATUAL
for i in range(6, -1, -1):
    dia = (agora - timedelta(days=i)).date()
    tendencia_labels.append(dia.strftime('%d/%m'))
    tendencia_criados.append(
        Ticket.objects.filter(criado_em__date=dia).count()  # ← 7 queries
    )
    tendencia_fechados.append(
        Ticket.objects.filter(
            Q(status__in=['resolvido', 'fechado']),
            Q(atualizado_em__date=dia)
        ).count()  # ← mais 7 queries
    )
```

**Impacto:** 14 queries SQL por carregamento do dashboard admin.

**Correção:**
```python
from django.db.models.functions import TruncDate

sete_dias_atras = (agora - timedelta(days=6)).date()

criados_por_dia = dict(
    Ticket.objects.filter(criado_em__date__gte=sete_dias_atras)
    .annotate(dia=TruncDate('criado_em'))
    .values('dia')
    .annotate(count=Count('id'))
    .values_list('dia', 'count')
)
fechados_por_dia = dict(
    Ticket.objects.filter(
        status__in=['resolvido', 'fechado'],
        atualizado_em__date__gte=sete_dias_atras
    )
    .annotate(dia=TruncDate('atualizado_em'))
    .values('dia')
    .annotate(count=Count('id'))
    .values_list('dia', 'count')
)

for i in range(6, -1, -1):
    dia = (agora - timedelta(days=i)).date()
    tendencia_labels.append(dia.strftime('%d/%m'))
    tendencia_criados.append(criados_por_dia.get(dia, 0))
    tendencia_fechados.append(fechados_por_dia.get(dia, 0))
```

---

### PERF-005 — Loop com queries por agente (reports_service.py)

**Arquivo:** `dashboard/reports_service.py` linhas 126-200  
**Severidade:** 🔴 CRÍTICO

```python
# CÓDIGO ATUAL
agents = Agent.objects.filter(is_active=True)
for agent in agents:  # ← Para cada agente...
    agent_tickets = tickets.filter(assigned_to=agent)
    resolved_tickets = agent_tickets.filter(status='FECHADO')
    total_tickets = agent_tickets.count()            # query 1
    # ...
    for ticket in resolved_tickets:                  # query 2 + loop N
        resolution_time = (ticket.resolved_at - ticket.created_at).total_seconds() / 3600
    # ...
    first_response_tickets = agent_tickets.filter(...)
    for ticket in first_response_tickets:            # query 3 + loop N
        response_time = (ticket.first_response_at - ticket.created_at).total_seconds() / 3600
    # ...
    satisfaction_tickets = agent_tickets.exclude(...)  # query 4
```

**Impacto:** Para 30 agentes, são ~120 queries + iteração em Python de todos os tickets. Com volumes altos, relatórios levarão minutos.

**Correção:**
```python
from django.db.models import Avg, Count, Q, F, ExpressionWrapper, DurationField

agent_stats = (
    tickets.filter(assigned_to__isnull=False)
    .values('assigned_to__id', 'assigned_to__user__first_name', 'assigned_to__user__email')
    .annotate(
        total_tickets=Count('id'),
        resolved_tickets=Count('id', filter=Q(status='FECHADO')),
        pending_tickets=Count('id', filter=Q(status__in=['NOVO', 'ABERTO', 'EM_ANDAMENTO'])),
        escalated_tickets=Count('id', filter=Q(escalated=True)),
        avg_resolution_time=Avg(
            ExpressionWrapper(F('resolved_at') - F('created_at'), output_field=DurationField()),
            filter=Q(status='FECHADO', resolved_at__isnull=False)
        ),
        avg_first_response=Avg(
            ExpressionWrapper(F('first_response_at') - F('created_at'), output_field=DurationField()),
            filter=Q(first_response_at__isnull=False)
        ),
        avg_satisfaction=Avg('customer_satisfaction', filter=Q(customer_satisfaction__isnull=False)),
    )
)
```

---

### PERF-006 — sla_manager._calculate_avg_resolution_time itera em Python (sla.py)

**Arquivo:** `dashboard/sla.py` linhas 222-236  
**Severidade:** 🟠 ALTO

```python
# CÓDIGO ATUAL
def _calculate_avg_resolution_time(self, tickets):
    resolution_times = []
    for ticket in tickets:  # ← Itera TODOS os tickets na memória
        if ticket.resolvido_em:
            time_diff = ticket.resolvido_em - ticket.criado_em
            resolution_times.append(time_diff.total_seconds() / 3600)
    if resolution_times:
        return round(sum(resolution_times) / len(resolution_times), 2)
```

**Correção:**
```python
def _calculate_avg_resolution_time(self, tickets):
    from django.db.models import Avg, F, ExpressionWrapper, DurationField
    result = tickets.filter(resolvido_em__isnull=False).aggregate(
        avg=Avg(ExpressionWrapper(
            F('resolvido_em') - F('criado_em'),
            output_field=DurationField()
        ))
    )['avg']
    return round(result.total_seconds() / 3600, 2) if result else 0
```

---

### PERF-007 — monitor_sla_violations itera todos os tickets (sla.py)

**Arquivo:** `dashboard/sla.py` linhas 252-305  
**Severidade:** 🟠 ALTO

```python
# CÓDIGO ATUAL
active_tickets = Ticket.objects.filter(
    status__in=['aberto', 'em_andamento', 'aguardando_cliente']
).exclude(sla_deadline__isnull=True)

for ticket in active_tickets:  # ← Itera TODOS os tickets ativos
    sla_status = sla_manager.check_sla_status(ticket)
    # check_sla_status pode fazer ticket.save() → outra query
```

**Impacto:** Celery task que carrega todos os tickets ativos na memória. Com 10.000 tickets abertos, consome memória excessiva e dispara queries individuais adicionais.

**Correção:**
```python
@shared_task
def monitor_sla_violations():
    now = timezone.now()
    
    # 1. Tickets já violados SLA (bulk query)
    violated_tickets = Ticket.objects.filter(
        status__in=['aberto', 'em_andamento', 'aguardando_cliente'],
        sla_deadline__lt=now,
        sla_deadline__isnull=False,
    ).exclude(
        sla_violations__violation_type='deadline_missed'
    ).select_related('agente')
    
    # Bulk create violações
    violations = [
        SLAViolation(
            ticket=t,
            violation_type='deadline_missed',
            expected_deadline=t.sla_deadline,
            actual_time=now,
            severity='high',
        ) for t in violated_tickets
    ]
    SLAViolation.objects.bulk_create(violations)
    
    # 2. Tickets com SLA em warning (próximas 2 horas)
    warning_tickets = Ticket.objects.filter(
        status__in=['aberto', 'em_andamento', 'aguardando_cliente'],
        sla_deadline__gt=now,
        sla_deadline__lte=now + timedelta(hours=2),
    ).select_related('agente')
    
    # ... processar warnings em batch
```

---

### PERF-008 — Loop de queries por dia no estoque_dashboard (estoque_views.py)

**Arquivo:** `dashboard/estoque_views.py` linhas 62-78  
**Severidade:** 🟡 MÉDIO

```python
# CÓDIGO ATUAL
movimentacoes_por_dia = []
for i in range(7):
    data = timezone.now().date() - timedelta(days=i)
    entradas = MovimentacaoEstoque.objects.filter(
        data_movimentacao__date=data, tipo_operacao='entrada'
    ).count()  # ← 7 queries
    saidas = MovimentacaoEstoque.objects.filter(
        data_movimentacao__date=data, tipo_operacao='saida'
    ).count()  # ← 7 queries
```

**Correção:**
```python
sete_dias = timezone.now().date() - timedelta(days=6)
movs_agrupadas = (
    MovimentacaoEstoque.objects
    .filter(data_movimentacao__date__gte=sete_dias)
    .annotate(dia=TruncDate('data_movimentacao'))
    .values('dia', 'tipo_operacao')
    .annotate(total=Count('id'))
)
mov_dict = {}
for m in movs_agrupadas:
    mov_dict.setdefault(m['dia'], {})['entrada' if m['tipo_operacao'] == 'entrada' else 'saida'] = m['total']
```

---

### PERF-009 — Loop com queries por departamento (financeiro_views.py)

**Arquivo:** `dashboard/financeiro_views.py` linhas 697-727  
**Severidade:** 🟡 MÉDIO

```python
# CÓDIGO ATUAL (api_centros_custo_stats)
departamentos = CentroCusto.objects.filter(status='ativo').values_list('departamento', flat=True).distinct()

for dept in departamentos:  # ← N+1
    centros_dept = CentroCusto.objects.filter(departamento=dept, status='ativo')
    total_orcamento = centros_dept.aggregate(total=Sum('orcamento_mensal'))['total'] or 0
    total_gasto = MovimentacaoFinanceira.objects.filter(
        centro_custo__in=centros_dept, ...
    ).aggregate(total=Sum('valor'))['total'] or 0
```

**Correção:**
```python
stats_departamentos = (
    CentroCusto.objects.filter(status='ativo')
    .values('departamento')
    .annotate(
        total_orcamento=Sum('orcamento_mensal'),
        total_gasto=Sum(
            'movimentacoes__valor',
            filter=Q(
                movimentacoes__tipo='despesa',
                movimentacoes__data_movimentacao__month=mes_atual,
                movimentacoes__data_movimentacao__year=ano_atual,
            )
        )
    )
)
```

---

### PERF-010 — _calcular_tempo_medio_resposta itera tickets (views.py)

**Arquivo:** `dashboard/views.py` linhas 1036-1050  
**Severidade:** 🟡 MÉDIO

```python
# CÓDIGO ATUAL
def _calcular_tempo_medio_resposta(tickets_qs):
    tickets_com_interacao = tickets_qs.filter(
        interacoes__isnull=False
    ).annotate(
        primeira_resposta=Min('interacoes__criado_em')
    ).filter(primeira_resposta__isnull=False)
    
    total_minutos = 0
    count = 0
    for t in tickets_com_interacao[:100]:  # Limita a 100, mas ainda itera
        diff = t.primeira_resposta - t.criado_em
        total_minutos += diff.total_seconds() / 60
        count += 1
```

**Correção:**
```python
def _calcular_tempo_medio_resposta(tickets_qs):
    from django.db.models import Avg, F, ExpressionWrapper, DurationField, Min

    result = tickets_qs.filter(
        interacoes__isnull=False
    ).annotate(
        primeira_resposta=Min('interacoes__criado_em')
    ).filter(
        primeira_resposta__isnull=False
    ).aggregate(
        media=Avg(ExpressionWrapper(
            F('primeira_resposta') - F('criado_em'),
            output_field=DurationField()
        ))
    )['media']

    if not result:
        return 'N/A'
    
    media_min = result.total_seconds() / 60
    if media_min < 60:
        return f'{int(media_min)}min'
    horas = int(media_min // 60)
    minutos = int(media_min % 60)
    return f'{horas}h {minutos:02d}min'
```

---

### PERF-011 — ml_engine.prepare_data faz query por ticket (ml_engine.py)

**Arquivo:** `dashboard/ml_engine.py` linhas 126-170  
**Severidade:** 🟠 ALTO

```python
# CÓDIGO ATUAL
tickets = Ticket.objects.filter(
    criado_em__gte=timezone.now() - timedelta(days=365)
).select_related('cliente', 'agente')

data = []
for ticket in tickets:  # ← itera potencialmente milhares
    sentiment = analisar_sentimento_pt(text)     # CPU-bound
    cliente_tickets = Ticket.objects.filter(      # ← Query POR ticket!
        cliente=ticket.cliente
    ).count()
    satisfacao = self._get_satisfaction(ticket)   # ← Mais query por ticket
```

**Impacto:** Para 10.000 tickets → 20.000+ queries adicionais + análise de sentimento síncrona.

**Correção:**
```python
# Pré-computar contagens de tickets por cliente
from django.db.models import Subquery, OuterRef

cliente_counts = dict(
    Ticket.objects.values('cliente_id')
    .annotate(count=Count('id'))
    .values_list('cliente_id', 'count')
)

# Pré-carregar avaliações
from .models_satisfacao import AvaliacaoSatisfacao
avaliacoes = dict(
    AvaliacaoSatisfacao.objects.filter(
        ticket__criado_em__gte=timezone.now() - timedelta(days=365)
    ).values_list('ticket_id', 'nota_atendimento')
)

tickets = Ticket.objects.filter(
    criado_em__gte=timezone.now() - timedelta(days=365)
).select_related('cliente', 'agente').iterator(chunk_size=1000)

for ticket in tickets:
    cliente_historico = cliente_counts.get(ticket.cliente_id, 0)
    satisfacao = avaliacoes.get(ticket.id)
    # ...
```

---

## B) UNBOUNDED QUERIES

### PERF-012 — Listas financeiras sem paginação (financeiro_views.py)

**Arquivo:** `dashboard/financeiro_views.py`  
**Severidade:** 🔴 CRÍTICO  
**Linhas afetadas:** 147, 159, 185, 287

```python
# contratos_lista (L147)
contratos = Contrato.objects.select_related('cliente').all()  # ← SEM LIMITE

# faturas_lista (L159)
faturas = Fatura.objects.select_related('contrato__cliente').all()  # ← SEM LIMITE

# movimentacoes_lista (L185)
movimentacoes = MovimentacaoFinanceira.objects.select_related('categoria', 'usuario').all()  # ← SEM LIMITE

# api_movimentacoes (L287)
movimentacoes = MovimentacaoFinanceira.objects.select_related('categoria', 'usuario')
for mov in movimentacoes:  # ← Serializa TUDO na memória
    data.append({...})
```

**Impacto:** Sistema governamental/financeiro pode ter milhões de registros financeiros. Carregar todos na memória pode crashar o processo Django (OOM) e causar timeout no banco.

**Correção para todas as views financeiras:**
```python
# Usar Paginator ou ListView com paginate_by
from django.core.paginator import Paginator

def contratos_lista(request):
    contratos_qs = Contrato.objects.select_related('cliente').order_by('-criado_em')
    paginator = Paginator(contratos_qs, 25)
    page = request.GET.get('page')
    contratos = paginator.get_page(page)
    # ...

# Para API JSON:
def api_movimentacoes(request):
    page = int(request.GET.get('page', 1))
    per_page = min(int(request.GET.get('per_page', 50)), 200)
    
    movimentacoes = MovimentacaoFinanceira.objects.select_related(
        'categoria', 'usuario'
    ).order_by('-data_movimentacao')
    
    paginator = Paginator(movimentacoes, per_page)
    page_obj = paginator.get_page(page)
    
    data = [{
        'id': mov.id,
        'descricao': mov.descricao,
        # ...
    } for mov in page_obj]
    
    return JsonResponse({
        'movimentacoes': data,
        'total': paginator.count,
        'pages': paginator.num_pages,
        'current_page': page,
    })
```

---

### PERF-013 — Relatório de estoque carrega tudo em Python (estoque_views.py)

**Arquivo:** `dashboard/estoque_views.py` linhas 465-480  
**Severidade:** 🟠 ALTO

```python
# CÓDIGO ATUAL
produtos = queryset.order_by('categoria__nome', 'nome')

# Totais calculados em Python iterando sobre TODOS os produtos
total_valor_estoque = sum(p.valor_estoque for p in produtos)  # ← Puxa TUDO do DB
total_produtos_criticos = sum(1 for p in produtos if p.estoque_critico)
```

**Correção:**
```python
from django.db.models import Sum, F, Count, Q

totais = queryset.aggregate(
    total_valor_estoque=Sum(F('estoque_atual') * F('preco_custo')),
    total_produtos_criticos=Count('id', filter=Q(estoque_atual__lte=F('estoque_minimo')))
)
total_valor_estoque = totais['total_valor_estoque'] or 0
total_produtos_criticos = totais['total_produtos_criticos']

# Paginar os produtos para renderização
paginator = Paginator(queryset.order_by('categoria__nome', 'nome'), 50)
page = request.GET.get('page')
produtos = paginator.get_page(page)
```

---

### PERF-014 — TicketCreateView carrega todos os clientes (views.py)

**Arquivo:** `dashboard/views.py` linha 821  
**Severidade:** 🟡 MÉDIO

```python
# CÓDIGO ATUAL
context['clientes'] = Cliente.objects.all().order_by('nome')  # ← Sem limite
```

**Correção:**
```python
# Usar select2 com busca AJAX em vez de carregar todos os clientes
# Ou limitar para autocomplete:
context['clientes'] = Cliente.objects.all().order_by('nome')[:500]
# Melhor: implementar endpoint de busca AJAX para select2
```

---

### PERF-015 — Relatório de movimentações sem paginação (estoque_views.py)

**Arquivo:** `dashboard/estoque_views.py` linhas 510-530  
**Severidade:** 🟠 ALTO

```python
# CÓDIGO ATUAL
movimentacoes = queryset.order_by('-data_movimentacao')  # ← Sem paginação no template
```

**Correção:** Usar `Paginator` ou converter para `ListView` com `paginate_by`.

---

### PERF-016 — Contagem repetida de KPIs sobre tabela completa (views.py)

**Arquivo:** `dashboard/views.py` linhas 726-755 (TicketListView.get_context_data)  
**Severidade:** 🟠 ALTO

```python
# CÓDIGO ATUAL — 7 queries sobre Ticket.objects.all()
all_tickets = Ticket.objects.all()
context['kpi_total'] = all_tickets.count()
context['kpi_abertos'] = all_tickets.filter(status=StatusTicket.ABERTO).count()
context['kpi_andamento'] = all_tickets.filter(status=StatusTicket.EM_ANDAMENTO).count()
context['kpi_resolvidos'] = all_tickets.filter(status__in=[...]).count()
context['kpi_criticos'] = all_tickets.filter(prioridade=PrioridadeTicket.CRITICA, ...).count()
context['kpi_nao_atribuidos'] = all_tickets.filter(agente__isnull=True, ...).count()
```

**Correção:**
```python
kpis = Ticket.objects.aggregate(
    kpi_total=Count('id'),
    kpi_abertos=Count('id', filter=Q(status=StatusTicket.ABERTO)),
    kpi_andamento=Count('id', filter=Q(status=StatusTicket.EM_ANDAMENTO)),
    kpi_resolvidos=Count('id', filter=Q(status__in=[StatusTicket.RESOLVIDO, StatusTicket.FECHADO])),
    kpi_criticos=Count('id', filter=Q(
        prioridade=PrioridadeTicket.CRITICA,
        status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO]
    )),
    kpi_nao_atribuidos=Count('id', filter=Q(
        agente__isnull=True,
        status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO]
    )),
)
context.update(kpis)
```

---

### PERF-017 — tickets_abertos/andamento/aguardando como queries separadas (executive_views.py)

**Arquivo:** `dashboard/executive_views.py` linhas 68-70  
**Severidade:** 🟡 MÉDIO

```python
tickets_abertos = Ticket.objects.filter(status='aberto').count()
tickets_andamento = Ticket.objects.filter(status='em_andamento').count()
tickets_aguardando = Ticket.objects.filter(status='aguardando_cliente').count()
```

**Correção:** Consolidar num único `aggregate` como feito no admin_dashboard.

---

## C) SYNCHRONOUS BOTTLENECKS

### PERF-018 — ML inference em request handler (ml_engine.py)

**Arquivo:** `dashboard/ml_engine.py` linhas 324-380  
**Severidade:** 🔴 CRÍTICO

```python
# CÓDIGO ATUAL
def predict_ticket_properties(self, titulo, descricao, cliente_id=None):
    self._load_models()  # ← Lê ficheiros do disco a cada chamada!
    
    # ... faz inferência ML síncrona
    if self.priority_model:
        priority_pred = self.priority_model.predict(X)[0]  # ← CPU-bound
```

**Impacto:** Cada pedido de predição faz I/O de disco (carregar modelos) + inferência ML síncrona. Bloqueia o worker Django por centenas de ms.

**Correção:**
```python
class TicketPredictor:
    _instance = None
    _models_loaded = False
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load_models()
            cls._models_loaded = True
        return cls._instance
    
    def predict_ticket_properties(self, titulo, descricao, cliente_id=None):
        if not self._models_loaded:
            self._load_models()
            self._models_loaded = True
        # ... rest of prediction logic
```

Idealmente, mover para Celery task ou microsserviço ML dedicado.

---

### PERF-019 — prepare_data faz análise de sentimento por ticket (ml_engine.py)

**Arquivo:** `dashboard/ml_engine.py` linhas 148-150  
**Severidade:** 🟠 ALTO

```python
# CÓDIGO ATUAL - dentro do loop de tickets
sentiment = analisar_sentimento_pt(text)  # TextBlob por texto - lento
```

**Impacto:** TextBlob é lento (~5ms por texto). Para 10.000 tickets = 50 segundos só de análise de sentimento. Deve rodar como task Celery.

**Correção:**
```python
# Usar batch processing e mover train_models para Celery
@shared_task
def train_ml_models():
    predictor = TicketPredictor()
    predictor.train_models()
```

---

### PERF-020 — Signal handlers executam trabalho pesado (signals.py)

**Arquivo:** `dashboard/signals.py` linhas 47-265 (múltiplos handlers)  
**Severidade:** 🟠 ALTO

```python
# CÓDIGO ATUAL - signal post_save excessivamente pesado
@receiver(post_save, sender=Ticket)
def ticket_created_or_updated(sender, instance, created, **kwargs):
    # WebSocket broadcast
    _safe_group_send(...)
    
    # Loop criando notificações
    agents = User.objects.filter(...)
    for agent in agents:
        Notification.objects.create(...)
    
    # Tenta encontrar user por email do cliente
    client_user = User.objects.get(email=instance.cliente.email)
    Notification.objects.create(...)
```

**Impacto:** Cada `ticket.save()` executa queries adicionais e I/O dentro do mesmo request. Há 3 signals `post_save` no `Ticket`: `ticket_created_or_updated`, `setup_sla_for_new_ticket`, `track_resolution_time`, `audit_ticket_change`. Total: ~10-20 queries extras por save.

**Correção:** Mover trabalho pesado para Celery:

```python
@receiver(post_save, sender=Ticket)
def ticket_post_save(sender, instance, created, **kwargs):
    from .tasks import process_ticket_notifications
    # Agendar como task assíncrona
    process_ticket_notifications.delay(instance.id, created)
```

---

### PERF-021 — SLA breach notifica todos supervisores em loop (signals.py)

**Arquivo:** `dashboard/signals.py` linhas 247-274  
**Severidade:** 🟡 MÉDIO

```python
supervisors = User.objects.filter(is_staff=True, is_active=True)
for supervisor in supervisors:
    Notification.objects.create(...)  # N inserts
    _safe_group_send(f"user_{supervisor.id}", ...)  # N WebSocket
```

**Correção:** `bulk_create` + broadcast único para group "supervisors".

---

## D) MISSING DATABASE INDEXES

### PERF-022 — Campos críticos do Ticket sem índice

**Arquivo:** `dashboard/models.py` linhas 165-195  
**Severidade:** 🔴 CRÍTICO (composto)

Campos usados intensivamente em `filter()`, `order_by()`, `aggregate()` sem `db_index=True`:

| Campo | Usado em | Queries/request estimadas |
|-------|----------|--------------------------|
| `Ticket.agente` | TicketListView, analytics, reports | 5-10 |
| `Ticket.resolvido_em` | Tempo de resolução, SLA, relatórios | 3-5 |
| `Ticket.fechado_em` | Financeiro, relatórios | 2-3 |
| `Ticket.sla_deadline` | SLA monitor, executive views | 2-4 |
| `Ticket.sla_resolution_deadline` | Dashboard view | 1-2 |
| `Ticket.is_escalated` | Dashboard view, reports | 1-2 |
| `Ticket.tipo` | Filtros | 1 |

**Índices compostos ausentes (mais impactantes):**

| Índice composto | Queries beneficiadas |
|----------------|---------------------|
| `(status, criado_em)` | Dashboard, analytics, tendências |
| `(status, prioridade)` | KPIs, kanban |
| `(agente, status)` | AgenteDashboard, reports |
| `(cliente, criado_em)` | Portal do cliente |
| `(status, agente, criado_em)` | Listagens filtradas |

**Correção no Meta do modelo Ticket:**
```python
class Ticket(models.Model):
    # ... campos existentes ...
    
    # Adicionar db_index nos campos
    resolvido_em = models.DateTimeField(null=True, blank=True, db_index=True)
    fechado_em = models.DateTimeField(null=True, blank=True, db_index=True)
    sla_deadline = models.DateTimeField(null=True, blank=True, db_index=True)
    is_escalated = models.BooleanField(default=False, db_index=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status', '-criado_em'], name='idx_ticket_status_criado'),
            models.Index(fields=['status', 'prioridade'], name='idx_ticket_status_prioridade'),
            models.Index(fields=['agente', 'status'], name='idx_ticket_agente_status'),
            models.Index(fields=['cliente', '-criado_em'], name='idx_ticket_cliente_criado'),
            models.Index(fields=['status', 'sla_deadline'], name='idx_ticket_status_sla'),
            models.Index(fields=['status', 'agente', '-criado_em'], name='idx_ticket_status_agente_criado'),
        ]
```

---

### PERF-023 — Modelos financeiros sem índices

**Arquivo:** `dashboard/models.py` (Fatura, MovimentacaoFinanceira, Contrato)  
**Severidade:** 🟠 ALTO

```python
# Fatura — queries frequentes por status e data_vencimento
class Fatura(models.Model):
    status = models.CharField(...)  # ← Sem db_index, usado em filtros/aggregates
    data_vencimento = models.DateField()  # ← Sem db_index, usado em ordering

# MovimentacaoFinanceira — queries frequentes por tipo e data
class MovimentacaoFinanceira(models.Model):
    tipo = models.CharField(...)  # ← Sem db_index
    data_movimentacao = models.DateField()  # ← Sem db_index

# Contrato
class Contrato(models.Model):
    status = models.CharField(...)  # ← Sem db_index
```

**Correção:**
```python
class Fatura(models.Model):
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente', db_index=True)
    data_vencimento = models.DateField(db_index=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status', '-data_vencimento']),
        ]

class MovimentacaoFinanceira(models.Model):
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, db_index=True)
    data_movimentacao = models.DateField(db_index=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['tipo', '-data_movimentacao']),
            models.Index(fields=['centro_custo', '-data_movimentacao']),
        ]

class Contrato(models.Model):
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ativo', db_index=True)
```

---

### PERF-024 — AvaliacaoSatisfacao sem índice em avaliado_em

**Arquivo:** `dashboard/models_satisfacao.py`  
**Severidade:** 🟡 MÉDIO

```python
class AvaliacaoSatisfacao(models.Model):
    avaliado_em = models.DateTimeField(auto_now_add=True)  # ← Sem índice, filtrado em executive_views/analytics
```

**Correção:**
```python
class AvaliacaoSatisfacao(models.Model):
    avaliado_em = models.DateTimeField(auto_now_add=True, db_index=True)
```

---

### PERF-025 — SLAViolation sem índice em created_at

**Arquivo:** `dashboard/models.py` (SLAViolation)  
**Severidade:** 🟡 MÉDIO

Usado em `sla.py` e `api_views.py` com `filter(created_at__gte=...)`.

```python
class SLAViolation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)  # ← Sem db_index
    
    class Meta:
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['ticket', '-created_at']),
        ]
```

---

### PERF-026 — CentroCusto.status sem índice

**Arquivo:** `dashboard/models.py` (CentroCusto)  
**Severidade:** 🟡 MÉDIO

Filtrado frequentemente com `filter(status='ativo')`.

```python
status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ativo', db_index=True)
```

---

### PERF-027 — ItemAtendimento sem índice composto para relatórios financeiros

**Arquivo:** `dashboard/models.py` (ItemAtendimento)  
**Severidade:** 🟠 ALTO

Usado extensivamente em `financeiro_views.py` com filtros compostos.

```python
class Meta:
    indexes = [
        models.Index(fields=['ticket', 'tipo_item']),
        models.Index(fields=['produto', '-adicionado_em']),
    ]
```

---

### PERF-028 — PerfilAgente.status sem índice  

**Arquivo:** `dashboard/models.py`  
**Severidade:** 🟡 MÉDIO

Filtrado com `filter(status='online')` no dashboard.

```python
status = models.CharField(max_length=10, choices=StatusAgente.choices, default=StatusAgente.OFFLINE, db_index=True)
```

---

## E) CACHING OPPORTUNITIES

### PERF-029 — DashboardView sem cache (views.py)

**Arquivo:** `dashboard/views.py` linhas 295-520 (DashboardView.get_context_data)  
**Severidade:** 🟠 ALTO

**Impacto:** ~25 queries SQL executadas a cada page load do dashboard principal. Se 50 usuários acessam simultaneamente = 1.250 queries para dados que mudam a cada poucos minutos.

**Correção:**
```python
from django.core.cache import cache

class DashboardView(TemplateView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        cache_key = 'dashboard_main_metrics'
        cached = cache.get(cache_key)
        if cached:
            context.update(cached)
            return context
        
        # ... computar métricas ...
        
        metrics = {
            'tickets_por_mes': ...,
            'status_data': ...,
            # ... todas as métricas
        }
        cache.set(cache_key, metrics, timeout=300)  # Cache 5 minutos
        context.update(metrics)
        return context
```

---

### PERF-030 — admin_dashboard sem cache (views.py)

**Arquivo:** `dashboard/views.py` linhas 166-237  
**Severidade:** 🟠 ALTO

Mesmo problema do DashboardView — muitas queries por request.

**Correção:** Mesmo padrão — `cache.get_or_set('admin_dashboard_data', compute_fn, timeout=300)`.

---

### PERF-031 — executive_dashboard sem cache (executive_views.py)

**Arquivo:** `dashboard/executive_views.py` linhas 18-84  
**Severidade:** 🟠 ALTO

~15 queries SQL por request.

**Correção:**
```python
cache_key = 'executive_dashboard_data'
cached = cache.get(cache_key)
if cached:
    return render(request, template, cached)

# ... compute ...
cache.set(cache_key, context, timeout=180)  # 3 minutos
```

---

### PERF-032 — analytics_dashboard sem cache (analytics_views.py)

**Arquivo:** `dashboard/analytics_views.py` linhas 10-110  
**Severidade:** 🟠 ALTO

O mais pesado — cerca de 10+ queries incluindo o loop de 30 dias.

---

### PERF-033 — TicketListView KPIs recalculados por página (views.py)

**Arquivo:** `dashboard/views.py` linhas 726-755  
**Severidade:** 🟡 MÉDIO

KPIs globais (total de tickets, abertos, etc.) recalculados a cada paginação.

**Correção:**
```python
# Cache KPIs globais por 2 minutos
kpis = cache.get_or_set(
    'ticket_list_kpis',
    lambda: Ticket.objects.aggregate(...),
    timeout=120
)
context.update(kpis)
```

---

### PERF-034 — SLA policies lookup sem cache (sla.py)

**Arquivo:** `dashboard/sla.py` linhas 29-37  
**Severidade:** 🟡 MÉDIO

```python
sla_policy = SLAPolicy.objects.filter(
    categoria=ticket.categoria,
    prioridade=ticket.prioridade
).first()
```

**Correção:**
```python
cache_key = f'sla_policy_{ticket.categoria_id}_{ticket.prioridade}'
sla_policy = cache.get(cache_key)
if sla_policy is None:
    sla_policy = SLAPolicy.objects.filter(
        categoria=ticket.categoria,
        prioridade=ticket.prioridade
    ).first()
    cache.set(cache_key, sla_policy, timeout=3600)  # 1 hora - políticas mudam raramente
```

---

### PERF-035 — CategoriaTicket.objects.all() repetida (views.py)

**Arquivo:** `dashboard/views.py` linhas 699, 820, 863  
**Severidade:** 🟡 MÉDIO

Categorias são carregadas a cada request em múltiplas views.

**Correção:**
```python
def get_categorias():
    return cache.get_or_set(
        'categorias_ticket',
        lambda: list(CategoriaTicket.objects.all()),
        timeout=3600
    )
```

---

## F) MEMORY ISSUES

### PERF-036 — PerfilAgente.tickets_ativos property faz query por acesso (models.py)

**Arquivo:** `dashboard/models.py` linhas 618-622  
**Severidade:** 🔴 CRÍTICO

```python
class PerfilAgente(models.Model):
    @property
    def tickets_ativos(self):
        return Ticket.objects.filter(
            agente=self.user,
            status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO, StatusTicket.AGUARDANDO_CLIENTE]
        ).count()  # ← Query por acesso no template!
```

**Impacto:** Se o template lista 20 agentes, são 20 queries ocultas. Essa property é chamada no dashboard e Kanban.

**Correção:** Usar annotation no queryset:
```python
# Na view:
agentes_qs = PerfilAgente.objects.select_related('user').filter(
    user__is_active=True
).annotate(
    tickets_ativos_count=Count(
        'user__tickets_agente',
        filter=Q(user__tickets_agente__status__in=['aberto', 'em_andamento', 'aguardando_cliente'])
    )
)[:10]

# No template usar {{ agente.tickets_ativos_count }} em vez de {{ agente.tickets_ativos }}
```

---

### PERF-037 — CentroCusto properties fazem queries (models.py)

**Arquivo:** `dashboard/models.py` linhas 1002-1050  
**Severidade:** 🟠 ALTO

```python
@property
def orcamento_utilizado_mes_atual(self):
    total = MovimentacaoFinanceira.objects.filter(
        centro_custo=self, ...
    ).aggregate(total=models.Sum('valor'))['total'] or 0
    return total

@property
def percentual_orcamento_utilizado(self):
    utilizado = self.orcamento_utilizado_mes_atual  # ← chama a query acima!
    # ...

@property
def saldo_orcamento_mensal(self):
    return self.orcamento_mensal - self.orcamento_utilizado_mes_atual  # ← OUTRA query
    
@property  
def status_orcamento(self):
    percentual = self.percentual_orcamento_utilizado  # ← mais 2 queries encadeadas
```

**Impacto:** Cada acesso a um CentroCusto no template pode gerar 4+ queries (orcamento_utilizado → percentual → saldo → status). Lista de 10 centros = 40 queries.

**Correção:** Usar annotations na view:
```python
centros = CentroCusto.objects.filter(status='ativo').annotate(
    gasto_mes=Sum(
        'movimentacoes__valor',
        filter=Q(
            movimentacoes__tipo='despesa',
            movimentacoes__data_movimentacao__month=mes_atual,
            movimentacoes__data_movimentacao__year=ano_atual,
        )
    )
)
# No template: {{ centro.gasto_mes }} e cálculos de percentual no template/view
```

---

### PERF-038 — export_tickets_excel sem .iterator() (api_views.py)

**Arquivo:** `dashboard/api_views.py` linhas 362-395  
**Severidade:** 🟠 ALTO

```python
tickets = Ticket.objects.filter(criado_em__gte=since).select_related(
    "cliente", "agente", "categoria"
).order_by("-criado_em")

for t in tickets:  # ← Carrega TODOS os tickets na memória
    ws.append([...])
```

**Impacto:** Para um período de 365 dias com 100K tickets, consome ~200MB de RAM.

**Correção:**
```python
tickets = Ticket.objects.filter(criado_em__gte=since).select_related(
    "cliente", "agente", "categoria"
).order_by("-criado_em").iterator(chunk_size=1000)
```

---

### PERF-039 — ml_engine carrega DataFrame inteiro em memória

**Arquivo:** `dashboard/ml_engine.py` linhas 122-175  
**Severidade:** 🟠 ALTO

A preparação de dados carrega todos os tickets de 365 dias em uma lista Python, depois cria um DataFrame.

**Correção:** Usar `.iterator()` com chunk_size e processar em batches:
```python
tickets = Ticket.objects.filter(
    criado_em__gte=timezone.now() - timedelta(days=365)
).select_related('cliente', 'agente').iterator(chunk_size=2000)
```

---

### PERF-040 — Kanban carrega tickets sem limite efetivo (views.py)

**Arquivo:** `dashboard/views.py` linhas 690-710  
**Severidade:** 🟡 MÉDIO

```python
# O Kanban faz 5 queries (uma por status), cada uma com [:50]
# Porém, a contagem é feita DEPOIS do slice:
tickets = base_qs.filter(status=status_key)[:50]
kanban_columns.append({
    'count': tickets.count() if hasattr(tickets, 'count') else len(tickets),
    # tickets.count() num queryset sliced faz outra query SEM o slice
})
```

**Correção:**
```python
# Contagem real separada
count = base_qs.filter(status=status_key).count()
tickets = list(base_qs.filter(status=status_key)[:50])
kanban_columns.append({
    'count': count,
    'tickets': tickets,
})
```

Ou melhor, fazer tudo em uma query com conditional aggregation para as contagens.

---

## G) PROBLEMAS ADICIONAIS

### PERF-041 — Signals duplicados no Ticket (signals.py)

**Arquivo:** `dashboard/signals.py`  
**Severidade:** 🟠 ALTO

Há **4 signals `post_save`** registrados para o modelo `Ticket`:
1. `ticket_created_or_updated` (L47)
2. `setup_sla_for_new_ticket` (L329)
3. `track_resolution_time` (L371)
4. `audit_ticket_change` (L614)

Mais 1 `pre_save`:
5. `track_first_response` (L349)

**Impacto:** Cada `ticket.save()` executa 5 handlers com múltiplas queries cada. Um `save()` simples pode gerar 20-30 queries extras.

**Correção:**
1. Consolidar em UM handler `post_save` e UM `pre_save`
2. Mover I/O pesado (notificações, WebSocket) para Celery tasks
3. Usar `update_fields` em saves parciais para evitar triggers desnecessários

---

### PERF-042 — UserListView faz 4 queries de contagem (views.py)

**Arquivo:** `dashboard/views.py` linhas 127-133  
**Severidade:** 🟡 BAIXO

```python
all_users = User.objects.all()
context['total_users'] = all_users.count()
context['active_users'] = all_users.filter(is_active=True).count()
context['staff_users'] = all_users.filter(is_staff=True).count()
context['admin_users'] = all_users.filter(is_superuser=True).count()
```

**Correção:**
```python
context.update(User.objects.aggregate(
    total_users=Count('id'),
    active_users=Count('id', filter=Q(is_active=True)),
    staff_users=Count('id', filter=Q(is_staff=True)),
    admin_users=Count('id', filter=Q(is_superuser=True)),
))
```

---

### PERF-043 — ClientePortalView admin faz muitas queries individuais (views.py)

**Arquivo:** `dashboard/views.py` linhas 1060-1110  
**Severidade:** 🟡 MÉDIO

```python
# Admin view faz ~12 queries separadas
context['tickets_abertos'] = all_tickets.filter(status='aberto').count()
context['tickets_em_andamento'] = all_tickets.filter(status='em_andamento').count()
context['tickets_resolvidos'] = all_tickets.filter(status='resolvido').count()
context['tickets_fechados'] = all_tickets.filter(status='fechado').count()
context['tickets_alta_prioridade'] = all_tickets.filter(prioridade='alta').count()
context['tickets_media_prioridade'] = all_tickets.filter(prioridade='media').count()
context['tickets_baixa_prioridade'] = all_tickets.filter(prioridade='baixa').count()
```

**Correção:** Consolidar com `aggregate`.

---

### PERF-044 — analytics_agent_performance faz N+1 queries (api_views.py)

**Arquivo:** `dashboard/api_views.py` linhas 527-555  
**Severidade:** 🟠 ALTO

```python
agents = User.objects.filter(is_staff=True, is_active=True)
data = []
for agent in agents:  # ← Para cada agente...
    tickets = Ticket.objects.filter(agente=agent, criado_em__gte=since)
    resolved = tickets.filter(status__in=["resolvido", "fechado"])
    # ... 3-4 queries por agente
```

**Correção:**
```python
data = (
    Ticket.objects.filter(criado_em__gte=since, agente__is_staff=True, agente__is_active=True)
    .values('agente__id', 'agente__first_name', 'agente__last_name', 'agente__username')
    .annotate(
        total_tickets=Count('id'),
        resolved=Count('id', filter=Q(status__in=['resolvido', 'fechado'])),
        open=Count('id', filter=Q(status='aberto')),
        avg_resolution_hours=Avg(
            ExpressionWrapper(F('resolvido_em') - F('criado_em'), output_field=DurationField()),
            filter=Q(status__in=['resolvido', 'fechado'], resolvido_em__isnull=False)
        ),
    )
    .order_by('-resolved')
)
```

---

### PERF-045 — auto_assign_ticket queries em cada regra/agente (auto_assignment.py)

**Arquivo:** `dashboard/auto_assignment.py` linhas 50-80  
**Severidade:** 🟡 MÉDIO

```python
for regra in regras:
    if regra_se_aplica(ticket, regra):
        # ...
        for agente in agentes_candidatos:
            carga, created = CargoTrabalho.objects.get_or_create(agente=agente)  # ← Query por agente
```

**Correção:** Prefetch cargas de trabalho:
```python
regras = RegraAtribuicao.objects.filter(ativa=True).select_related('agente_especifico')
# Pré-carregar todas as cargas de trabalho
cargas = {c.agente_id: c for c in CargoTrabalho.objects.filter(disponivel=True)}
```

---

### PERF-046 — relatorio_detalhado sem autenticação e sem cache (analytics_views.py)

**Arquivo:** `dashboard/analytics_views.py` linhas 131-194  
**Severidade:** 🟠 ALTO (segurança + performance)

```python
def relatorio_detalhado(request):  # ← SEM @login_required!
    tickets = Ticket.objects.all()
    # ...
    context = {
        'tickets': tickets.order_by('-criado_em')[:100],  # ← Limita a 100 mas sem select_related
    }
```

**Correção:**
```python
@login_required
def relatorio_detalhado(request):
    tickets = Ticket.objects.select_related('cliente', 'agente', 'categoria')
    # ...
```

---

### PERF-047 — dashboard_financeiro executa ~20 queries complexas (financeiro_views.py)

**Arquivo:** `dashboard/financeiro_views.py` linhas 24-150  
**Severidade:** 🟠 ALTO

O dashboard financeiro executa aproximadamente 20 queries com aggregates complexos a cada carregamento. Muitas dessas queries podem ser cacheadas.

**Correção:**
```python
@login_required
def dashboard_financeiro(request):
    cache_key = f'fin_dashboard_{timezone.now().strftime("%Y%m%d_%H")}'
    cached = cache.get(cache_key)
    if cached:
        return render(request, 'financeiro/dashboard.html', cached)
    
    # ... compute ...
    cache.set(cache_key, context, timeout=600)  # 10 min
    return render(request, 'financeiro/dashboard.html', context)
```

---

## PLANO DE AÇÃO POR PRIORIDADE

### 🔴 Imediato (próximo deploy)
1. **PERF-000** — Corrigir recursão infinita em `_safe_group_send`
2. **PERF-002** — Eliminar carregamento de todos os tickets em `executive_kpis_api`
3. **PERF-012** — Adicionar paginação nas views financeiras
4. **PERF-022** — Adicionar índices compostos no Ticket

### 🟠 Curto prazo (1-2 semanas)
5. **PERF-001** — Eliminar loop de 30 queries em analytics
6. **PERF-003** — Usar `bulk_create` para notificações
7. **PERF-005** — Reescrever reports_service sem N+1
8. **PERF-016** — Consolidar KPIs em single aggregate
9. **PERF-020** — Mover signal handlers para Celery
10. **PERF-029/30/31/32** — Implementar caching nos dashboards
11. **PERF-036** — Substituir property por annotation

### 🟡 Médio prazo (2-4 semanas)
12. **PERF-018** — Isolar ML em processo separado
13. **PERF-023/24/25/26/27/28** — Adicionar índices nos modelos financeiros
14. **PERF-041** — Consolidar signals do Ticket
15. **PERF-037** — Eliminar queries em properties do CentroCusto

---

## ESTIMATIVA DE GANHO

| Ação | Queries/request antes | Queries/request depois | Redução |
|------|----------------------|----------------------|---------|
| Dashboard principal | ~25 | ~5 (+ cache) | 80% |
| Admin dashboard | ~20 | ~4 (+ cache) | 80% |
| Executive dashboard | ~15 + loop | ~5 (+ cache) | 67% |
| Analytics dashboard | ~40 (30 do loop) | ~8 (+ cache) | 80% |
| TicketListView | ~12 | ~3 | 75% |
| Financeiro dashboard | ~20 | ~10 (+ cache) | 50% |
| Ticket save (signals) | ~25 extras | ~3 (async) | 88% |

**Estimativa total:** Redução de **75-85% das queries SQL** nos endpoints mais acessados.

---

*Fim do Relatório de Auditoria de Performance*
