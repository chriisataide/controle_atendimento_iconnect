
# Sistema de Controle de Atendimento iConnect - Changelog

## [2.0.0] — Enterprise Edition (2026-02-22)

### Fase 1: Foundation
- Unificação de InteracaoTicket (canal, tipo nota_interna/sistema/status_change)
- Serviço de busca unificado (search_service.py)
- Relatórios refatorados (reports_service.py)
- Modelos de auditoria (AuditEvent, SecurityAlert, ComplianceReport, DataAccessLog)
- Unificação SLA (models_sla deprecated, managed=False)
- KnowledgeBase aprimorado (CategoriaConhecimento, campos novos)

### Fase 2: Segurança & RBAC
- RBAC completo (rbac.py: UserRole, @role_required, RoleRequiredMixin)
- 4 roles: admin, supervisor, agente, cliente
- Signals de auditoria (login/logout/login_failed + ticket audit)
- SecurityHeadersMiddleware, AuditMiddleware
- django-axes: 5 tentativas → 30min lockout
- Comando setup_rbac para provisionamento

### Fase 3: Tickets Avançados
- Ticket ITIL: tipo (incidente/requisicao/problema/mudanca)
- Tickets pai/filho, relacionados, merge
- Watchers (M2M)
- CannedResponse (macros), TicketTemplate, CustomField, StatusTransition

### Fase 4: API REST Completa
- JWT (SimpleJWT 1h access / 7d refresh) + Token + Session auth
- CRUD tickets, clientes, respostas prontas
- Bulk actions (close, change_status, change_priority, assign)
- Time entries (registro de tempo)
- Webhooks CRUD + delivery com HMAC-SHA256 + retry
- API Keys (hash + prefix + permissions + rate limit)
- Export Excel (openpyxl)
- Analytics (overview, time-series, satisfaction, SLA, agent performance, period comparison)
- CORS, throttling (100/day anon, 1000/day user), pagination
- Health check endpoint

### Fase 5: IA / LLM
- AIConfiguration model (OpenAI, Anthropic, Google, local)
- AIInteraction model (log de chamadas com tokens/tempo)
- AIService: auto_categorize, predict_priority, suggest_response, summarize_conversation, analyze_sentiment, find_duplicates, auto_triage
- Heurísticas inteligentes como fallback sem LLM
- ScheduledRule (automação cron com condições/ações JSON)
- Endpoints API: /ai-triage/, /ai-suggest-response/, /ai-summarize/, /sentiment/, /find-duplicates/

### Fase 6: Analytics BI
- ScheduledReport (daily/weekly/monthly, PDF/Excel/CSV, emails)
- SharedDashboard (token público, expiração, view_count)
- KPIAlert (thresholds + cooldown + email)
- Analytics comparação de períodos
- Agent performance metrics

### Fase 7: Omnichannel
- EmailAccount (IMAP/POP3), InboundEmail, EmailTemplate
- EmailInboundService: polling IMAP, parse email, criação/reply de tickets
- Detecção de reply por [TK-XXXXX] no subject ou In-Reply-To header
- Celery task: check_inbound_emails

### Fase 8: Testes
- 41 testes automatizados cobrindo:
  - Models: Cliente, Ticket, CannedResponse, APIKey, Tag, TimeEntry, Webhook, SharedDashboard
  - API: Health, JWT (obtain/refresh/invalid), Tickets CRUD, Clientes, Bulk actions, Analytics, CannedResponses, Export
  - Services: AIService (priority/sentiment/duplicates), WebhookService, GamificationService, CustomerHealthService
  - RBAC: Roles admin/agente, permissões

### Fase 9: UX Premium
- Dark theme Slate+Cyan (CSS variables, transições suaves, localStorage)
- Keyboard shortcuts (Alt+D/T/N/P, /, Esc)
- Sidebar collapse
- Kanban Board (drag & drop, AJAX status update, filtros por agente/categoria)
- Error pages customizadas (404, 500, 403) com design Slate+Cyan/Red/Amber
- Gamification (badges, pontos, leaderboard)
- Customer Health Score (scoring ponderado)
- i18n pt-BR/en/es (LANGUAGES, LOCALE_PATHS, .po/.mo)

### Infraestrutura
- Celery tasks: deliver_webhook, check_inbound_emails, execute_scheduled_rules, send_scheduled_reports, recalculate_customer_health, update_agent_leaderboard, check_kpi_alerts, monitor_sla_breaches
- Migrations: 0020-0023
- Django 5.2.6, Python 3.12
- 21 novos models, 5 services, 8 Celery tasks, 30+ API endpoints

---

## [Unreleased]
### Adicionado
- Documentação automática das APIs (Swagger e Redoc) via drf-yasg em `/swagger/` e `/redoc/`.
- Exemplo de settings para integrações externas (Slack, WhatsApp, CRM, ERP, webhooks).
- Service worker e manifest para PWA offline.
- Testes automatizados para modelos principais.
- Pipeline CI/CD com lint, test, coverage e dependabot.
- Monitoramento Sentry, health check, métricas e logs estruturados.
- Segurança: 2FA admin, brute-force protection, atualização de dependências.
- Otimização: cache Redis, compressão, minificação de assets.

### Alterado
- Modularização dos settings para facilitar ativação de integrações e features.

### Corrigido
- Ajustes de responsividade e acessibilidade no template base.

---

## [1.0.0] 2025-09-08

### ✨ Funcionalidades Implementadas

**🎫 Sistema de Tickets Completo**
- ✅ Lista de tickets com filtros avançados
- ✅ Criação e edição de tickets
- ✅ Sistema de chat integrado
- ✅ Status dinâmicos de atendimento
- ✅ Histórico completo de interações

**👨‍💼 Dashboard do Agente**
- ✅ Painel personalizado por agente
- ✅ Status em tempo real (Online, Ocupado, Ausente, Offline)
- ✅ Gestão de tickets atribuídos
- ✅ Ações rápidas via AJAX
- ✅ Sistema de distribuição automática

**👤 Portal do Cliente**
- ✅ Interface dedicada para clientes
- ✅ Abertura de tickets self-service
- ✅ Acompanhamento de solicitações
- ✅ Histórico de atendimentos

**🔐 Sistema de Autenticação**
- ✅ Login/logout seguro
- ✅ Perfis diferenciados (Admin, Agente, Cliente)
- ✅ Controle de permissões
- ✅ Redirecionamento inteligente

**📊 Dashboard com Gráficos**
- ✅ Métricas em tempo real
- ✅ Gráficos coloridos e interativos
- ✅ Indicadores de performance
- ✅ Relatórios visuais

**🎨 Interface Moderna**
- ✅ Design baseado em Material Design
- ✅ Tema escuro/claro
- ✅ Animações suaves
- ✅ Responsivo para mobile

### 🔧 Configurações e Melhorias

**⚙️ Configuração Avançada**
- ✅ Dropdown de configurações interativo
- ✅ Atalhos de teclado personalizados
- ✅ Informações do sistema
- ✅ Persistência de preferências

**🎯 Sistema de Cores**
- ✅ Paleta Material Design integrada
- ✅ Gradientes dinâmicos nos gráficos
- ✅ Cores baseadas em dados
- ✅ Animações e transições elegantes

**🚀 Performance**
- ✅ Otimizações de CSS e JavaScript
- ✅ Carregamento assíncrono
- ✅ Cache inteligente
- ✅ Compressão de assets

## [Próximas Versões]

### 📋 Planejado para v1.1.0
- [ ] Sistema de notificações push
- [ ] Integração com WhatsApp/Telegram
- [ ] Relatórios PDF exportáveis
- [ ] API REST completa
- [ ] Sistema de SLA automático

### 🔮 Roadmap Futuro
- [ ] Chatbot com IA
- [ ] Integração com CRM
- [ ] Aplicativo móvel
- [ ] Multi-tenancy
- [ ] Analytics avançado

---

**Desenvolvido por:** Chris Ataíde  
**Tecnologias:** Django 5.2.6, Python 3.13+, Material Design  
**Licença:** MIT  
