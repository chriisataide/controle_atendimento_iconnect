# Auditoria Completa do Sistema iConnect

**Data:** Julho 2025  
**Auditor:** Arquiteto de Software Sênior / Auditor Técnico  
**Escopo:** Análise funcional, arquitetural, de segurança, performance e evolução estratégica  
**Stack:** Django 5.2.6 · Python 3.13.12 · PostgreSQL · Redis · Celery · Django Channels · Docker Compose

---

## Sumário Executivo

O sistema iConnect é uma plataforma de atendimento ao cliente madura, com ~21.000 linhas de código em views e services, ~45 modelos no core, sistema RBAC definido, criptografia de PII, multi-tenancy, WebSocket em tempo real, módulos financeiro, SLA, chatbot com IA, e gamificação.

**Porém, a auditoria revelou problemas críticos de segurança que exigem ação imediata**, especialmente a **não-aplicação do RBAC** nas views, que permite que qualquer usuário autenticado (incluindo clientes) acesse dados financeiros, administrativos e operacionais do sistema inteiro.

| Severidade | Quantidade |
|---|---:|
| 🔴 Crítico | 6 |
| 🟠 Médio | 15 |
| 🟡 Ajuste Recomendado | 10 |
| 🟢 Melhoria Estratégica | 7 |
| 🏗 Sugestão Arquitetural | 6 |

---

## Estágio 1 — Análise Funcional

### Cobertura de Funcionalidades

| Módulo | Arquivos | Linhas | Status |
|---|---:|---:|---|
| Views (26 arquivos) | 26 | 10.953 | Funcional |
| Services (26 arquivos) | 26 | 9.972 | Funcional |
| Models (12 módulos) | 12 | ~4.500+ | Funcional |
| Testes (10 arquivos) | 10 | 3.326 | **Insuficiente** |
| URLs | 1 (main) | 120+ rotas | Funcional |

**Módulos implementados:** Tickets, SLA, Chat em tempo real, Chatbot IA, Financeiro, Estoque, Equipamentos, Automação, Workflows, Analytics, Executive Dashboard, WhatsApp, Knowledge Base, Push Notifications, Gamificação, Multi-tenancy, Compliance/Auditoria, Webhooks, Mobile.

---

## Estágio 2 — Padrões de Código e Arquitetura

### 🏗 Sugestão Arquitetural 1: Modelos excessivamente concentrados

**Arquivo:** `dashboard/models/base.py` — **2.019 linhas com ~45 modelos**

O arquivo concentra modelos de domínios completamente distintos (Tickets, Financeiro, SLA, Webhooks, IA, Gamificação, E-mail). Isso viola o SRP e dificulta manutenção.

**Recomendação:** Separar em módulos de domínio:
```
models/
  ticket.py       # Ticket, TicketAnexo, InteracaoTicket, StatusTransition, Tag
  sla.py          # SLAPolicy, SLAHistory, SLAAlert, SLAViolation
  financial.py    # CategoriaFinanceira, Contrato, Fatura, Pagamento, etc.
  agent.py        # PerfilAgente, PerfilUsuario, CannedResponse
  integration.py  # WebhookEndpoint, WebhookDelivery, APIKey, EmailAccount
  ai.py           # AIConfiguration, AIInteraction
  gamification.py # GamificationBadge, AgentBadge, AgentLeaderboard
```

### 🏗 Sugestão Arquitetural 2: Views monolíticas

**Arquivos críticos:**
- `views/api.py` — 903 linhas
- `views/financeiro.py` — 810 linhas
- `views/estoque.py` — 627 linhas

**Recomendação:** Dividir por domínio/recurso conforme padrão Django REST:
```
views/api/
  tickets.py
  analytics.py
  sla.py
  webhooks.py
  gamification.py
```

### 🏗 Sugestão Arquitetural 3: Services sem interface consistente

Os 26 services não seguem um contrato comum. Alguns são classes (`TicketService`, `SLAMonitor`), outros são funções soltas, outros são Celery tasks. Não há injeção de dependência.

**Recomendação:** Adotar padrão de Service Layer com interface base e registry.

### 🏗 Sugestão Arquitetural 4: Tenant isolation incompleta

O `TenantAwareMixin` está definido mas **NÃO é aplicado a nenhum modelo existente**. O `Ticket` model não herda de `TenantAwareMixin`. A multi-tenancy é só infraestrutura sem efetivação.

**Recomendação:** Aplicar `TenantAwareMixin` a todos os modelos de negócio ou documentar como single-tenant.

### 🏗 Sugestão Arquitetural 5: Duplicação models/ vs models_pkg/

Existem dois diretórios com modelos duplicados:
- `dashboard/models/` — módulos ativos
- `dashboard/models_pkg/` — cópia paralela

Isso gera confusão e risco de divergência.

### 🏗 Sugestão Arquitetural 6: forms/ vs forms_pkg/

Mesma duplicação nos formulários. Deve-se manter apenas uma fonte de verdade.

---

## Estágio 3 — Segurança (Nível Corporativo)

### 🔴 CRÍTICO 1: RBAC Definido mas NUNCA Aplicado nas Views

**Severidade: CRÍTICA — Risco de acesso não autorizado a TODO o sistema**

O sistema possui um RBAC robusto definido em `dashboard/utils/rbac.py` com 8 papéis (admin, gerente, supervisor, tecnico_senior, agente, financeiro, visualizador, cliente), decoradores (`@role_required`), mixins (`RoleRequiredMixin`), e permissões granulares.

**Porém, após varredura completa dos 26 arquivos de views, o decorator `@role_required` e o mixin `RoleRequiredMixin` NÃO SÃO UTILIZADOS EM NENHUMA VIEW.** Todas as views utilizam apenas `@login_required`.

**Impacto:** Qualquer usuário autenticado — inclusive um **cliente** — pode:
- Acessar o dashboard administrativo
- Ver todos os dados financeiros (receitas, despesas, contratos, faturas)
- Exportar todos os tickets do sistema em Excel
- Gerenciar usuários, agentes e equipes
- Acessar configurações de automação e workflows
- Ver analytics e métricas operacionais
- Gerenciar estoque e equipamentos
- Acessar módulos de compliance e auditoria

**Evidência:**
```bash
# Busca por @role_required ou RoleRequiredMixin em todas as views
$ grep -r "@role_required\|RoleRequiredMixin" dashboard/views/
# Resultado: 0 matches

# Busca por @login_required em todas as views
$ grep -r "@login_required" dashboard/views/
# Resultado: 100+ matches
```

**Correção URGENTE:**
```python
# ANTES (INSEGURO — qualquer usuário logado acessa)
@login_required
def dashboard_financeiro(request):
    ...

# DEPOIS (CORRIGIDO — apenas roles específicas)
@login_required
@role_required('admin', 'financeiro', 'gerente')
def dashboard_financeiro(request):
    ...
```

**Prioridade: P0 — Implementar IMEDIATAMENTE**

---

### 🔴 CRÍTICO 2: IDOR (Insecure Direct Object Reference) em Endpoints da API

**Arquivo:** `dashboard/views/api.py`

Múltiplos endpoints acessam objetos diretamente por `pk` sem verificação de ownership ou role:

| Endpoint | Linha | Risco |
|---|---|---|
| `ticket_time_entries` | ~L492 | Qualquer usuário vê/adiciona time entries de qualquer ticket |
| `ai_triage_ticket` | ~L587 | Qualquer usuário aciona triagem IA em qualquer ticket |
| `ai_suggest_response` | ~L600 | Qualquer usuário obtém sugestões IA de qualquer ticket |
| `ai_summarize_ticket` | ~L610 | Qualquer usuário resumo IA de qualquer ticket |
| `client_health_score` | ~L700 | Qualquer usuário consulta health score de qualquer cliente |

**Correção:**
```python
# ANTES (INSEGURO)
ticket = Ticket.objects.get(pk=pk)

# DEPOIS (CORRIGIDO)
from ..views.helpers import user_can_access_ticket
ticket = get_object_or_404(Ticket, pk=pk)
if not user_can_access_ticket(request.user, ticket):
    return Response({'error': 'Sem permissão'}, status=403)
```

**Prioridade: P0**

---

### 🔴 CRÍTICO 3: Módulo Financeiro Inteiro sem Controle de Acesso

**Arquivo:** `dashboard/views/financeiro.py` — 810 linhas, TODAS as views com apenas `@login_required`

**Dados expostos a qualquer usuário logado:**
- Dashboard financeiro completo com receitas, despesas e margens
- Listagem de todos os contratos e faturas
- Todas as movimentações financeiras
- Relatórios financeiros personalizáveis
- Criação/edição de centros de custo
- APIs de estatísticas financeiras

**Prioridade: P0**

---

### 🔴 CRÍTICO 4: Export de Dados sem RBAC

**Arquivo:** `dashboard/views/api.py` → `export_tickets_excel`

Qualquer usuário autenticado pode exportar **TODOS** os tickets do sistema em formato Excel, sem filtro por role. Inclui dados de clientes, descrições, informações internas.

**Prioridade: P0**

---

### 🔴 CRÍTICO 5: Race Condition na Geração de Número de Ticket

**Arquivo:** `dashboard/models/base.py` → `Ticket.save()`, linha ~337

```python
ultimo = Ticket.objects.select_for_update().aggregate(
    max_num=Max('id')
)['max_num'] or 0
self.numero = f'TK-{ultimo + 1:05d}'
```

**Problemas:**
1. Usa `Max('id')` em vez de `Max` do número sequencial — se tickets forem deletados, IDs terão gaps e os números não serão sequenciais
2. `select_for_update().aggregate()` não faz lock efetivo — `select_for_update` funciona em rows, mas `aggregate` não seleciona rows
3. O `id` (PK auto-increment) já é incrementado pelo banco, tornando a lógica redundante e propensa a duplicações

**Correção recomendada:**
```python
from django.db.models import Max

def save(self, *args, **kwargs):
    with transaction.atomic():
        if not self.numero:
            ultimo_numero = Ticket.objects.select_for_update().aggregate(
                max_num=Max('numero')
            )['max_num']
            if ultimo_numero:
                num = int(ultimo_numero.replace('TK-', '')) + 1
            else:
                num = 1
            self.numero = f'TK-{num:05d}'
        super().save(*args, **kwargs)
```

Ou melhor: usar uma sequência separada no PostgreSQL (`CREATE SEQUENCE ticket_numero_seq`).

**Prioridade: P1**

---

### 🔴 CRÍTICO 6: Auto-assign Referencia Campo Inexistente

**Arquivo:** `dashboard/services/ticket_service.py` → `_auto_assign_agent()`

```python
agentes = PerfilAgente.objects.filter(
    especializacoes__icontains=ticket.categoria.nome,  # ❌ Campo incorreto
    ...
)
```

O campo real do modelo `PerfilAgente` é `especialidades` (ManyToManyField), não `especializacoes`. Além disso, `__icontains` não funciona com M2M fields.

**Resultado:** A auto-atribuição NUNCA funciona baseada em especialidade. O fallback (agente com menos tickets) é sempre usado.

**Correção:**
```python
agentes = PerfilAgente.objects.filter(
    especialidades__nome__icontains=ticket.categoria.nome,
    ...
)
```

**Prioridade: P1**

---

### 🟠 MÉDIO 1: Documentação Swagger/Redoc Pública

**Arquivo:** `dashboard/api/docs.py`

```python
permission_classes=(permissions.AllowAny,),
```

A documentação da API está acessível publicamente, expondo todos os endpoints, schemas e estruturas de dados. Facilita reconhecimento por atacantes.

**Correção:** `permission_classes=(permissions.IsAuthenticated,)` ou `IsAdminOrSupervisor`

---

### 🟠 MÉDIO 2: Tenant Middleware — Spoofing via Header

**Arquivo:** `dashboard/tenants.py` → `TenantMiddleware`

```python
slug = request.META.get('HTTP_X_TENANT_SLUG')
if slug:
    tenant = Tenant.objects.filter(slug=slug, is_active=True).first()
```

Qualquer request pode enviar o header `X-Tenant-Slug` para mudar o contexto do tenant. Não há validação se o usuário pertence ao tenant especificado no header.

**Correção:** Após resolver o tenant via header, verificar `TenantMembership`:
```python
if tenant and request.user.is_authenticated:
    if not TenantMembership.objects.filter(
        tenant=tenant, user=request.user, is_active=True
    ).exists():
        tenant = None  # Negar acesso
```

---

### 🟠 MÉDIO 3: Analytics sem Filtro de Role

**Arquivo:** `dashboard/views/api.py` → `analytics_overview`, `analytics_time_series`, `analytics_satisfaction`

Qualquer usuário autenticado (inclusive clientes) pode ver métricas analíticas gerais do sistema: contagem de tickets de todos os clientes, métricas de SLA, distribuição por status.

**Nota positiva:** `analytics_agent_performance` e `analytics_period_comparison` verificam `_is_admin_or_supervisor` corretamente.

---

### 🟠 MÉDIO 4: Webhook Trigger sem Restrição

**Arquivo:** `dashboard/views/api.py` → `webhook_external_trigger`

Qualquer usuário autenticado pode disparar webhooks/workflows arbitrários.

---

### 🟠 MÉDIO 5: Shared Dashboard — Information Disclosure

**Arquivo:** `dashboard/views/api.py` → `shared_dashboard_view`

Endpoint **público** (sem autenticação) que expõe contagem de tickets por status e prioridade. Protegido apenas por token no URL. Se o token vazar, dados operacionais são expostos.

**Recomendação:** Adicionar expiração ao token, rate limiting e logging de acessos.

---

### 🟠 MÉDIO 6: Bulk Actions sem Validação

**Arquivo:** `dashboard/views/api.py` → `bulk_action_tickets`

Na action `assign`, o valor é passado diretamente como `agente_id` sem validar se o user existe ou está ativo:
```python
elif action == "assign":
    tickets.update(agente_id=value)  # Sem validação
```

---

### 🟠 MÉDIO 7: Criptografia sem Chave Dedicada

**Arquivo:** `dashboard/utils/crypto.py`

```python
key = getattr(settings, 'FIELD_ENCRYPTION_KEY', None)
if not key:
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()[:32]
```

Se `FIELD_ENCRYPTION_KEY` não estiver configurada, a chave de criptografia é derivada do `SECRET_KEY`. Se o `SECRET_KEY` mudar (rotação), todos os dados criptografados ficam **irrecuperáveis**.

**Agravante:** Não há mecanismo de rotação de chaves. Sem re-encrypt de dados existentes.

---

### 🟠 MÉDIO 8: Múltiplos post_save no Ticket sem Ordenação

**Arquivo:** `dashboard/signals.py`

O modelo `Ticket` tem **4+ handlers no `post_save`:**
1. `ticket_created_or_updated` — notificações WebSocket + Celery
2. `setup_sla_for_new_ticket` — criação automática de SLA
3. `track_resolution_time` — tracking de tempo de resolução
4. `audit_ticket_change` — registro de auditoria

Django não garante ordem de execução de signals. Se o SLA ainda não existir quando a notificação é enviada, pode haver dados inconsistentes.

**Recomendação:** Consolidar em um único handler dispatcher ou usar `django.dispatch.Signal` com ordering.

---

### 🟠 MÉDIO 9: `get_dashboard_metrics()` Retorna Dados Falsos

**Arquivo:** `dashboard/views/helpers.py`

```python
except ImportError:
    return {
        'total_tickets': 0,
        'open_tickets': 0,
        # ... hardcoded zeros
    }
```

Em caso de `ImportError`, a função retorna dados zerados silenciosamente, mascarando erros. O dashboard mostra "0 tickets" em vez de informar o erro.

---

### 🟠 MÉDIO 10: SLAViolation Sem `time_exceeded`

**Arquivo:** `dashboard/services/sla.py` → `monitor_sla_violations`

O `SLAViolation` é criado sem popular o campo `time_exceeded` (DurationField). Isso pode causar `IntegrityError` se o campo for NOT NULL, ou dados incompletos para relatórios de compliance.

---

### 🟠 MÉDIO 11: `log_suspicious_activity` — Ruído

**Arquivo:** `dashboard/utils/security.py`

O decorator `@log_suspicious_activity` registra **TODOS** os requests na view como "atividade suspeita" no cache, não apenas atividades realmente suspeitas. Isso gera ruído e torna o monitoramento inútil.

Além disso, os logs ficam apenas no cache Redis com TTL de 1 hora — sem persistência.

**Nota:** O sistema TEM persistência de audit via `AuditEvent` no banco (usado nos signals), mas o utilities de segurança não o utiliza. Há duplicidade de mecanismos de audit.

---

### 🟠 MÉDIO 12: CSRF_COOKIE_HTTPONLY=True

**Arquivo:** `controle_atendimento/settings_base.py`

```python
CSRF_COOKIE_HTTPONLY = True
```

Com esta configuração, JavaScript não pode ler o cookie CSRF. Para forms tradicionais isso é OK (Django usa hidden field), mas para chamadas AJAX/fetch, o frontend não pode obter o token via `document.cookie`. O `api.py` usa DRF com `@api_view` que pode depender deste token.

**Recomendação:** Verificar se o frontend usa `X-CSRFToken` header via meta tag ou desabilitar para requisições AJAX.

---

### 🟠 MÉDIO 13: DashboardConsumer — `send_dashboard_update` Duplicado e Incorreto

**Arquivo:** `dashboard/consumers.py` → `DashboardConsumer`

O método `send_dashboard_update` está definido duas vezes:
1. Primeiro como método que busca estatísticas do banco
2. Depois como handler de group message que simplesmente retransmite

Mas o segundo é definido fora do bloco try/except do primeiro, com indentação incorreta. Resultado: o handler de group sobrescreve o método utility.

---

### 🟠 MÉDIO 14: `save_file_message` Não Implementado

**Arquivo:** `dashboard/consumers.py` → `ChatConsumer`

```python
async def save_file_message(self, file_data, file_name, file_type):
    """Salva mensagem com arquivo"""
    # Implementar upload de arquivo
    # Por enquanto, retorna None
    return None
```

Upload de arquivo via WebSocket está stub. Se o frontend enviar `file_upload`, o backend silenciosamente ignora.

---

### 🟠 MÉDIO 15: Validadores de Senha Fracos

**Arquivo:** `controle_atendimento/settings_base.py`

```python
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
```

O `MinimumLengthValidator` usa o padrão de 8 caracteres. Para sistema corporativo, recomenda-se 12+ caracteres. Não há validação de complexidade (maiúsculas + números + símbolos).

---

## Estágio 4 — Performance

### 🟡 AJUSTE 1: N+1 Queries no Dashboard

**Arquivo:** `dashboard/views/dashboard.py` → `DashboardView.get_context_data`

O dashboard faz ~20+ queries separadas no `get_context_data`:
- Total de tickets (1 query)
- Tickets por status (5 queries)
- Tickets por prioridade (4 queries)
- Agentes ativos (1 query)
- SLA stats (2-3 queries)
- Resolvidos hoje/semana (2 queries)
- Tempo médio (1 query)
- E mais...

**Recomendação:** Consolidar em 2-3 queries com `annotate()`, `Subquery`, ou usar cache com invalidação:
```python
from django.db.models import Case, When, IntegerField, Count

stats = Ticket.objects.aggregate(
    total=Count('id'),
    abertos=Count(Case(When(status='aberto', then=1), output_field=IntegerField())),
    em_andamento=Count(Case(When(status='em_andamento', then=1), output_field=IntegerField())),
    # ... etc
)
```

### 🟡 AJUSTE 2: N+1 no Heatmap Analytics

**Arquivo:** `dashboard/views/helpers.py` → `get_analytics_data()`

Executa 7 × 12 = **84 queries individuais** para construir o heatmap (uma por dia da semana × hora):
```python
for day in range(7):
    for hour in range(0, 24, 2):
        count = tickets.filter(
            criado_em__week_day=day+1,
            criado_em__hour__gte=hour,
            criado_em__hour__lt=hour+2
        ).count()
```

**Recomendação:** Uma única query com `annotate` + `ExtractWeekDay` + `ExtractHour`.

### 🟡 AJUSTE 3: Ticket.save() com Transaction Desnecessário

Cada `Ticket.save()` abre uma transação atômica (`with transaction.atomic()`), mesmo quando o número já existe. A geração de número deveria ser condicional.

### 🟡 AJUSTE 4: `_calculate_avg_resolution_time` Itera em Python

**Arquivo:** `dashboard/services/sla.py`

Calcula tempo médio de resolução iterando tickets em Python, fazendo `timedelta` arithmetic. Deveria usar `Avg(F('resolvido_em') - F('criado_em'))` no banco.

### 🟡 AJUSTE 5: WebSocket `get_dashboard_statistics` Sem Cache

**Arquivo:** `dashboard/consumers.py` → `NotificationConsumer`

Cada WebSocket connection e cada `request_stats` faz 5 queries ao banco. Com 50 agentes conectados, são 250 queries imediatas. Deveria usar `cache_service` existente.

---

## Estágio 5 — Melhorias e Evolução

### 🟡 AJUSTE 6: Services Bypassed

O `TicketService` existe mas muitas views fazem operações diretas no modelo:
- `TicketCreateView.form_valid` processa uploads e JSON inline
- `update_ticket_status` em `tickets.py` faz validação e update diretamente
- `add_interaction` não usa nenhum service

**Recomendação:** Toda lógica de negócio deve passar pelo service layer. Views devem ser finas.

### 🟡 AJUSTE 7: Cobertura de Testes Crítica

| Área | Linhas | Testes | Cobertura Estimada |
|---|---:|---:|---|
| Services (26 arquivos) | 9.972 | 12 métodos | **~2%** |
| Views (26 arquivos) | 10.953 | 20 + 140 (legacy) | ~15% |
| Models | ~4.500 | 29 métodos | ~20% |
| API | 903 | 16 métodos | ~30% |

O `test_legacy.py` concentra **49% dos testes** (140 de 287). Os services com 9.972 linhas têm apenas 12 testes.

**Recomendação:** Meta de 70% de cobertura para services e views críticas. Testes prioritários:
1. RBAC enforcement (quando implementado)
2. TicketService operations
3. SLA calculations
4. Financial operations
5. Tenant isolation

### 🟡 AJUSTE 8: `send_dashboard_update()` Nunca Conectada

**Arquivo:** `dashboard/signals.py`

Função `send_dashboard_update()` definida mas nunca conectada a nenhum signal. Dashboard updates em tempo real não funcionam via signals.

### 🟡 AJUSTE 9: KPIs em TicketListView Ignoram RBAC

**Arquivo:** `dashboard/views/tickets.py` → `TicketListView.get_context_data`

Computa KPIs em `Ticket.objects.all()` ao invés de usar o queryset filtrado por RBAC. Um agente vê contadores de TODOS os tickets, não apenas os seus.

### 🟡 AJUSTE 10: ProfileView sem Form Validation

**Arquivo:** `dashboard/views/auth_profile.py` → `ProfileView._handle_profile_update`

Usa `request.POST.get()` diretamente sem Form/Serializer Django. Não há validação de tamanho, formato ou sanitização além do que o ORM faz.

---

## 🟢 Melhorias Estratégicas

### 🟢 ESTRATÉGICA 1: Implementar API Versionada

A API atual não tem versionamento. Mudanças breaking afetam todos os clientes.

**Recomendação:**
```
/api/v1/tickets/
/api/v2/tickets/
```
Usar DRF Versioning (`URLPathVersioning` ou `AcceptHeaderVersioning`).

### 🟢 ESTRATÉGICA 2: CQRS para Dashboard

O dashboard current faz 20+ queries síncronas. Implementar Command/Query Separation:
- **Commands:** service layer (create/update via Celery)
- **Queries:** views materializadas no PostgreSQL ou cache Redis pré-computado

### 🟢 ESTRATÉGICA 3: Observabilidade (OpenTelemetry)

Adicionar distributed tracing com OpenTelemetry para:
- Rastrear tempo de cada query no dashboard
- Correlacionar requests HTTP → WebSocket → Celery tasks
- Alertas automáticos de degradação

### 🟢 ESTRATÉGICA 4: Row-Level Security no PostgreSQL

Além do RBAC no Django, implementar RLS no PostgreSQL para defesa em profundidade:
```sql
CREATE POLICY tenant_isolation ON dashboard_ticket
    USING (tenant_id = current_setting('app.current_tenant_id')::int);
```

### 🟢 ESTRATÉGICA 5: Feature Flags

Implementar feature flags (django-waffle ou custom) para:
- Deploy progressivo de novas funcionalidades
- A/B testing
- Desabilitar módulos por tenant/plano
- Kill switch para features problemáticas

### 🟢 ESTRATÉGICA 6: Health Check Endpoints

Adicionar endpoints de health check para monitoramento:
```
/health/           → Status geral
/health/db/        → PostgreSQL
/health/redis/     → Redis
/health/celery/    → Workers
/health/websocket/ → Channels
```

### 🟢 ESTRATÉGICA 7: Rate Limiting por Endpoint

O `rate_limit` decorator atual é genérico. Implementar limites específicos por endpoint e por role:
```python
@rate_limit(max_requests=100, window=60)   # 100/min para admin
@rate_limit(max_requests=30, window=60)    # 30/min para agente
@rate_limit(max_requests=10, window=60)    # 10/min para cliente
```

---

## 📌 Plano de Ação Priorizado

### Fase 1 — Emergência (1-2 semanas)
> **Objetivo: Corrigir vulnerabilidades críticas de segurança**

| # | Ação | Severidade | Esforço | Arquivos |
|---|---|---|---|---|
| 1 | Aplicar `@role_required` em TODAS as views | 🔴 P0 | 3-4 dias | 26 arquivos de views |
| 2 | Corrigir IDORs na API | 🔴 P0 | 1 dia | `views/api.py` |
| 3 | Proteger módulo financeiro | 🔴 P0 | 0.5 dia | `views/financeiro.py` |
| 4 | Proteger export de dados | 🔴 P0 | 0.5 dia | `views/api.py` |
| 5 | Corrigir referência `especializacoes` | 🔴 P1 | 0.5 dia | `services/ticket_service.py` |
| 6 | Corrigir Ticket.numero race condition | 🔴 P1 | 1 dia | `models/base.py` |

### Fase 2 — Estabilização (2-4 semanas)
> **Objetivo: Solidificar segurança e corrigir falhas médias**

| # | Ação | Severidade | Esforço |
|---|---|---|---|
| 7 | Validar tenant no header X-Tenant-Slug | 🟠 | 0.5 dia |
| 8 | Proteger Swagger (IsAuthenticated) | 🟠 | 0.5 hora |
| 9 | Validar bulk actions | 🟠 | 0.5 dia |
| 10 | Configurar FIELD_ENCRYPTION_KEY dedicada | 🟠 | 1 dia |
| 11 | Consolidar signals do Ticket | 🟠 | 1 dia |
| 12 | Corrigir SLAViolation.time_exceeded | 🟠 | 0.5 dia |
| 13 | Refatorar `log_suspicious_activity` | 🟠 | 0.5 dia |
| 14 | Aumentar mínimo de senha para 12 chars | 🟠 | 0.5 hora |
| 15 | Revisar CSRF_COOKIE_HTTPONLY com AJAX | 🟠 | 1 dia |

### Fase 3 — Performance e Qualidade (1-2 meses)
> **Objetivo: Otimizar queries, aumentar testes**

| # | Ação | Severidade | Esforço |
|---|---|---|---|
| 16 | Consolidar queries do Dashboard | 🟡 | 2 dias |
| 17 | Reescrever heatmap analytics (1 query) | 🟡 | 1 dia |
| 18 | Cache em WebSocket stats | 🟡 | 0.5 dia |
| 19 | Migrar lógica de views para services | 🟡 | 1 semana |
| 20 | Escrever testes para services (meta 70%) | 🟡 | 2 semanas |
| 21 | Corrigir KPIs TicketListView com RBAC filter | 🟡 | 0.5 dia |
| 22 | Refatorar test_legacy.py em módulos | 🟡 | 1 semana |

### Fase 4 — Evolução Estratégica (2-4 meses)
> **Objetivo: Escalar para produção enterprise**

| # | Ação | Severidade | Esforço |
|---|---|---|---|
| 23 | Separar models/base.py em domínios | 🏗 | 1 semana |
| 24 | Limpar duplicação models/ vs models_pkg/ | 🏗 | 2 dias |
| 25 | API versionada (v1/v2) | 🟢 | 1 semana |
| 26 | CQRS para dashboard | 🟢 | 2 semanas |
| 27 | OpenTelemetry integration | 🟢 | 1 semana |
| 28 | Feature flags | 🟢 | 1 semana |
| 29 | Health check endpoints | 🟢 | 1 dia |
| 30 | Row-Level Security PG | 🟢 | 2 semanas |

---

## Pontos Positivos Identificados

Apesar dos problemas, o sistema tem fundações sólidas:

1. **Infraestrutura RBAC bem projetada** — O `rbac.py` é bem estruturado com roles, permissions, decorators e mixins. O problema é só a não-aplicação nas views.

2. **Criptografia PII implementada** — Campos sensíveis (telefone, CPF) usam Fernet/AES com `EncryptedCharField`. O `encrypt_on_save` nos models é correto.

3. **SecurityHeadersMiddleware robusta** — CSP com nonce, X-Frame-Options DENY, X-Content-Type-Options, Referrer-Policy strict-origin.

4. **Validação de upload completa** — Verifica extensão, MIME type, magic bytes E conteúdo malicioso (PHP tags, script injection).

5. **SoftDeleteModel para compliance** — Padrão BACEN para dados financeiros com audit trail completo.

6. **Audit trail persistente** — `AuditEvent`, `SecurityAlert`, `ComplianceReport`, `DataAccessLog` com indexes otimizados.

7. **Multi-tenancy arquitetada** — `Tenant`, `TenantMembership`, `TenantAwareMixin`, `TenantMiddleware` — infraestrutura pronta, falta só aplicar.

8. **WebSocket bem implementados** — `NotificationConsumer`, `TicketChatConsumer`, `ChatConsumer`, `AgentStatusConsumer` com autenticação adequada e verificação de acesso.

9. **SLA Monitor com business hours** — Cálculo de deadlines considerando horário comercial e feriados.

10. **Celery com fallback síncrono** — Tasks que funcionam mesmo sem worker Celery ativo.

---

## Métricas do Sistema

| Métrica | Valor |
|---|---|
| Total de modelos | ~60+ |
| Total de views | 26 arquivos / 10.953 linhas |
| Total de services | 26 arquivos / 9.972 linhas |
| Total de testes | 287 métodos / 3.326 linhas |
| Razão teste/código | ~15.9% (linhas) |
| URLs registradas | 120+ |
| Roles RBAC definidos | 8 |
| Roles RBAC **aplicados** | **0** ⚠️ |
| Modelos com criptografia PII | 3 (PontoDeVenda, Cliente, PerfilUsuario) |
| WebSocket consumers | 5 |
| Celery tasks | 10+ |
| TODOs pendentes no código | 4 (service worker PWA) |

---

*Relatório gerado em Julho 2025. Próxima revisão recomendada após implementação da Fase 1.*
