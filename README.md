# 🎯 Sistema de Controle de Atendimento iConnect

[![Django](https://img.shields.io/badge/Django-5.2.6-green.svg)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

![Sistema de Tickets](https://img.shields.io/badge/Sistema-Tickets-success.svg)
![Dashboard](https://img.shields.io/badge/Dashboard-Agente-orange.svg)
![Portal](https://img.shields.io/badge/Portal-Cliente-blue.svg)

Um sistema completo de gestão de atendimento e tickets desenvolvido em **Django** com interface moderna baseada em **Material Design**. O sistema oferece funcionalidades avançadas para controle de chamados, gestão de agentes e portal do cliente.

## ✨ Principais Funcionalidades

### 🎫 **Sistema de Tickets Completo**
- **Lista de Tickets**: Visualização com filtros avançados (status, categoria, prioridade, busca)
- **Detalhes do Ticket**: Interface completa com histórico de interações
- **Criação/Edição**: Formulários intuitivos para gestão de chamados
- **Sistema de Chat**: Interações públicas e privadas nos tickets
- **Status Dinâmicos**: Controle completo do fluxo de atendimento

### 👨‍💼 **Dashboard do Agente**
- **Painel Personalizado**: Métricas específicas do agente
- **Status em Tempo Real**: Online, Ocupado, Ausente, Offline
- **Tickets Atribuídos**: Gestão completa dos tickets do agente
- **Ações Rápidas**: Atualizações de status via AJAX
- **Distribuição Automática**: Sistema inteligente de atribuição

### 👤 **Portal do Cliente**
- **Interface Dedicada**: Área específica para clientes
- **Meus Tickets**: Visualização apenas dos próprios tickets
- **Estatísticas Pessoais**: Métricas individuais de atendimento
- **Histórico Completo**: Acompanhamento de todos os chamados

### 🎨 **Interface Moderna**
- **Material Dashboard 3.2.0**: Design profissional e responsivo
- **Navegação Intuitiva**: Menu organizado por seções
- **Componentes Avançados**: Filtros, paginação, modais, badges
- **Tema Escuro/Claro**: Suporte a múltiplos temas
- **Mobile First**: Interface adaptável para dispositivos móveis

## 🚀 Tecnologias Utilizadas

- **Backend**: Django 5.2.6, Python 3.13+
- **Frontend**: Material Dashboard 3.2.0, Bootstrap 5, JavaScript
- **Banco de Dados**: SQLite (desenvolvimento) / PostgreSQL (produção)
- **Estilização**: Material Design, CSS3, SCSS
- **Autenticação**: Django Auth System
- **Upload de Arquivos**: Pillow para processamento de imagens

## 📋 Modelos de Dados

### 🧑‍💼 **Perfis de Usuário**
- **PerfilUsuario**: Informações estendidas dos usuários
- **PerfilAgente**: Configurações específicas de agentes
- **Cliente**: Dados dos clientes do sistema

### 🎟️ **Sistema de Tickets**
- **Ticket**: Chamados com status, prioridade e categoria
- **CategoriaTicket**: Organização por tipo de atendimento
- **InteracaoTicket**: Histórico de conversas e atualizações
- **StatusTicket**: Controle de fluxo (Aberto, Em Andamento, Resolvido, Fechado)

## 🌐 Páginas e Funcionalidades

### **🏠 Dashboard Principal**
- Visão geral do sistema
- Métricas gerais de tickets
- Gráficos e estatísticas
- Timeline de atividades recentes

### **🎫 Gestão de Tickets**
- Lista completa com filtros avançados
- Criação de novos tickets
- Detalhes com sistema de chat
- Edição e atualização de status

### **👨‍💼 Área do Agente**
- Dashboard personalizado
- Tickets atribuídos
- Controle de status de presença
- Métricas de performance

### **👤 Portal do Cliente**
- Interface simplificada
- Visualização de tickets próprios
- Criação de novos chamados
- Acompanhamento de status

### **⚙️ Perfil e Configurações**
- Gerenciamento de perfil completo
- Upload de avatar
- Informações pessoais e profissionais
- Configurações de conta

## 🛠️ Instalação e Configuração

### **Pré-requisitos**
- Python 3.13+
- Node.js 16+ (opcional, para desenvolvimento frontend)
- Git

### **1. Clone o Repositório**
```bash
git clone https://github.com/chriisataide/controle_atendimento_iconnect.git
cd controle_atendimento_iconnect
```

### **2. Configurar Ambiente Python**
```bash
# Criar ambiente virtual
python -m venv .venv

# Ativar ambiente virtual
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

### **3. Configurar Banco de Dados**
```bash
# Aplicar migrações
python manage.py migrate

# Criar superusuário
python manage.py createsuperuser

# Criar dados de exemplo (opcional)
python manage.py criar_dados_exemplo
```

### **4. Executar o Servidor**
```bash
python manage.py runserver
```

Acesse: `http://127.0.0.1:8000/`

## 📚 Estrutura do Projeto

```
controle_atendimento_iconnect/
├── controle_atendimento/          # Configurações principais do Django
├── dashboard/                     # App principal do sistema
│   ├── models.py                 # Modelos de dados
│   ├── views.py                  # Views e lógica de negócio
│   ├── admin.py                  # Interface administrativa
│   └── management/commands/      # Comandos personalizados
├── templates/                     # Templates HTML
│   ├── base.html                 # Template base
│   └── dashboard/                # Templates específicos
│       ├── tickets/              # Templates de tickets
│       ├── agente/               # Templates do agente
│       └── cliente/              # Templates do cliente
├── assets/                        # Arquivos estáticos (Material Dashboard)
├── media/                         # Uploads de usuários
└── requirements.txt               # Dependências Python
```

## 🔧 Principais URLs do Sistema

| Função | URL | Descrição |
|--------|-----|-----------|
| **Dashboard Principal** | `/` | Visão geral do sistema |
| **Lista de Tickets** | `/tickets/` | Gerenciamento completo de tickets |
| **Criar Ticket** | `/tickets/novo/` | Formulário de criação |
| **Detalhes do Ticket** | `/tickets/<id>/` | Visualização e interações |
| **Dashboard Agente** | `/agente/` | Painel do agente |
| **Meus Tickets (Agente)** | `/agente/tickets/` | Tickets atribuídos |
| **Portal Cliente** | `/cliente/` | Área do cliente |
| **Meus Tickets (Cliente)** | `/cliente/tickets/` | Tickets do cliente |
| **Perfil** | `/profile/` | Configurações de perfil |
| **Admin** | `/admin/` | Interface administrativa |

## 🎨 Customização de Interface

### **Temas e Cores**
O sistema utiliza o Material Dashboard com suporte a:
- **Cores Primárias**: Blue, Green, Orange, Red, Purple
- **Modo Escuro**: Suporte completo a tema dark
- **Responsividade**: Mobile-first design
- **Componentes**: Material Design components

### **Personalização de Estilos**
```scss
// Localização: assets/scss/material-dashboard.scss
// Personalize cores, fontes e componentes
```

## 🔐 Sistema de Permissões

### **Tipos de Usuário**
1. **Administrador**: Acesso completo ao sistema
2. **Agente**: Gestão de tickets atribuídos
3. **Cliente**: Visualização dos próprios tickets
4. **Usuário**: Acesso básico ao sistema

### **Controle de Acesso**
- Autenticação obrigatória em todas as páginas
- Decorators `@login_required` para views
- Permissões baseadas em grupos do Django
- Middleware personalizado para controle de acesso

## 📊 API e Integrações

### **APIs AJAX Disponíveis**
- **Atualizar Status do Ticket**: `POST /api/tickets/status/`
- **Atualizar Status do Agente**: `POST /api/agente/status/`
- **Adicionar Interação**: `POST /tickets/<id>/interacao/`

### **Exemplo de Uso da API**
```javascript
// Atualizar status do ticket via JavaScript
fetch('/api/tickets/status/', {
    method: 'POST',
    headers: {
        'X-CSRFToken': csrfToken,
        'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: `ticket_id=${ticketId}&status=${newStatus}`
})
```

## 🚀 Deploy em Produção

### **Configurações de Produção**
```python
# settings.py
DEBUG = False
ALLOWED_HOSTS = ['seu-dominio.com']

# Banco de dados PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'controle_atendimento',
        'USER': 'postgres',
        'PASSWORD': 'sua_senha',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### **Deploy com Docker (Opcional)**
```dockerfile
# Dockerfile
FROM python:3.13
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

## 🧪 Testes

### **Executar Testes**
```bash
python manage.py test
```

### **Cobertura de Testes**
```bash
pip install coverage
coverage run --source='.' manage.py test
coverage report
coverage html
```

## 📈 Métricas e Monitoramento

### **Logs do Sistema**
- Logs automáticos de interações
- Rastreamento de mudanças de status
- Auditoria de ações dos usuários

### **Métricas Disponíveis**
- Total de tickets por período
- Tempo médio de resolução
- Performance dos agentes
- Satisfação dos clientes

## 🤝 Contribuição

1. Fork o projeto
2. Crie sua feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 👥 Créditos

- **Django Framework**: [Django Project](https://www.djangoproject.com/)
- **Bootstrap**: [Bootstrap Team](https://getbootstrap.com/)
- **Material Icons**: [Google Material Design](https://material.io/icons/)

## 📞 Suporte

Para suporte e dúvidas:
- 📧 Email: chrisataide@example.com
- 🐛 Issues: [GitHub Issues](https://github.com/chriisataide/controle_atendimento_iconnect/issues)
- 📖 Documentação: [Wiki do Projeto](https://github.com/chriisataide/controle_atendimento_iconnect/wiki)

---

## 🎯 Roadmap Futuro

- [ ] **Sistema de Relatórios Avançados**
- [ ] **Notificações em Tempo Real**
- [ ] **API REST Completa**
- [ ] **Integração com WhatsApp/Telegram**
- [ ] **Sistema de SLA e Métricas**
- [ ] **Dashboard Executivo**
- [ ] **Módulo de Conhecimento (KB)**
- [ ] **Chatbot Inteligente**

**🌟 Desenvolvido com ❤️ usando Django**
