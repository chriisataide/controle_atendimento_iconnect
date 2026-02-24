# 🎯 Sistema de Controle de Atendimento iConnect

[![Django](https://img.shields.io/badge/Django-5.2.6-green.svg)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/chriisataide/controle_atendimento_iconnect/actions/workflows/ci.yml/badge.svg)](https://github.com/chriisataide/controle_atendimento_iconnect/actions)

![Sistema de Tickets](https://img.shields.io/badge/Sistema-Tickets-success.svg)
![Dashboard](https://img.shields.io/badge/Dashboard-Agente-orange.svg)
![Portal](https://img.shields.io/badge/Portal-Cliente-blue.svg)
![SLA](https://img.shields.io/badge/SLA-Monitoring-red.svg)
![WhatsApp](https://img.shields.io/badge/WhatsApp-Integrado-brightgreen.svg)

Um sistema completo de gestão de atendimento e tickets desenvolvido em **Django** com interface moderna baseada em **Material Design**. O sistema oferece funcionalidades avançadas para controle de chamados, gestão de agentes, portal do cliente, SLA, chat em tempo real, chatbot IA e integrações com WhatsApp.

## 🏗️ Arquitetura

```
┌─────────────┐    ┌──────────┐    ┌────────────────┐
│   Nginx     │───▶│ Daphne   │───▶│  Django ASGI   │
│  (Reverse   │    │ (ASGI)   │    │  + Channels    │
│   Proxy)    │    └──────────┘    └───────┬────────┘
└─────────────┘                            │
                                ┌──────────┼──────────┐
                                │          │          │
                          ┌─────▼──┐  ┌────▼───┐ ┌───▼────┐
                          │Postgres│  │ Redis  │ │ Celery │
                          │  15    │  │  7     │ │Workers │
                          └────────┘  └────────┘ │+ Beat  │
                                                 └────────┘
```

- **Backend**: Django 5.2.6 + Django REST Framework + Channels (WebSocket)
- **ASGI Server**: Daphne (HTTP + WebSocket)
- **Banco de Dados**: PostgreSQL 15 (produção) / SQLite (desenvolvimento)
- **Cache & Mensageria**: Redis 7 (cache, sessions, Celery broker, channel layers)
- **Tarefas Assíncronas**: Celery + Celery Beat (agendamento periódico)
- **Monitoramento Celery**: Flower (protegido por autenticação)
- **Reverse Proxy**: Nginx com SSL
- **Frontend**: Material Dashboard 3.2.0, Bootstrap 5, JavaScript
- **CI/CD**: GitHub Actions (lint, test, security scan, Docker build, deploy)

## ✨ Funcionalidades

### 🎫 Sistema de Tickets ITIL
- Tipos: Incidente, Requisição, Problema, Mudança
- Hierarquia: Tickets pai/filho, merge e vinculação
- Watchers/Followers
- Kanban Board interativo
- Anexos com validação de segurança (magic bytes)
- Exportação para Excel/CSV/PDF

### ⏱️ SLA (Service Level Agreement)
- Políticas de SLA por categoria e prioridade
- Monitoramento automático com alertas
- Escalação multinível
- Dashboard de compliance
- Violações rastreadas com webhooks

### 💬 Chat em Tempo Real
- WebSocket via Django Channels
- Salas de chat vinculadas a tickets
- Criação de ticket a partir do chat
- Histórico persistente

### 🤖 Chatbot IA
- Motor de IA com análise de sentimentos
- Base de conhecimento configurável
- Predição de prioridade automática
- Detecção de tickets duplicados

### 📱 WhatsApp Business
- Integração via API oficial
- Recebimento e envio de mensagens
- Criação automática de tickets
- Webhooks configuráveis

### 📊 Dashboard Executivo
- KPIs em tempo real
- Gráficos analíticos
- Alertas de métricas configuráveis
- Relatórios agendados (email automático)

### 🔐 Segurança
- CSP com nonces criptográficos por request
- Headers de segurança (HSTS, X-Frame-Options, etc.)
- Rate limiting por IP/usuário
- Upload validation com magic bytes
- Django Axes (proteção brute-force)
- Criptografia de PII em repouso (LGPD/BACEN)
- JWT com rotation de tokens
- RBAC (Role-Based Access Control)
- Audit trail completo

### 🛡️ LGPD
- Gestão de consentimentos com expiração
- Solicitações de direitos do titular (Art. 18)
- Log de acesso a dados pessoais
- Retenção automática de dados (Celery Beat)
- Criptografia de CPF, telefone, dados sensíveis

### 🏢 Multi-tenancy
- Isolamento de dados por organização
- Convites e gestão de membros
- Switch entre tenants

### 🎮 Gamificação
- Leaderboard de agentes
- Métricas de performance
- Atualização automática

### 📦 Módulos Adicionais
- **Equipamentos**: Gestão de inventário com alertas de garantia
- **Estoque**: Controle de produtos e serviços
- **Financeiro**: Itens de atendimento com valores
- **PWA**: Progressive Web App com push notifications
- **Mobile**: Interface otimizada para dispositivos móveis
- **SSO**: SAML/OIDC para Single Sign-On

## 🚀 Quick Start

### Pré-requisitos
- Python 3.13+
- Docker & Docker Compose (recomendado)
- Git

### Opção 1: Docker Compose (Recomendado)

```bash
# Clonar o repositório
git clone https://github.com/chriisataide/controle_atendimento_iconnect.git
cd controle_atendimento_iconnect

# Configurar variáveis de ambiente
cp .env.example .env
# Edite o .env com suas credenciais (SECRET_KEY, POSTGRES_PASSWORD, etc.)

# Subir todos os serviços
docker compose up -d

# Verificar status
docker compose ps
```

Serviços disponíveis:
| Serviço | Porta | Descrição |
|---------|-------|-----------|
| **nginx** | 80/443 | Reverse proxy com SSL |
| **web** | 8000 | Django ASGI (Daphne) |
| **db** | — | PostgreSQL 15 (rede interna) |
| **redis** | — | Redis 7 (rede interna) |
| **celery** | — | Worker de tarefas assíncronas |
| **celery-beat** | — | Agendador de tarefas periódicas |
| **flower** | 5555 | Monitor Celery (autenticado) |

### Opção 2: Desenvolvimento Local

```bash
# Criar e ativar ambiente virtual
python -m venv .venv
source .venv/bin/activate  # macOS/Linux

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis
cp .env.example .env
# Edite o .env (mínimo: SECRET_KEY)

# Aplicar migrações
python manage.py migrate

# Criar superusuário
python manage.py createsuperuser

# Executar
python manage.py runserver
```

## 📋 Variáveis de Ambiente

Consulte o arquivo `.env.example` para a lista completa. Principais:

| Variável | Obrigatória | Descrição |
|----------|:-----------:|-----------|
| `SECRET_KEY` | ✅ | Chave secreta Django |
| `POSTGRES_PASSWORD` | ✅ (Docker) | Senha do PostgreSQL |
| `REDIS_PASSWORD` | ✅ (Docker) | Senha do Redis |
| `ALLOWED_HOSTS` | ✅ (Prod) | Hosts permitidos |
| `CELERY_BROKER_URL` | — | URL do broker Redis |
| `OPENAI_API_KEY` | — | Chave para chatbot IA |
| `WHATSAPP_TOKEN` | — | Token WhatsApp Business |

## 🧪 Testes

```bash
# Testes com cobertura
coverage run --source=dashboard manage.py test dashboard.tests -v2
coverage report --fail-under=60

# Ou com pytest
pytest -v

# Módulos de teste disponíveis:
# dashboard/tests/test_models.py       — Models
# dashboard/tests/test_api.py          — API REST
# dashboard/tests/test_services.py     — Serviços
# dashboard/tests/test_views.py        — Views
# dashboard/tests/test_sso.py          — SSO
# dashboard/tests/test_workflows.py    — Workflows
# dashboard/tests/test_tenants.py      — Multi-tenancy
# dashboard/tests_legacy.py            — Testes legados (em migração)
```

## 📚 Estrutura do Projeto

```
controle_atendimento_iconnect/
├── controle_atendimento/       # Configurações Django (settings, urls, celery, asgi)
├── dashboard/                  # App principal
│   ├── models*.py             # Models (tickets, chat, LGPD, equipamentos, etc.)
│   ├── views.py               # Views de template
│   ├── api_views.py           # API REST (v1)
│   ├── serializers.py         # Serializers DRF
│   ├── consumers.py           # WebSocket consumers
│   ├── tasks.py               # Celery tasks
│   ├── security.py            # Rate limiting, upload validation, CSP
│   ├── sla.py                 # Motor de SLA
│   ├── rbac.py                # Sistema de permissões
│   ├── tenants.py             # Multi-tenancy
│   ├── sso.py                 # SAML/OIDC
│   ├── tests/                 # Testes organizados por módulo
│   └── services/              # Serviços de negócio
├── templates/                  # Templates HTML (Material Dashboard)
├── assets/                     # Arquivos estáticos (CSS, JS, imagens)
├── docker/                     # Entrypoints e configs Docker
├── .github/workflows/          # CI/CD (GitHub Actions)
├── docker-compose.yml          # Orquestração de containers
├── Dockerfile                  # Build multi-stage
└── requirements.txt            # Dependências Python
```

## 🔧 Tarefas Periódicas (Celery Beat)

| Task | Frequência | Descrição |
|------|-----------|-----------|
| `monitor_sla_breaches` | 5 min | Verificar violações de SLA |
| `execute_scheduled_rules` | 5 min | Executar regras de automação |
| `check_inbound_emails` | 5 min | Processar emails recebidos |
| `check_kpi_alerts` | 15 min | Verificar alertas de KPI |
| `send_scheduled_reports` | 1 hora | Enviar relatórios agendados |
| `check_equipment_alerts` | 1 hora | Alertas de equipamentos |
| `update_agent_leaderboard` | 1 hora | Atualizar ranking de agentes |
| `recalculate_customer_health` | 6 horas | Health score dos clientes |
| `lgpd_data_retention` | 24 horas | Retenção de dados LGPD |

## 🔐 Sistema de Permissões

| Tipo | Acesso |
|------|--------|
| **Administrador** | Acesso total, configurações, tenants |
| **Supervisor** | Gestão de equipe, SLA, relatórios |
| **Agente** | Tickets atribuídos, chat, base de conhecimento |
| **Cliente** | Portal próprio, tickets, acompanhamento |

## 🤝 Contribuição

1. Fork o projeto
2. Crie sua feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 📞 Suporte

- 🐛 Issues: [GitHub Issues](https://github.com/chriisataide/controle_atendimento_iconnect/issues)
- 📖 Documentação: [Wiki do Projeto](https://github.com/chriisataide/controle_atendimento_iconnect/wiki)

---

**🌟 Desenvolvido com ❤️ usando Django — iCodev Tecnologia e Inovação**
