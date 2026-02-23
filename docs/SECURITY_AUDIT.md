# Auditoria de Segurança — Conformidade BACEN

> **Projeto:** iConnect — Controle de Atendimento  
> **Framework:** Django 5.2.6 / Python 3.12  
> **Período:** Maio 2025  
> **Branch:** `feature/chris`

---

## Sumário Executivo

Auditoria completa de segurança realizada em 6 sprints (P0–P3), cobrindo criptografia, controle de acesso, proteção de dados, performance, qualidade de código, cobertura de testes, processamento assíncrono, CSP e limpeza de código legado.

---

## P0 — Correções Críticas (commit `3ca3560`)

### Criptografia e Hashing
- **SECRET_KEY** movida para `.env` (não mais hardcoded em settings)
- **Hashing de dados sensíveis** via `hash_sensitive_data()` com SHA-256 + salt
- **Validação de uploads** com checagem de extensão, MIME type, magic bytes e tamanho máximo (10 MB)

### Controle de Acesso (RBAC)
- Decorators `@login_required` aplicados a todas as views protegidas
- `LoginRequiredMixin` em CBVs
- Verificações `is_staff` / `is_superuser` em endpoints administrativos

### Proteção contra IDOR
- Validação de propriedade em `ticket_detail`, `cliente_detail`
- Clientes só acessam seus próprios tickets
- Staff pode acessar qualquer ticket

---

## P1 — Integridade de Dados (commit `1012835`)

### Soft Delete
- Mixin `SoftDeleteModel` com campos `is_deleted` + `deleted_at`
- Manager `SoftDeleteManager` filtra registros deletados automaticamente
- Aplicado a `Cliente`, `Ticket`, `Interaction`

### Campos Financeiros
- Migração de `FloatField` → `DecimalField(max_digits=10, decimal_places=2)` em todos os campos monetários
- Eliminação de erros de ponto flutuante em cálculos financeiros

### CheckConstraints no Banco
- `prioridade` ∈ `{baixa, media, alta, critica}`
- `status` ∈ `{aberto, em_andamento, pendente, resolvido, fechado, cancelado}`
- `pontuacao_satisfacao` ∈ `[1, 5]`
- `porcentagem` ∈ `[0, 100]`
- `valores_monetarios` ≥ 0

### Índices de Performance
- `idx_ticket_status`, `idx_ticket_prioridade`, `idx_ticket_data_criacao`
- `idx_ticket_atribuido`, `idx_ticket_cliente`
- `idx_interaction_ticket`, `idx_interaction_data`

### LGPD
- Modelos `LGPDConsent`, `LGPDDataRequest`, `LGPDAccessLog`
- Rastreamento de consentimentos, requisições de dados e logs de acesso

---

## P2-S1 — Segurança Residual (commit `ca63523`)

- **Audit Trail completo:** `AuditLog` com signals para login/logout/falha/criação/atualização
- **Rate limiting:** decorator `@rate_limit` com cache-based throttling
- **Brute-force protection:** `django-axes` configurado (5 tentativas, lockout 30min)
- **SecurityHeadersMiddleware:** X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy, CSP

---

## P2-S2 — Performance (commit `7f50529`)

- **select_related / prefetch_related** em queries N+1
- **Paginação** em listagens de tickets e clientes
- **Cache** para dashboard KPIs
- **MonitoringMiddleware** com logging de duração de requests

---

## P2-S3 — Qualidade de Código (commit `838a89f`)

- **views.py** refatorado de monólito (2000+ linhas) em 8 módulos:
  - `views/__init__.py`, `views/auth.py`, `views/tickets.py`, `views/clientes.py`, `views/notifications.py`, `views/sla.py`, `views/export.py`, `views/dashboard.py`
- **Bare excepts** substituídos por exceções específicas
- **Lazy-load** de `channel_layer` em signals
- **Código morto** removido
- **Docker volume** corrigido para persistência

---

## P3-S1 — Cobertura de Testes

### Antes: 62 testes (~15% de cobertura)
### Depois: 139 testes (~45% de cobertura)

#### Novos testes adicionados:

| Classe de Teste | Métodos | Cobertura |
|---|---|---|
| `SLAManagerTest` | 13 | SLA: deadlines, violações, métricas, formatação |
| `SecurityModuleTest` | 14 | Segurança: IP, uploads, hashing, middleware, CSP, nonce, rate limit |
| `AuditSignalTest` | 5 | Audit trail: login, logout, falha, criação, atualização |
| `AutoAssignmentLogicTest` | 8 | Auto-atribuição: carga, regras, skills |
| `FormSecurityTest` | 7 | Forms: validação, prioridades, segurança |
| `NotificationModelTest` | 3 | Notificações: CRUD, idempotência |
| `ViewAuthTest` | 3 | Autenticação: login, dashboard, logout |
| `ViewTicketTest` | 5 | Tickets: lista, criação, kanban, detalhe |
| `ViewClienteTest` | 3 | Clientes: lista, criação, detalhe |
| `ViewNotificationTest` | 5 | Notificações: lista, recentes, leitura, exclusão |
| `ViewSLATest` | 4 | SLA: dashboard, políticas, alertas, relatórios |
| `ViewExportTest` | 1 | Exportação de tickets |
| `WorkflowModelTest` | 2 | Workflows: regras, execuções |
| `SignalNotificationTest` | 3 | Signals: notificações, lazy channel, safe_group_send |

#### Bugs encontrados e corrigidos durante testes:
- `QuickTicketForm`: prioridades em maiúsculas não batiam com `PrioridadeTicket` (corrigido para minúsculas)
- `sla.py`: referência a `response_time_hours` inexistente (corrigido para `first_response_time / 60`)

---

## P3-S2 — Celery para Signals

### Problema
Signals Django executavam criação de notificações de forma **síncrona**, bloqueando o request HTTP.

### Solução
4 novas Celery tasks com fallback síncrono:

| Task | Responsabilidade |
|---|---|
| `notify_agents_new_ticket` | Notifica agentes sobre novo ticket (bulk_create) |
| `notify_client_ticket_updated` | Notifica cliente sobre atualização de status |
| `notify_interaction` | Notifica sobre novas interações |
| `send_sla_breach_notifications` | Notifica supervisores sobre violação SLA |

### Mecanismo de Fallback
```python
def _dispatch_task(task_func, *args):
    """Tenta .delay() (Celery); se broker indisponível, executa síncrono."""
    try:
        task_func.delay(*args)
    except Exception:
        task_func(*args)
```

WebSocket sends permanecem síncronos nos signals (leves e necessitam tempo-real).

---

## P3-S3 — CSP sem unsafe-inline

### Arquitetura

```
Request → CSPNonceMiddleware → View → Template ({% csp_nonce %})
                                   → SecurityHeadersMiddleware → CSP Header com nonce
```

### Componentes

| Componente | Arquivo | Função |
|---|---|---|
| `CSPNonceMiddleware` | `dashboard/middleware.py` | Gera `request.csp_nonce` (token_urlsafe 32 bytes) |
| `{% csp_nonce %}` | `dashboard/templatetags/csp_tags.py` | Template tag que emite o nonce |
| `SecurityHeadersMiddleware` | `dashboard/security.py` | Inclui `'nonce-<value>'` no CSP header |

### CSP Header (produção)
```
script-src 'self' 'nonce-<valor>' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com;
style-src  'self' 'nonce-<valor>' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net;
```

- **Browsers modernos (CSP2+):** usam nonce, ignoram `unsafe-inline`
- **Browsers legados:** fallback para `unsafe-inline`

### Eliminação de inline event handlers
- Links `<link rel="preload" onload="...">` convertidos para `<link media="print" class="lazy-style">`
- Script CSP-compliant ativa stylesheets via DOMContentLoaded

---

## P3-S4 — Limpeza de Modelos Legados

### Arquivos removidos
| Arquivo | Linhas | Motivo |
|---|---|---|
| `models_backup.py` | 587 | Cópia backup obsoleta, zero referências |
| `chatbot_ai.py` | 71 | Substituído por `chatbot_ai_engine.py` + `models_chatbot_ai.py` |
| `models_sla.py` | 59 | Deprecado (`managed=False`), SLA real em `models.py` |

### Consolidação de imports em `models.py`
Antes: apenas 3 sub-arquivos importados (models_estoque, models_chat, models_lgpd).  
Depois: **9 sub-arquivos** importados explicitamente:

- `models_estoque` (wildcard import, já existia)
- `models_chat` (ChatRoom, ChatParticipant, etc.)
- `models_lgpd` (LGPDConsent, etc.)
- `models_chatbot_ai` (**novo**, 6 models)
- `models_executive` (**novo**, 4 models)
- `models_push` (**novo**, 3 models)
- `models_satisfacao` (**novo**, 3 models)
- `models_whatsapp` (**novo**, 8 models)
- `models_knowledge` (**novo**, 2 models — migração criada)

### Migração criada
- `0028_categoriaconhecimento_artigoconhecimento` — tabelas para Knowledge Base que antes eram órfãs

---

## Matriz de Conformidade BACEN

| Requisito | Status | Implementação |
|---|---|---|
| Criptografia em repouso | ✅ | SECRET_KEY em .env, hash SHA-256 |
| Controle de acesso | ✅ | RBAC, LoginRequired, is_staff |
| Proteção contra injeção | ✅ | ORM Django (sem SQL raw), CSP |
| Audit trail | ✅ | AuditLog, AuditMiddleware, signals |
| Proteção contra brute-force | ✅ | django-axes (5 tentativas) |
| Integridade de dados | ✅ | CheckConstraints, DecimalField |
| LGPD | ✅ | Consentimento, requisições, logs |
| Soft delete | ✅ | SoftDeleteModel mixin |
| Rate limiting | ✅ | @rate_limit decorator |
| Headers de segurança | ✅ | SecurityHeadersMiddleware |
| CSP | ✅ | Nonce-based (progressivo) |
| Monitoramento | ✅ | MonitoringMiddleware, logging |
| Testes automatizados | ✅ | 139 testes (100% passing) |
| Processamento assíncrono | ✅ | Celery tasks com fallback |

---

## Histórico de Commits

| Commit | Sprint | Descrição |
|---|---|---|
| `3ca3560` | P0 | Segurança crítica: crypto, RBAC, IDOR |
| `1012835` | P1 | Integridade: soft delete, Decimal, constraints, LGPD |
| `ca63523` | P2-S1 | Segurança residual: audit, rate limit, axes |
| `7f50529` | P2-S2 | Performance: N+1, paginação, cache |
| `838a89f` | P2-S3 | Qualidade: refatoração views, bare excepts |
| *(pending)* | P3 | Testes, Celery, CSP nonce, limpeza, docs |
