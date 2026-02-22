# 🗺️ ROADMAP — iConnect Helpdesk Enterprise

> **Objetivo:** Transformar o iConnect de um helpdesk funcional em um software de classe enterprise, competitivo com Zendesk, Freshdesk e Jira Service Management.
>
> **Data:** Fevereiro 2026
>
> **Stack atual:** Django 5.2.6 · Python 3.12 · SQLite (dev) / PostgreSQL (prod) · Redis · Celery · Channels · DRF · Material Dashboard 2 Slate+Cyan

---

## 📊 Estado Atual — Snapshot

| Área | Status | Nota |
|------|--------|------|
| Tickets CRUD | ✅ Funcional | Criação, listagem, detalhe, edição, exportação CSV |
| SLA | ⚠️ Duplicado | 2 sistemas independentes (`SLAPolicy` + `SLA/MetricaSLA`) |
| Base de Conhecimento | ⚠️ Fragmentada | 3 modelos não integrados |
| Chat Real-time | ✅ Funcional | WebSocket via Channels, chat rooms, read receipts |
| WhatsApp | ✅ Funcional | Webhook, templates, auto-response, analytics |
| Chatbot IA | ⚠️ Básico | Regex/keyword matching, sem LLM real |
| Automação/Workflows | ✅ Funcional | Motor JSON-based, 7 triggers, 6 tipos de ação |
| API REST | ❌ Vazio | `api_views.py` sem conteúdo |
| Busca Avançada | ❌ Quebrado | Referencia modelos inexistentes |
| Relatórios Avançados | ❌ Quebrado | Referencia modelos inexistentes |
| Portal do Cliente | ⚠️ Parcial | Cliente não vinculado a User |
| Segurança | ⚠️ Básica | Sem RBAC, sem 2FA, audit em cache volátil |
| Testes | ❌ Mínimo | Apenas 3 unit tests |
| Mobile/PWA | ✅ Funcional | Templates dedicados, push notifications |
| Módulo Financeiro | ✅ Funcional | Contratos, faturas, movimentações, centros de custo |
| Módulo Estoque | ✅ Funcional | Produtos, movimentações, estoque crítico |

---

## 🏗️ FASE 1 — Fundação Sólida (Semanas 1-3)

> **Meta:** Corrigir código quebrado, eliminar redundâncias, garantir que tudo funciona.

### 1.1 Corrigir Código Quebrado

| # | Tarefa | Arquivo(s) | Esforço |
|---|--------|-----------|---------|
| 1 | Corrigir `search_service.py` — substituir `Customer`→`Cliente`, `Agent`→`User`, `created_at`→`criado_em`, `assigned_to`→`agente`, `ticket_number`→`numero` | `dashboard/search_service.py` | 2h |
| 2 | Corrigir `reports_service.py` — mesmas substituições de nomes de modelo/campos | `dashboard/reports_service.py` | 2h |
| 3 | Adicionar campo `tipo` ao `InteracaoTicket` — choices: `resposta`, `nota_interna`, `sistema`, `status_change` | `dashboard/models.py` + migração | 1h |
| 4 | Adicionar campo `canal` ao `InteracaoTicket` — choices: `web`, `email`, `whatsapp`, `chat`, `api` | `dashboard/models.py` + migração | 30min |
| 5 | Adicionar `psycopg2-binary` ao `requirements.txt` | `requirements.txt` | 5min |
| 6 | Mover models de `services/advanced_audit_service.py` para `dashboard/audit_models.py` | `audit_models.py`, `services/` | 1h |

### 1.2 Unificar Sistemas Duplicados

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 7 | **Unificar SLA** — Manter `SLAPolicy` (mais completo) de `models.py`, deprecar `SLA`+`MetricaSLA` de `models_sla.py` | Migrar referências, mover lógica útil do sla.py para `services/sla_calculator.py` | 4h |
| 8 | **Unificar KB** — Manter `ArtigoConhecimento` de `models_knowledge.py` como modelo principal, migrar dados de `KnowledgeBase` e `ChatbotKnowledgeBase` | Criar FK do chatbot para ArtigoConhecimento | 3h |
| 9 | **Unificar Auto-assignment** — Consolidar `auto_assignment.py` e `automation.py` em um único `services/assignment_service.py` | Manter skills/competências do auto_assignment.py | 3h |
| 10 | **Unificar Chatbot** — Consolidar `chatbot_ai_engine.py` e `automation.py/ChatbotService` em `services/chatbot_service.py` | Manter a engine mais sofisticada | 2h |

### 1.3 Limpar Projeto

| # | Tarefa | Esforço |
|---|--------|---------|
| 11 | Remover todos os arquivos `.bak` do diretório templates/ | 15min |
| 12 | Organizar imports e remover código morto | 2h |
| 13 | Configurar Celery para dev com `CELERY_TASK_ALWAYS_EAGER = True` em `settings_dev.py` | 15min |

**Resultado da Fase 1:** Zero código quebrado, zero redundância, base limpa para construir.

---

## 🔒 FASE 2 — Segurança & Controle de Acesso (Semanas 3-5)

> **Meta:** RBAC, audit trail, 2FA — fundação de segurança enterprise.

### 2.1 RBAC — Role-Based Access Control

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 14 | Criar `Role` model com permissões granulares | Roles: `admin`, `supervisor`, `agente`, `cliente` | 3h |
| 15 | Criar Django Groups pré-configurados | Um Group por Role com permissões específicas | 2h |
| 16 | Criar decorator `@role_required('admin', 'supervisor')` | Substituir checks `is_staff`/`is_superuser` manuais | 2h |
| 17 | Criar mixin `RoleRequiredMixin` para CBVs | Para class-based views | 1h |
| 18 | Migrar TODAS as views para usar novo RBAC | ~50 views a atualizar | 6h |
| 19 | Adicionar tela de gestão de roles no Admin | Atribuir roles a usuários | 3h |

**Permissões por Role:**

```
Admin:        TUDO (gestão de sistema, usuários, configurações)
Supervisor:   Ver todos os tickets, reatribuir, ver relatórios, gerenciar agentes
Agente:       Ver tickets atribuídos, responder, usar KB, ver próprias métricas
Cliente:      Ver próprios tickets, criar tickets, consultar KB pública, avaliar
```

### 2.2 Audit Trail Persistente

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 20 | Implementar model `AuditLog` em `audit_models.py` | user, action, model, object_id, old_values, new_values, ip, timestamp | 2h |
| 21 | Criar middleware `AuditMiddleware` que persiste em banco | Substituir o atual que só loga no console | 3h |
| 22 | Signal `post_save`/`post_delete` para audit automático de Ticket, InteracaoTicket, SLAPolicy | Log toda alteração crítica automaticamente | 3h |
| 23 | Tela de visualização de audit logs no admin | Filtro por usuário, período, modelo, ação | 3h |

### 2.3 Autenticação Avançada

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 24 | Implementar 2FA com `django-otp` + TOTP (Google Authenticator) | Obrigatório para admin/supervisor, opcional para agentes | 4h |
| 25 | Session management — forçar logout, listar sessões ativas | Lista de dispositivos/sessões do usuário | 3h |
| 26 | Password policy reforçada — complexidade, expiração, histórico | Customizar validadores do Django | 2h |
| 27 | Login brute-force protection com `django-axes` (já tem config exemplo) | Lockout após 5 tentativas | 1h |

**Resultado da Fase 2:** Sistema seguro com RBAC, audit trail, 2FA — pronto para clientes enterprise.

---

## 🎫 FASE 3 — Tickets de Classe Mundial (Semanas 5-8)

> **Meta:** Funcionalidades de ticket que os melhores helpdesks oferecem.

### 3.1 Modelo de Ticket Avançado

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 28 | Adicionar `tipo` ao Ticket — Incidente, Requisição, Problema, Mudança (ITIL) | CharField com choices | 1h |
| 29 | Adicionar `parent_ticket` (FK self) — Sub-tickets | Permite split de tickets | 1h |
| 30 | Adicionar `related_tickets` (M2M self) — Tickets vinculados | Associação bidirecional | 1h |
| 31 | Adicionar `merged_into` (FK self) — Merge de tickets | Redirect de tickets duplicados | 1h |
| 32 | Migrar `tags` de CharField CSV → ManyToManyField com model `Tag` | Busca e filtro eficientes | 3h |
| 33 | Implementar `CustomField` model — campos dinâmicos por tipo de ticket | Nome, tipo (text/number/date/select/checkbox), obrigatório, opções | 4h |
| 34 | Implementar `TicketCustomFieldValue` — valores dos campos customizados | FK Ticket + FK CustomField + valor genérico | 2h |
| 35 | Regras de transição de status com model `StatusTransition` | Define quais transições são válidas (ex: fechado não volta para aberto) | 3h |

### 3.2 Funcionalidades de Produtividade

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 36 | **Respostas Prontas (Macros)** — model `CannedResponse` com título, corpo, categoria, variáveis | Ex: `{{cliente_nome}}`, `{{ticket_numero}}` | 4h |
| 37 | **Templates de Ticket** — model `TicketTemplate` com pré-preenchimento | Tipo comum + campos pré-configurados | 3h |
| 38 | **Bulk Actions** — Seleção múltipla na lista + ações em massa | Fechar, reatribuir, mudar prioridade, adicionar tag | 4h |
| 39 | **Followers/Watchers** — M2M `watchers` no Ticket | Usuários que recebem notificações sem serem agente | 2h |
| 40 | **Time Tracking** — model `TimeEntry` (ticket, user, minutos, descrição, data) | Registro de horas por interação + relatório | 4h |
| 41 | **Merge de Tickets** — View + UI para mesclar tickets duplicados | Combina interações, mantém o mais antigo | 4h |
| 42 | **Collision Detection** — WebSocket avisa quando 2 agentes abrem o mesmo ticket | "João está vendo este ticket" | 3h |

### 3.3 SLA Avançado

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 43 | **SLA Pause** — Pausar contagem quando status = `aguardando_cliente` | Campo `sla_paused_at`, `sla_paused_duration` | 3h |
| 44 | **Feriados** — model `Holiday` com datas configuráveis | Integrar no cálculo de business hours | 2h |
| 45 | **SLA por Cliente/Contrato** — FK opcional `sla_override` no Contrato | Cliente premium pode ter SLA diferente | 2h |
| 46 | **Multi-tier Escalation** — Cadeia: Agente → Supervisor → Gerente → Diretor | model `EscalationChain` com níveis | 3h |

**Resultado da Fase 3:** Sistema de tickets ITIL-compliant com produtividade profissional.

---

## 🌐 FASE 4 — API REST & Portal do Cliente (Semanas 8-11)

> **Meta:** API completa para integrações + portal de autoatendimento.

### 4.1 API REST Completa

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 47 | **Autenticação JWT** — `djangorestframework-simplejwt` com access/refresh tokens | Login, refresh, blacklist | 3h |
| 48 | **ViewSets completos** — Ticket, Cliente, Interação, KB, SLA, Notificação | CRUD com filtros, paginação, ordering | 8h |
| 49 | **Filtros avançados** — `django-filter` com FilterSet por modelo | Filtro por status, prioridade, data, agente, categoria | 3h |
| 50 | **Throttling** — Rate limiting por tipo de autenticação | Anon: 100/dia, Auth: 1000/dia, Premium: 5000/dia | 1h |
| 51 | **Paginação padrão** — `PageNumberPagination` com page_size configurável | Default 20, max 100 | 30min |
| 52 | **Documentação Swagger** funcional — Ativar drf-yasg com schemas corretos | Endpoints documentados com exemplos | 3h |
| 53 | **Webhooks Outbound** — model `WebhookEndpoint` + envio assíncrono via Celery | Eventos: ticket_created, updated, resolved, etc. | 6h |
| 54 | **API Keys** — model `APIKey` com hash + permissões + rate limit próprio | Para integrações de terceiros | 4h |
| 55 | **CORS** — `django-cors-headers` com whitelist configurável | Para SPAs e apps mobile | 1h |
| 56 | **Versionamento** — URL-based: `/api/v1/`, `/api/v2/` | Namespace por versão | 2h |

### 4.2 Portal do Cliente Funcional

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 57 | **Vincular Cliente ↔ User** — OneToOneField + signal de sincronização | Permite autenticação do cliente | 3h |
| 58 | **Auto-registro de clientes** — Formulário público + confirmação por email | Criar conta + perfil Cliente automaticamente | 4h |
| 59 | **Dashboard do cliente** — Meus tickets, status, SLA visível, satisfação | Template dedicado com métricas pessoais | 4h |
| 60 | **Abertura de ticket pelo cliente** — Formulário simplificado com upload de anexo | Campos: título, descrição, categoria, anexo | 3h |
| 61 | **Acompanhamento em tempo real** — Timeline de interações públicas do ticket | WebSocket para updates ao vivo | 3h |
| 62 | **KB Pública** — Lista de artigos acessíveis sem login | Busca, categorias, votos de utilidade | 4h |
| 63 | **Pesquisa de Satisfação** — Formulário pós-resolução com 1-5 estrelas + comentário | Link no email de resolução + widget no portal | 3h |
| 64 | **Self-service** — Sugestão automática de artigos KB ao digitar título do ticket | AJAX com similarity matching | 3h |

**Resultado da Fase 4:** API robusta para integrações + portal completo de autoatendimento.

---

## 🤖 FASE 5 — IA & Automação Inteligente (Semanas 11-14)

> **Meta:** IA real com LLM, automação avançada, chatbot inteligente.

### 5.1 Integração LLM

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 65 | **Configuração OpenAI/Claude** — Settings com API key, modelo, temperatura | Suporte a múltiplos provedores (OpenAI, Anthropic, local) | 2h |
| 66 | **Chatbot com LLM** — Substituir regex por RAG (Retrieval Augmented Generation) | Busca KB → contexto → LLM → resposta | 8h |
| 67 | **Auto-categorização** — Classificar ticket por título/descrição usando LLM | Na criação, sugerir categoria/prioridade/tipo | 3h |
| 68 | **Resumo de conversas** — LLM resume interações longas em 2-3 frases | Botão "Resumir" no detalhe do ticket | 3h |
| 69 | **Sugestão de resposta** — LLM sugere resposta baseada em KB + histórico similar | "IA sugere:" ao lado do campo de resposta | 4h |
| 70 | **Detecção de duplicatas** — Embedding + similarity para encontrar tickets similares | Na criação, "Tickets similares encontrados:" | 4h |
| 71 | **Análise de sentimento real** — LLM analisa tom do cliente em tempo real | Badge no ticket: 😊 Positivo / 😐 Neutro / 😠 Negativo | 2h |
| 72 | **Auto-triage** — Pipeline completo: título → categoriza + prioriza + atribui + sugere KB | Fluxo zero-touch para tickets simples | 4h |

### 5.2 Automação Avançada

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 73 | **Scheduled triggers** — Cron-based rules (ex: fechar tickets resolvidos há 7 dias) | Celery beat + model `ScheduledRule` | 4h |
| 74 | **Editor visual de workflows** — Drag-and-drop para criar regras | Frontend com nodes + connections (usar jsPlumb ou similar) | 12h |
| 75 | **Webhook triggers** — Eventos externos disparam workflows | Endpoint `POST /api/v1/webhooks/trigger/` | 3h |
| 76 | **Dry-run de workflows** — Simular execução sem aplicar mudanças | Botão "Testar" com log simulado | 3h |
| 77 | **Rate limiting de workflows** — Max execuções por regra por hora | Prevenir loops infinitos | 2h |
| 78 | **SLA-based triggers** — Workflow ativado por warning/breach real do SLA monitor | Conectar `monitor_sla_violations` aos workflow events | 2h |

**Resultado da Fase 5:** Chatbot inteligente com LLM, auto-triage, automação sofisticada.

---

## 📊 FASE 6 — Analytics & Relatórios Enterprise (Semanas 14-16)

> **Meta:** Dashboards executivos, relatórios exportáveis, métricas em tempo real.

### 6.1 Relatórios Avançados

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 79 | **Exportação PDF** — Relatórios formatados com `reportlab` ou `weasyprint` | Template HTML → PDF com gráficos | 6h |
| 80 | **Exportação Excel** — Planilhas com `openpyxl` com formatação e gráficos | Múltiplas abas por seção do relatório | 4h |
| 81 | **Relatórios agendados** — Celery beat envia relatório por email (diário/semanal/mensal) | model `ScheduledReport` com cron + destinatários | 4h |
| 82 | **Report builder** — Interface para criar relatórios customizados | Selecionar campos, filtros, agrupamento, gráfico | 8h |
| 83 | **Comparação de períodos** — "Este mês vs. mês anterior" em todos os dashboards | Delta percentual + sparkline | 3h |
| 84 | **Dashboards compartilháveis** — URL pública com token para compartilhar dashboard | Útil para stakeholders sem conta | 3h |

### 6.2 Métricas em Tempo Real

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 85 | **Live dashboard** — WebSocket streaming de métricas-chave | Tickets abertos, fila, CSAT, SLA compliance em real-time | 4h |
| 86 | **Presença de agentes** — Status online/offline/ocupado em tempo real | Heartbeat WebSocket + lista no sidebar | 3h |
| 87 | **Wallboard mode** — Dashboard fullscreen para TV no escritório | Layout especial com auto-refresh | 3h |
| 88 | **KPI Alerts** — Notificação quando métricas cruzam thresholds | Ex: CSAT < 4.0, SLA compliance < 90%, fila > 50 | 3h |

**Resultado da Fase 6:** Business intelligence completo com relatórios profissionais.

---

## 📧 FASE 7 — Omnichannel & Integrações (Semanas 16-20)

> **Meta:** Todos os canais de comunicação + integrações com ferramentas populares.

### 7.1 Email Inbound

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 89 | **IMAP Polling** — Celery task que verifica caixa de email periodicamente | Conectar à caixa de suporte (support@empresa.com) | 6h |
| 90 | **Email → Ticket** — Parser que cria ticket a partir de email recebido | Assunto → título, corpo → descrição, remetente → cliente | 4h |
| 91 | **Reply → Interação** — Detectar reply a notificação e adicionar como interação | Parsing de headers In-Reply-To / References | 4h |
| 92 | **Email templates editáveis** — Admin pode customizar templates de notificação | Editor WYSIWYG com variáveis de template | 4h |

### 7.2 Unified Inbox

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 93 | **Inbox unificado** — Fila única com mensagens de todos os canais | Email + WhatsApp + Chat + Web em uma lista | 6h |
| 94 | **Responder pelo canal original** — Agente responde e mensagem vai pelo canal que originou | Se veio por WhatsApp, resposta vai por WhatsApp | 3h |
| 95 | **Canal indicator** — Badge visual mostrando origem de cada mensagem | 📧 Email · 💬 Chat · 📱 WhatsApp · 🌐 Web | 1h |

### 7.3 Integrações Externas

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 96 | **Microsoft Teams** — Bot para criar/atualizar tickets via Teams | Webhook + Adaptive Cards | 6h |
| 97 | **Telegram Bot** — Canal de atendimento via Telegram | Webhook + criação de tickets | 4h |
| 98 | **Jira integration** — Sincronizar tickets com issues do Jira | API REST bidirecional | 8h |
| 99 | **Zapier/Make** — Webhook triggers + actions para automação externa | Documentação de payloads | 4h |
| 100 | **SSO/SAML** — Single Sign-On com `django-allauth` ou `python-social-auth` | Google, Microsoft, SAML para enterprise | 6h |

**Resultado da Fase 7:** Verdadeiro omnichannel com integrações profissionais.

---

## 🧪 FASE 8 — Qualidade & Performance (Semanas 20-22)

> **Meta:** Testes, performance, observabilidade — pronto para produção.

### 8.1 Testes

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 101 | **Unit tests** — Modelos, services, utils (meta: 80% cobertura) | pytest + pytest-django + factory-boy | 12h |
| 102 | **Integration tests** — Views, APIs, webhooks | Testar fluxos completos E2E | 8h |
| 103 | **API tests** — Cada endpoint com auth, filtros, paginação, erros | DRF test framework | 6h |
| 104 | **Load tests** — Simular 1000+ tickets simultâneos | locust ou k6 | 4h |
| 105 | **CI/CD pipeline** — GitHub Actions com testes, lint, deploy | Roda em cada PR/push | 4h |

### 8.2 Performance

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 106 | **Query optimization** — `select_related`/`prefetch_related` em TODAS as views | Eliminar N+1 queries | 4h |
| 107 | **Caching strategy** — Cache de dashboards, relatórios, KB com invalidação inteligente | Django cache framework + Redis | 4h |
| 108 | **Database indexing** — Índices compostos para queries frequentes | Analisar logs de slow queries | 2h |
| 109 | **Async views** — Converter views pesadas para async (Django 5.x native) | Relatórios e dashboards | 4h |
| 110 | **CDN + static optimization** — Minificação CSS/JS, lazy loading de imagens | django-compressor já instalado | 2h |

### 8.3 Observabilidade

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 111 | **Structured logging** — JSON logs com contexto (user, request_id, ticket) | `python-json-logger` | 2h |
| 112 | **Health check endpoint** — `/api/health/` com status de DB, Redis, Celery | Para load balancers e monitoramento | 2h |
| 113 | **Sentry alertas** — Configurar alertas por severidade, atribuição automática | Já tem SDK instalado | 1h |
| 114 | **Métricas Prometheus** — Exportar métricas para monitoramento externo | `django-prometheus` | 3h |

**Resultado da Fase 8:** Software confiável, testado, performático e observável.

---

## ✨ FASE 9 — UX & Features Premium (Semanas 22-26)

> **Meta:** Polimento final que transforma em produto premium.

### 9.1 Interface

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 115 | **Tema escuro** funcional — Toggle light/dark com persistência | CSS variables + toggle no navbar | 6h |
| 116 | **Error pages** customizadas — 404, 500, 403 com design consistente | Templates bonitos com links úteis | 2h |
| 117 | **Onboarding wizard** — Tour guiado para novos usuários | Shepherd.js ou Intro.js | 4h |
| 118 | **Keyboard shortcuts** — Atalhos para ações frequentes | N: novo ticket, /: busca, Esc: fechar | 3h |
| 119 | **Drag-and-drop** — Reordenar tickets, upload de arquivos, mover entre colunas (Kanban) | Kanban board como view alternativa de tickets | 8h |
| 120 | **Acessibilidade (WCAG 2.1)** — ARIA labels, contrast ratios, screen reader support | Audit com axe-core + correções | 6h |

### 9.2 Features Premium

| # | Tarefa | Detalhes | Esforço |
|---|--------|---------|---------|
| 121 | **Multi-tenancy** — Separação por organização com `django-tenants` ou tenant_id FK | Cada empresa vê apenas seus dados | 12h |
| 122 | **i18n/l10n** — Internacionalização com Django i18n | Português + Inglês + Espanhol | 8h |
| 123 | **White-label** — Logo/cores/domínio customizáveis por tenant | Branding no portal do cliente | 4h |
| 124 | **Gamification** — Pontos, badges, leaderboard para agentes | Motivação da equipe | 6h |
| 125 | **Customer health score** — Score calculado por frequência de tickets, CSAT, tempo de resolução | Identifica clientes em risco | 4h |

**Resultado da Fase 9:** Produto premium com UX polida e features de mercado.

---

## 📅 Timeline Visual

```
Semana  1-3   ███████  FASE 1: Fundação (código quebrado + unificação)
Semana  3-5   █████    FASE 2: Segurança (RBAC + Audit + 2FA)
Semana  5-8   ████████ FASE 3: Tickets Avançados (ITIL + macros + SLA)
Semana  8-11  ████████ FASE 4: API REST + Portal Cliente
Semana 11-14  ████████ FASE 5: IA + LLM + Automação
Semana 14-16  █████    FASE 6: Analytics + Relatórios
Semana 16-20  ████████ FASE 7: Omnichannel + Integrações
Semana 20-22  █████    FASE 8: Testes + Performance
Semana 22-26  ████████ FASE 9: UX Premium + Multi-tenancy
```

---

## 🎯 Quick Wins (Impacto Alto, Esforço Baixo)

Estas tarefas podem ser feitas a qualquer momento com retorno imediato:

| # | Quick Win | Esforço | Impacto |
|---|-----------|---------|---------|
| QW1 | Adicionar campo `tipo` ao InteracaoTicket | 1h | Corrige workflows quebrados |
| QW2 | Respostas Prontas (Macros) | 4h | Produtividade imediata dos agentes |
| QW3 | Bulk actions na lista de tickets | 4h | Gestão em escala |
| QW4 | Remover arquivos `.bak` | 15min | Projeto limpo |
| QW5 | Celery ALWAYS_EAGER em dev | 15min | Dev environment funcional |
| QW6 | Error pages 404/500 | 2h | Profissionalismo |
| QW7 | Keyboard shortcuts | 3h | Power users felizes |
| QW8 | Pesquisa de satisfação pós-resolução | 3h | Feedback do cliente |
| QW9 | SLA pause quando aguardando cliente | 3h | SLA justo |
| QW10 | CORS headers | 1h | Desbloqueia integrações frontend |

---

## 📦 Pacotes Necessários (Adicionar ao requirements.txt)

```
# Fase 2 — Segurança
django-otp==1.3.0              # 2FA/TOTP
django-axes==6.1.1             # Brute-force protection
qrcode==7.4.2                  # QR codes para 2FA

# Fase 4 — API
djangorestframework-simplejwt==5.3.1   # JWT authentication
django-filter==23.5            # API filtering
django-cors-headers==4.3.1     # CORS for API

# Fase 6 — Relatórios
weasyprint==61.2               # HTML → PDF
openpyxl==3.1.2                # Excel export

# Fase 7 — Integrações
django-allauth==0.59.0         # SSO/Social auth

# Fase 8 — Qualidade
pytest==7.4.3                  # Tests
pytest-django==4.7.0           # Django test integration
pytest-cov==4.1.0              # Coverage
factory-boy==3.3.0             # Test factories
locust==2.20.0                 # Load testing
django-prometheus==2.3.1       # Metrics
python-json-logger==2.0.7      # Structured logs

# Fase 9 — Premium
psycopg2-binary==2.9.9         # PostgreSQL (já deveria estar!)
```

---

## 🏆 Benchmark vs. Concorrentes

| Feature | Zendesk | Freshdesk | Jira SM | iConnect Hoje | iConnect Pós-Roadmap |
|---------|---------|-----------|---------|---------------|---------------------|
| Ticket CRUD | ✅ | ✅ | ✅ | ✅ | ✅ |
| ITIL Types | ✅ | ⚠️ | ✅ | ❌ | ✅ |
| Custom Fields | ✅ | ✅ | ✅ | ❌ | ✅ |
| SLA Management | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| Macros/Canned | ✅ | ✅ | ⚠️ | ❌ | ✅ |
| RBAC | ✅ | ✅ | ✅ | ❌ | ✅ |
| 2FA | ✅ | ✅ | ✅ | ❌ | ✅ |
| API REST | ✅ | ✅ | ✅ | ❌ | ✅ |
| Webhooks | ✅ | ✅ | ✅ | ❌ | ✅ |
| Email Inbound | ✅ | ✅ | ✅ | ❌ | ✅ |
| Chat Real-time | ✅ | ✅ | ⚠️ | ✅ | ✅ |
| WhatsApp | 💰 | 💰 | ❌ | ✅ | ✅ |
| AI/LLM Chatbot | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| Knowledge Base | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| Customer Portal | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| Reports/Export | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| SSO/SAML | ✅ | ✅ | ✅ | ❌ | ✅ |
| Multi-tenancy | ✅ | ✅ | ✅ | ❌ | ✅ |
| Mobile/PWA | ✅ | ✅ | ✅ | ✅ | ✅ |
| Financeiro | ❌ | ❌ | ❌ | ✅ | ✅ |
| Estoque | ❌ | ❌ | ❌ | ✅ | ✅ |

> **Diferencial competitivo do iConnect:** Módulos de Financeiro e Estoque integrados que nenhum concorrente oferece nativamente.

---

## 🚀 Por Onde Começar?

**Recomendação:** Fase 1 → Fase 2 → Fase 3, nesta ordem. Corrigir a fundação antes de construir features novas.

A Fase 1 é a mais urgente — código quebrado em produção prejudica a credibilidade do produto.
