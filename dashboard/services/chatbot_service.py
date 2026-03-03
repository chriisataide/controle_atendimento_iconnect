"""
Sistema de Chatbot Inteligente para iConnect
Implementa assistente virtual com IA para atendimento automatizado
"""

import json
import re
import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Q, Count, Avg, F
from asgiref.sync import sync_to_async

from ..models import Ticket, Notification, StatusTicket, PrioridadeTicket, Cliente
from .notifications import NotificationService

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Tipos de intenção do usuário"""
    GREETING = "greeting"
    HELP_REQUEST = "help_request"
    TICKET_STATUS = "ticket_status"
    CREATE_TICKET = "create_ticket"
    COMPLAINT = "complaint"
    BILLING_QUESTION = "billing_question"
    TECHNICAL_SUPPORT = "technical_support"
    ACCOUNT_INFO = "account_info"
    SCHEDULE_CALLBACK = "schedule_callback"
    ESCALATE = "escalate"
    GOODBYE = "goodbye"
    # Intents analíticas (dashboard)
    DASHBOARD_STATS = "dashboard_stats"
    DAILY_SUMMARY = "daily_summary"
    AGENT_PERFORMANCE = "agent_performance"
    CLIENT_ATTENTION = "client_attention"
    SYSTEM_GUIDE = "system_guide"
    UNKNOWN = "unknown"

@dataclass
class ChatbotResponse:
    """Estrutura de resposta do chatbot"""
    message: str
    intent: IntentType
    confidence: float
    actions: List[str] = None
    quick_replies: List[str] = None
    requires_human: bool = False
    context: Dict[str, Any] = None

class IntentClassifier:
    """Classificador de intenções usando regras e padrões"""
    
    def __init__(self):
        self.intent_patterns = {
            IntentType.GREETING: [
                r'\b(oi|olá|ola|hey|bom dia|boa tarde|boa noite|tudo bem)\b',
                r'\b(alo|alô|eai|e ai)\b'
            ],
            IntentType.HELP_REQUEST: [
                r'\b(ajuda|help|socorro|preciso|auxiliar|suporte)\b',
                r'\b(como fazer|como funciona|não consigo|duvida|dúvida)\b'
            ],
            IntentType.TICKET_STATUS: [
                r'\b(status|situação|andamento|protocolo)\b',
                r'\b(meu ticket|minha solicitação|meu chamado)\b',
                r'\b(número.*\d+|#\d+|tk\d+)\b'
            ],
            IntentType.CREATE_TICKET: [
                r'\b(abrir|criar|novo) (ticket|chamado|solicitação)\b',
                r'\b(reportar|relatar) (problema|bug|erro)\b'
            ],
            IntentType.COMPLAINT: [
                r'\b(reclamação|reclamar|insatisfeito|irritado)\b',
                r'\b(péssimo|ruim|horrível|problema sério)\b'
            ],
            IntentType.BILLING_QUESTION: [
                r'\b(cobrança|fatura|pagamento|valor|preço)\b',
                r'\b(conta|cartão|débito|crédito|boleto)\b'
            ],
            IntentType.TECHNICAL_SUPPORT: [
                r'\b(não funciona|bug|erro|falha|defeito)\b',
                r'\b(travou|lento|não carrega|não abre)\b'
            ],
            IntentType.ACCOUNT_INFO: [
                r'\b(minha conta|perfil|dados|informações pessoais)\b',
                r'\b(alterar|mudar|atualizar) (senha|email|telefone)\b'
            ],
            IntentType.SCHEDULE_CALLBACK: [
                r'\b(ligar|telefone|contato|callback)\b',
                r'\b(agendar|marcar) (ligação|contato)\b'
            ],
            IntentType.ESCALATE: [
                r'\b(falar com|gerente|supervisor|humano|pessoa)\b',
                r'\b(não resolve|não funciona|quero falar)\b'
            ],
            IntentType.GOODBYE: [
                r'\b(tchau|adeus|até logo|obrigado|valeu)\b',
                r'\b(fim|encerrar|sair)\b'
            ],
            # Intents analíticas para o dashboard
            IntentType.DASHBOARD_STATS: [
                r'\b(quantos|quantas|total|contagem)\b.*(ticket|chamado|aberto|pendente|resolvid)',
                r'\b(tickets?|chamados?)\s+(abertos?|pendentes?|hoje|ativos?)\b',
                r'\b(abertos?|pendentes?)\s+(hoje|agora|temos)\b',
                r'\b(quantos|quantas)\s+(tickets?|chamados?)\b',
            ],
            IntentType.DAILY_SUMMARY: [
                r'\b(resumo|resumir|overview|visão geral)\b',
                r'\b(resumo|relatório|report).*(dia|hoje|diário)\b',
                r'\b(dia|hoje|diário).*(resumo|relatório|report)\b',
                r'\b(como est[áa]|como vai|como anda).*(atendimento|dia|hoje)\b',
                r'\b(mostre|mostra|exib[ae]).*(resumo|dados|informações|números)\b',
            ],
            IntentType.AGENT_PERFORMANCE: [
                r'\b(tempo|média|performance|desempenho).*(resposta|agente|atendente)\b',
                r'\b(agente|atendente|equipe).*(tempo|performance|desempenho|produtividade)\b',
                r'\b(tempo médio|média de tempo)\b',
                r'\b(sla|nivel de serviço|nível de serviço)\b',
                r'\b(produtividade|eficiência)\b.*(agente|equipe|time)',
            ],
            IntentType.CLIENT_ATTENTION: [
                r'\b(clientes?|pacientes?).*(aten[çc][ãa]o|imediata|urgente|priorit|crític)\b',
                r'\b(aten[çc][ãa]o|urgente|priorit|crític).*(clientes?|pacientes?)\b',
                r'\b(quais|quem).*(precis|necessit).*(aten[çc][ãa]o|ajuda|suporte)\b',
                r'\b(clientes?|chamados?)\s+(urgentes?|críticos?|prioritários?)\b',
            ],
            # Guia de uso do sistema
            IntentType.SYSTEM_GUIDE: [
                r'\b(como|onde|aonde)\b.*(faço|faz|fazer|acessar|acessor|criar|editar|ver|listar|configurar|usar|mexer|navegar|abrir|encontrar|pesquisar|buscar|exportar|gerenciar|cadastrar|alterar|excluir|deletar)',
                r'\b(onde fica|como faço|como eu|como faz|me ensina|me mostra|me ajuda|me explica|me diz)\b',
                r'\b(tutorial|passo a passo|roteiro|instruções|instrucoes)\b',
                r'\b(quero|preciso|gostaria de?)\b.*(criar|editar|ver|listar|acessar|abrir|cadastrar|exportar|gerar|configurar)',
                r'\b(funcionalidade|função|módulo|seção|página|menu|tela)\b',
                r'\bpara que serve\b',
                r'\bcomo funciona\b',
                r'\bo que (o sistema|ele|isso) faz\b',
                r'\b(acessar?|ir para|entrar em|abrir)\b.*(tela|page|pagina|página|módulo|seção|menu)',
            ],
        }
    
    # Mapa completo de funcionalidades do sistema com roteiros passo a passo
    SYSTEM_GUIDES = {
        'dashboard': {
            'keywords': ['dashboard', 'painel', 'início', 'home', 'tela inicial', 'página inicial', 'visão geral'],
            'title': '📊 Dashboard Principal',
            'path': '/dashboard/',
            'guide': (
                '📊 **Dashboard Principal**\n\n'
                '**Como acessar o Dashboard:**\n\n'
                '1. Faça login no sistema\n'
                '2. Você será redirecionado automaticamente para o **Dashboard**\n'
                '3. Ou acesse pelo menu lateral clicando em **"Dashboard"**\n\n'
                '**O que você encontra no Dashboard:**\n'
                '• Resumo de tickets abertos, em andamento e resolvidos\n'
                '• Gráficos de desempenho\n'
                '• Alertas de SLA\n'
                '• Atividades recentes\n\n'
                '📍 Acesse em: /dashboard/'
            ),
        },
        'criar_ticket': {
            'keywords': ['criar ticket', 'novo ticket', 'abrir ticket', 'novo chamado', 'abrir chamado', 'criar chamado', 'registrar chamado', 'registrar ticket', 'tela de abertura de ticket', 'abertura de ticket'],
            'title': '📝 Criar Novo Ticket',
            'path': '/dashboard/tickets/novo/',
            'guide': (
                '📝 **Criar Novo Ticket**\n\n'
                '**Como criar um novo ticket:**\n\n'
                '1. No menu lateral, clique em **"Tickets"**\n'
                '2. Clique no botão **"+ Novo Ticket"** (canto superior direito)\n'
                '3. Preencha os campos obrigatórios:\n'
                '   • **Título** — Descreva brevemente o problema\n'
                '   • **Descrição** — Detalhe o que está acontecendo\n'
                '   • **Cliente** — Selecione o cliente\n'
                '   • **Prioridade** — Baixa, Média, Alta ou Urgente\n'
                '   • **Categoria** — Tipo do atendimento\n'
                '4. Clique em **"Salvar"**\n\n'
                '💡 Dica: Quanto mais detalhes na descrição, mais rápido será o atendimento!\n\n'
                '📍 Acesse em: /dashboard/tickets/novo/'
            ),
        },
        'listar_tickets': {
            'keywords': ['listar tickets', 'ver tickets', 'meus tickets', 'todos tickets', 'lista de tickets', 'lista de chamados', 'pesquisar ticket', 'buscar ticket', 'encontrar ticket'],
            'title': '📋 Listar e Pesquisar Tickets',
            'path': '/dashboard/tickets/',
            'guide': (
                '📋 **Listar e Pesquisar Tickets**\n\n'
                '**Como ver e pesquisar tickets:**\n\n'
                '1. No menu lateral, clique em **"Tickets"**\n'
                '2. Você verá a lista de todos os tickets\n'
                '3. Use os **filtros** no topo para refinar:\n'
                '   • Por status (Aberto, Em andamento, Resolvido, Fechado)\n'
                '   • Por prioridade\n'
                '   • Por agente responsável\n'
                '   • Por data\n'
                '4. Use a **barra de pesquisa** para buscar por título ou descrição\n'
                '5. Clique em um ticket para ver os detalhes\n\n'
                '📍 Acesse em: /dashboard/tickets/'
            ),
        },
        'kanban': {
            'keywords': ['kanban', 'quadro kanban', 'board', 'arrastar ticket', 'mover ticket', 'visualização kanban'],
            'title': '📌 Quadro Kanban',
            'path': '/dashboard/tickets/kanban/',
            'guide': (
                '📌 **Quadro Kanban**\n\n'
                '**Como usar o Quadro Kanban:**\n\n'
                '1. No menu lateral, clique em **"Tickets"** → **"Kanban"**\n'
                '2. Os tickets são organizados em colunas por status:\n'
                '   • **Aberto** → **Em Andamento** → **Aguardando** → **Resolvido**\n'
                '3. **Arraste e solte** os cards para mudar o status\n'
                '4. Clique em um card para ver detalhes completos\n\n'
                '💡 Dica: O Kanban é ideal para ter uma visão rápida do fluxo de trabalho!\n\n'
                '📍 Acesse em: /dashboard/tickets/kanban/'
            ),
        },
        'editar_ticket': {
            'keywords': ['editar ticket', 'alterar ticket', 'modificar ticket', 'atualizar ticket', 'mudar status', 'alterar chamado', 'editar chamado'],
            'title': '✏️ Editar Ticket',
            'path': '/dashboard/tickets/{id}/editar/',
            'guide': (
                '✏️ **Editar Ticket**\n\n'
                '**Como editar um ticket:**\n\n'
                '1. Acesse a lista de tickets (/dashboard/tickets/)\n'
                '2. Clique no ticket que deseja editar\n'
                '3. Na página de detalhes, clique em **"Editar"**\n'
                '4. Modifique os campos desejados:\n'
                '   • Status, prioridade, categoria\n'
                '   • Descrição, agente responsável\n'
                '5. Clique em **"Salvar"** para aplicar as alterações\n\n'
                '💡 Dica: Você também pode alterar o status rapidamente pelo Kanban!'
            ),
        },
        'clientes': {
            'keywords': ['cliente', 'clientes', 'cadastrar cliente', 'novo cliente', 'listar clientes', 'gestão de clientes', 'gerenciar clientes'],
            'title': '👥 Gestão de Clientes',
            'path': '/dashboard/clientes/',
            'guide': (
                '👥 **Gestão de Clientes**\n\n'
                '**Listar clientes:**\n'
                '1. No menu lateral, clique em **"Clientes"**\n'
                '2. Veja todos os clientes cadastrados\n\n'
                '**Cadastrar novo cliente:**\n'
                '1. Clique em **"+ Novo Cliente"**\n'
                '2. Preencha: Razão Social, CNPJ, e-mail, telefone\n'
                '3. Clique em **"Salvar"**\n\n'
                '**Editar cliente:**\n'
                '1. Clique no cliente na lista\n'
                '2. Clique em **"Editar"**\n'
                '3. Altere os dados e salve\n\n'
                '📍 Acesse em: /dashboard/clientes/'
            ),
        },
        'pontos_de_venda': {
            'keywords': ['ponto de venda', 'pontos de venda', 'pdv', 'unidade', 'filial', 'cadastrar pdv', 'uniorg'],
            'title': '🏪 Pontos de Venda',
            'path': '/dashboard/pontosdevenda/',
            'guide': (
                '🏪 **Pontos de Venda**\n\n'
                '**Como gerenciar pontos de venda:**\n\n'
                '1. No menu lateral, clique em **"Pontos de Venda"**\n'
                '2. Veja todas as unidades cadastradas\n\n'
                '**Cadastrar novo PDV:**\n'
                '1. Clique em **"+ Novo Ponto de Venda"**\n'
                '2. Preencha os dados:\n'
                '   • Razão Social, Nome Fantasia, CNPJ\n'
                '   • Endereço completo\n'
                '   • Dados do responsável\n'
                '   • Vincule a um **cliente** (empresa)\n'
                '3. Clique em **"Salvar"**\n\n'
                '📍 Acesse em: /dashboard/pontosdevenda/'
            ),
        },
        'usuarios': {
            'keywords': ['usuário', 'usuarios', 'criar usuário', 'novo usuário', 'editar usuário', 'gerenciar usuários', 'listar usuários', 'permissões', 'nível de acesso', 'role'],
            'title': '👤 Gestão de Usuários',
            'path': '/dashboard/users/',
            'guide': (
                '👤 **Gestão de Usuários**\n\n'
                '**Listar usuários:**\n'
                '1. No menu lateral, clique em **"Usuários"**\n\n'
                '**Criar novo usuário:**\n'
                '1. Clique em **"+ Novo Usuário"**\n'
                '2. Preencha: Usuário, E-mail, Senha\n'
                '3. Primeiro Nome e Sobrenome\n'
                '4. Selecione o **Nível de Acesso**:\n'
                '   • Administrador, Gerente, Supervisor\n'
                '   • Técnico Sênior, Agente, Financeiro\n'
                '   • Visualizador, Cliente\n'
                '5. Clique em **"Criar Usuário"**\n\n'
                '**Editar usuário:**\n'
                '1. Na lista, clique em **"Editar"** ao lado do usuário\n'
                '2. Altere dados, nível de acesso ou senha\n'
                '3. Clique em **"Salvar Alterações"**\n\n'
                '📍 Acesse em: /dashboard/users/'
            ),
        },
        'perfil': {
            'keywords': ['meu perfil', 'perfil', 'minha conta', 'alterar minha senha', 'trocar senha', 'meus dados', 'configurar perfil'],
            'title': '⚙️ Meu Perfil',
            'path': '/dashboard/profile/',
            'guide': (
                '⚙️ **Meu Perfil**\n\n'
                '**Como editar seu perfil:**\n\n'
                '1. Clique no seu **nome/avatar** no canto superior direito\n'
                '2. Selecione **"Perfil"**\n'
                '3. Edite suas informações pessoais\n'
                '4. Clique em **"Salvar"**\n\n'
                '📍 Acesse em: /dashboard/profile/'
            ),
        },
        'sla': {
            'keywords': ['sla', 'acordo de nível', 'tempo de resposta', 'tempo de resolução', 'prazo', 'políticas sla', 'alertas sla'],
            'title': '⏱️ Gestão de SLA',
            'path': '/dashboard/sla/',
            'guide': (
                '⏱️ **Gestão de SLA**\n\n'
                '**Dashboard SLA:**\n'
                '1. No menu lateral, clique em **"SLA"**\n'
                '2. Veja o painel com métricas de cumprimento\n\n'
                '**Criar política de SLA:**\n'
                '1. Acesse **"SLA"** → **"Políticas"**\n'
                '2. Defina tempos de resposta e resolução por prioridade\n\n'
                '**Alertas de SLA:**\n'
                '1. Acesse **"SLA"** → **"Alertas"**\n'
                '2. Veja tickets que estão próximos ou além do prazo\n\n'
                '📍 Acesse em: /dashboard/sla/'
            ),
        },
        'chat': {
            'keywords': ['chat', 'conversa', 'mensagem', 'conversar', 'chat interno', 'sala de chat'],
            'title': '💬 Chat Interno',
            'path': '/dashboard/chat/',
            'guide': (
                '💬 **Chat Interno**\n\n'
                '**Como usar o Chat:**\n\n'
                '1. No menu lateral, clique em **"Chat"**\n'
                '2. Veja suas salas de conversa ativas\n\n'
                '**Criar nova conversa:**\n'
                '1. Clique em **"Nova Conversa"**\n'
                '2. Selecione os participantes\n'
                '3. Comece a trocar mensagens em tempo real\n\n'
                '**Criar ticket a partir do chat:**\n'
                '1. Dentro de uma conversa, clique em **"Criar Ticket"**\n'
                '2. O histórico da conversa será vinculado ao ticket\n\n'
                '📍 Acesse em: /dashboard/chat/'
            ),
        },
        'relatorios': {
            'keywords': ['relatório', 'relatorios', 'exportar', 'gerar relatório', 'report', 'analytics', 'análise', 'estatísticas', 'métricas'],
            'title': '📈 Relatórios e Analytics',
            'path': '/dashboard/reports/',
            'guide': (
                '📈 **Relatórios e Analytics**\n\n'
                '**Como gerar relatórios:**\n\n'
                '1. No menu lateral, clique em **"Relatórios"**\n'
                '2. Escolha o tipo de relatório:\n'
                '   • Tickets por período\n'
                '   • Desempenho por agente\n'
                '   • SLA por cliente\n'
                '   • Itens de atendimento\n'
                '3. Selecione os **filtros** (data, status, agente)\n'
                '4. Clique em **"Gerar"**\n'
                '5. Exporte em **CSV** ou **PDF**\n\n'
                '📍 Acesse em: /dashboard/reports/'
            ),
        },
        'notificacoes': {
            'keywords': ['notificação', 'notificações', 'alerta', 'alertas', 'avisos', 'push'],
            'title': '🔔 Notificações',
            'path': '/dashboard/notifications/',
            'guide': (
                '🔔 **Notificações**\n\n'
                '**Como gerenciar notificações:**\n\n'
                '1. Clique no **ícone do sino** 🔔 no topo da página\n'
                '2. Veja notificações recentes\n'
                '3. Clique em **"Ver todas"** para a lista completa\n\n'
                '**Tipos de notificação:**\n'
                '• Novo ticket atribuído a você\n'
                '• Atualização de status de ticket\n'
                '• Alertas de SLA\n'
                '• Mensagens no chat\n\n'
                '📍 Acesse em: /dashboard/notifications/'
            ),
        },
        'automacao': {
            'keywords': ['automação', 'automatizar', 'regra', 'regras', 'workflow', 'fluxo', 'automático'],
            'title': '🤖 Automação e Workflows',
            'path': '/dashboard/automation/',
            'guide': (
                '🤖 **Automação e Workflows**\n\n'
                '**Regras de automação:**\n'
                '1. No menu, acesse **"Automação"** → **"Regras"**\n'
                '2. Crie regras como: "Se ticket urgente, atribuir ao supervisor"\n\n'
                '**Workflow Builder (Visual):**\n'
                '1. Acesse **"Automação"** → **"Workflows"**\n'
                '2. Use o editor visual para criar fluxos\n'
                '3. Arraste e conecte blocos de ação\n'
                '4. Ative o workflow quando pronto\n\n'
                '📍 Acesse em: /dashboard/automation/'
            ),
        },
        'whatsapp': {
            'keywords': ['whatsapp', 'wpp', 'zap', 'mensagem whatsapp', 'integração whatsapp'],
            'title': '📱 WhatsApp Business',
            'path': '/dashboard/whatsapp/',
            'guide': (
                '📱 **WhatsApp Business**\n\n'
                '**Como usar o WhatsApp Business:**\n\n'
                '1. No menu lateral, clique em **"WhatsApp"**\n'
                '2. Configure sua conta Business\n'
                '3. Gerencie contatos e conversas\n'
                '4. Configure respostas automáticas\n'
                '5. Envie e receba mensagens pelo sistema\n\n'
                '📍 Acesse em: /dashboard/whatsapp/'
            ),
        },
        'base_conhecimento': {
            'keywords': ['base de conhecimento', 'knowledge', 'artigo', 'artigos', 'documentação', 'faq', 'perguntas frequentes', 'manual'],
            'title': '📚 Base de Conhecimento',
            'path': '/dashboard/knowledge/',
            'guide': (
                '📚 **Base de Conhecimento**\n\n'
                '**Como usar a Base de Conhecimento:**\n\n'
                '1. No menu lateral, clique em **"Base de Conhecimento"**\n'
                '2. Pesquise artigos por palavra-chave\n'
                '3. Navegue por categorias\n'
                '4. Vote em artigos úteis (👍/👎)\n\n'
                '📍 Acesse em: /dashboard/knowledge/'
            ),
        },
        'macros': {
            'keywords': ['macro', 'macros', 'resposta rápida', 'respostas rápidas', 'template de resposta', 'modelo de resposta'],
            'title': '⚡ Respostas Rápidas (Macros)',
            'path': '/dashboard/macros/',
            'guide': (
                '⚡ **Respostas Rápidas (Macros)**\n\n'
                '**Como usar Respostas Rápidas:**\n\n'
                '1. No menu lateral, clique em **"Macros"**\n'
                '2. Veja as respostas prontas disponíveis\n\n'
                '**Criar nova macro:**\n'
                '1. Clique em **"+ Nova Macro"**\n'
                '2. Defina um título e o texto da resposta\n'
                '3. Salve para usar em tickets\n\n'
                '💡 Dica: Use macros nos tickets para responder mais rápido!\n\n'
                '📍 Acesse em: /dashboard/macros/'
            ),
        },
        'compliance': {
            'keywords': ['compliance', 'auditoria', 'lgpd', 'dados pessoais', 'privacidade', 'audit trail', 'trilha de auditoria'],
            'title': '🔒 Compliance e LGPD',
            'path': '/dashboard/compliance/audit/',
            'guide': (
                '🔒 **Compliance e LGPD**\n\n'
                '**Trilha de Auditoria:**\n'
                '1. No menu, acesse **"Compliance"** → **"Auditoria"**\n'
                '2. Veja o log de todas as ações no sistema\n'
                '3. Exporte para CSV se necessário\n\n'
                '**Painel LGPD:**\n'
                '1. Acesse **"Compliance"** → **"LGPD"**\n'
                '2. Gerencie solicitações de dados pessoais\n'
                '3. Processe pedidos de exclusão/portabilidade\n\n'
                '📍 Auditoria: /dashboard/compliance/audit/\n'
                '📍 LGPD: /dashboard/compliance/lgpd/'
            ),
        },
        'pesquisa': {
            'keywords': ['pesquisar', 'buscar', 'procurar', 'search', 'encontrar'],
            'title': '🔍 Pesquisa Avançada',
            'path': '/dashboard/search/',
            'guide': (
                '🔍 **Pesquisa Avançada**\n\n'
                '**Como pesquisar no sistema:**\n\n'
                '1. Use a **barra de pesquisa** no topo da página\n'
                '2. Ou acesse **"Pesquisa Avançada"** no menu\n'
                '3. Pesquise por:\n'
                '   • Tickets (título, descrição, número)\n'
                '   • Clientes (nome, CNPJ, e-mail)\n'
                '   • Usuários\n'
                '4. Use filtros para refinar os resultados\n\n'
                '📍 Acesse em: /dashboard/search/'
            ),
        },
        'exportar': {
            'keywords': ['exportar', 'export', 'download', 'baixar', 'csv', 'excel', 'pdf'],
            'title': '📥 Exportar Dados',
            'path': '/dashboard/export/tickets/',
            'guide': (
                '📥 **Exportar Dados**\n\n'
                '**Exportar tickets:**\n'
                '1. Acesse a lista de tickets\n'
                '2. Aplique os filtros desejados\n'
                '3. Clique em **"Exportar"** (ícone de download)\n'
                '4. Escolha o formato (CSV)\n\n'
                '**Exportar relatórios:**\n'
                '1. Acesse **"Relatórios"**\n'
                '2. Gere o relatório desejado\n'
                '3. Clique em **"Download"**\n\n'
                '📍 Acesse em: /dashboard/export/tickets/'
            ),
        },
        'agente_dashboard': {
            'keywords': ['dashboard agente', 'painel do agente', 'meus atendimentos', 'fila de atendimento', 'agente'],
            'title': '🎧 Dashboard do Agente',
            'path': '/dashboard/agente/',
            'guide': (
                '🎧 **Dashboard do Agente**\n\n'
                '**Como usar o Dashboard do Agente:**\n\n'
                '1. No menu lateral, clique em **"Agente"**\n'
                '2. Veja seus tickets atribuídos\n'
                '3. Acompanhe sua fila de atendimento\n'
                '4. Altere seu status (Online, Ausente, Ocupado)\n\n'
                '📍 Acesse em: /dashboard/agente/'
            ),
        },
        'portal_cliente': {
            'keywords': ['portal do cliente', 'portal cliente', 'área do cliente', 'meus chamados como cliente'],
            'title': '🏠 Portal do Cliente',
            'path': '/dashboard/cliente/',
            'guide': (
                '🏠 **Portal do Cliente**\n\n'
                '**Como usar o Portal do Cliente:**\n\n'
                '1. Faça login com sua conta de cliente\n'
                '2. Veja o painel com seus tickets\n'
                '3. Acompanhe o status dos chamados\n'
                '4. Abra novos chamados\n\n'
                '📍 Acesse em: /dashboard/cliente/'
            ),
        },
    }

    def classify(self, message: str) -> Tuple[IntentType, float]:
        """Classifica a intenção da mensagem"""
        
        message_lower = message.lower().strip()
        best_intent = IntentType.UNKNOWN
        best_confidence = 0.0
        
        for intent, patterns in self.intent_patterns.items():
            confidence = 0.0
            
            for pattern in patterns:
                matches = re.findall(pattern, message_lower, re.IGNORECASE)
                if matches:
                    confidence += len(matches) * 0.3
            
            # Bonus por comprimento da mensagem
            if confidence > 0:
                confidence += min(len(message_lower) / 100, 0.2)
            
            # Bonus para SYSTEM_GUIDE se keywords diretas matcharem
            if intent == IntentType.SYSTEM_GUIDE and confidence > 0:
                for guide_data in self.SYSTEM_GUIDES.values():
                    for keyword in guide_data['keywords']:
                        if keyword in message_lower:
                            confidence += 0.4
                            break
            
            if confidence > best_confidence:
                best_confidence = confidence
                best_intent = intent
        
        # Garantir que a confiança não exceda 1.0
        best_confidence = min(best_confidence, 1.0)
        
        return best_intent, best_confidence

class KnowledgeBase:
    """Base de conhecimento para respostas do chatbot"""
    
    def __init__(self):
        self.responses = {
            IntentType.GREETING: [
                "Olá! 👋 Sou o assistente virtual do iConnect. Como posso ajudá-lo hoje?",
                "Oi! Bem-vindo ao atendimento iConnect. Em que posso ser útil?",
                "Olá! Estou aqui para ajudar. O que você gostaria de saber?"
            ],
            IntentType.HELP_REQUEST: [
                "Claro! Posso ajudá-lo com:\n• Verificar status de tickets\n• Criar nova solicitação\n• Informações sobre sua conta\n• Suporte técnico\n• Estatísticas do dia\n\nO que você precisa?",
                "Estou aqui para ajudar! Você pode me perguntar sobre tickets, problemas técnicos, cobrança, estatísticas ou qualquer dúvida sobre nossos serviços."
            ],
            IntentType.BILLING_QUESTION: [
                "💰 Para questões de cobrança e faturamento, posso ajudar com:\n\n• Consultar faturas pendentes\n• Verificar pagamentos recentes\n• Informações sobre valores\n\nPrecisa de algo específico?",
            ],
            IntentType.ACCOUNT_INFO: [
                "👤 Para informações da sua conta, posso ajudar com:\n\n• Visualizar seus dados cadastrais\n• Atualizar informações de contato\n• Verificar permissões\n\nO que você precisa alterar?",
            ],
            IntentType.SCHEDULE_CALLBACK: [
                "📞 Entendi que você quer agendar um contato! Posso encaminhar sua solicitação para que um agente entre em contato com você. Deseja prosseguir?",
            ],
            IntentType.COMPLAINT: [
                "😟 Lamento que você esteja insatisfeito. Sua opinião é muito importante para nós.\n\nPara resolver sua situação, posso:\n• Criar um ticket prioritário\n• Encaminhar para um supervisor\n\nO que prefere?",
            ],
            IntentType.GOODBYE: [
                "Obrigado por usar o iConnect! Tenha um ótimo dia! 😊",
                "Foi um prazer ajudá-lo! Até logo! 👋",
                "Obrigado! Se precisar de mais alguma coisa, estarei aqui. Tchau! 😊"
            ],
            IntentType.UNKNOWN: [
                "Desculpe, não entendi muito bem. Você pode reformular sua pergunta?",
                "Hmm, não tenho certeza do que você quer dizer. Pode me dar mais detalhes?",
                "Não compreendi completamente. Tente perguntar sobre tickets, estatísticas ou atendimento."
            ]
        }
        
        self.quick_replies = {
            IntentType.GREETING: [
                "Tickets abertos hoje",
                "Resumo do dia",
                "Falar com atendente",
                "Ajuda"
            ],
            IntentType.HELP_REQUEST: [
                "Tickets abertos",
                "Resumo do dia",
                "Tempo de resposta",
                "Clientes urgentes"
            ],
            IntentType.BILLING_QUESTION: [
                "Ver faturas",
                "Falar com financeiro",
                "Voltar ao início"
            ],
            IntentType.ACCOUNT_INFO: [
                "Meus dados",
                "Alterar senha",
                "Voltar ao início"
            ],
            IntentType.COMPLAINT: [
                "Criar ticket urgente",
                "Falar com supervisor",
                "Voltar ao início"
            ],
            IntentType.UNKNOWN: [
                "Tickets abertos hoje",
                "Resumo do dia",
                "Falar com humano",
                "Ajuda"
            ]
        }
    
    def get_response(self, intent: IntentType) -> Tuple[str, List[str]]:
        """Obtém resposta e quick replies para uma intenção"""
        
        responses = self.responses.get(intent, self.responses[IntentType.UNKNOWN])
        quick_replies = self.quick_replies.get(intent, [])
        
        response = random.choice(responses)
        
        return response, quick_replies

class ChatbotService:
    """Serviço principal do chatbot inteligente"""
    
    def __init__(self):
        self.intent_classifier = IntentClassifier()
        self.knowledge_base = KnowledgeBase()
        self.notification_service = NotificationService()
        
        # Contexto da conversa por usuário
        self.conversation_contexts = {}
    
    async def process_message(self, 
                            user_id: int, 
                            message: str, 
                            customer_id: Optional[int] = None) -> ChatbotResponse:
        """
        Processa mensagem do usuário e retorna resposta do chatbot
        """
        
        try:
            # Classificar intenção
            intent, confidence = self.intent_classifier.classify(message)
            
            # Obter contexto da conversa
            context = self.conversation_contexts.get(user_id, {})
            
            # Processar baseado na intenção
            if intent == IntentType.TICKET_STATUS:
                return await self._handle_ticket_status(user_id, message, customer_id, context)
            
            elif intent == IntentType.CREATE_TICKET:
                return await self._handle_create_ticket(user_id, message, customer_id, context)
            
            elif intent == IntentType.TECHNICAL_SUPPORT:
                return await self._handle_technical_support(user_id, message, context)
            
            elif intent == IntentType.ESCALATE:
                return await self._handle_escalation(user_id, message, context)
            
            elif intent == IntentType.DASHBOARD_STATS:
                return await self._handle_dashboard_stats(user_id, message)
            
            elif intent == IntentType.DAILY_SUMMARY:
                return await self._handle_daily_summary(user_id, message)
            
            elif intent == IntentType.AGENT_PERFORMANCE:
                return await self._handle_agent_performance(user_id, message)
            
            elif intent == IntentType.CLIENT_ATTENTION:
                return await self._handle_client_attention(user_id, message)
            
            elif intent == IntentType.SYSTEM_GUIDE:
                return self._handle_system_guide(message)
            
            else:
                # Tentar encontrar guia do sistema antes de dar resposta padrão
                guide_response = self._handle_system_guide(message)
                if guide_response.confidence >= 0.5:
                    return guide_response
                
                # Resposta padrão via knowledge base
                response_text, quick_replies = self.knowledge_base.get_response(intent)
                
                return ChatbotResponse(
                    message=response_text,
                    intent=intent,
                    confidence=confidence,
                    quick_replies=quick_replies,
                    context={'last_intent': intent.value}
                )
        
        except Exception as e:
            logger.error(f"Erro no chatbot: {e}", exc_info=True)
            return self._error_response()
    
    # ====================================
    # HANDLERS ANALÍTICOS (DASHBOARD)
    # ====================================
    
    async def _handle_dashboard_stats(self, user_id: int, message: str) -> ChatbotResponse:
        """Retorna estatísticas de tickets do dashboard"""
        
        @sync_to_async
        def get_stats():
            hoje = timezone.now().date()
            total = Ticket.objects.count()
            abertos = Ticket.objects.filter(status=StatusTicket.ABERTO).count()
            em_andamento = Ticket.objects.filter(status=StatusTicket.EM_ANDAMENTO).count()
            aguardando = Ticket.objects.filter(status=StatusTicket.AGUARDANDO_CLIENTE).count()
            resolvidos_hoje = Ticket.objects.filter(
                status=StatusTicket.RESOLVIDO,
                atualizado_em__date=hoje
            ).count()
            criados_hoje = Ticket.objects.filter(criado_em__date=hoje).count()
            criticos = Ticket.objects.filter(
                prioridade=PrioridadeTicket.CRITICA,
                status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO]
            ).count()
            return {
                'total': total,
                'abertos': abertos,
                'em_andamento': em_andamento,
                'aguardando': aguardando,
                'resolvidos_hoje': resolvidos_hoje,
                'criados_hoje': criados_hoje,
                'criticos': criticos,
            }
        
        stats = await get_stats()
        
        response_text = "📊 **Estatísticas de Tickets**\n\n"
        response_text += f"🎫 Total de tickets: **{stats['total']}**\n"
        response_text += f"📂 Abertos: **{stats['abertos']}**\n"
        response_text += f"⚡ Em andamento: **{stats['em_andamento']}**\n"
        response_text += f"⏳ Aguardando cliente: **{stats['aguardando']}**\n"
        response_text += f"🆕 Criados hoje: **{stats['criados_hoje']}**\n"
        response_text += f"✅ Resolvidos hoje: **{stats['resolvidos_hoje']}**\n"
        
        if stats['criticos'] > 0:
            response_text += f"\n🚨 **{stats['criticos']} ticket(s) crítico(s) ativo(s)!**"
        
        return ChatbotResponse(
            message=response_text,
            intent=IntentType.DASHBOARD_STATS,
            confidence=0.95,
            quick_replies=["Resumo do dia", "Tempo de resposta", "Clientes urgentes", "Criar ticket"]
        )
    
    async def _handle_daily_summary(self, user_id: int, message: str) -> ChatbotResponse:
        """Retorna resumo completo do dia"""
        
        @sync_to_async
        def get_summary():
            hoje = timezone.now().date()
            
            criados = Ticket.objects.filter(criado_em__date=hoje).count()
            resolvidos = Ticket.objects.filter(
                status=StatusTicket.RESOLVIDO,
                atualizado_em__date=hoje
            ).count()
            fechados = Ticket.objects.filter(
                status=StatusTicket.FECHADO,
                atualizado_em__date=hoje
            ).count()
            
            abertos_ativos = Ticket.objects.filter(
                status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO]
            ).count()
            
            # Distribuição por prioridade dos ativos
            por_prioridade = dict(
                Ticket.objects.filter(
                    status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO]
                ).values_list('prioridade').annotate(c=Count('id')).values_list('prioridade', 'c')
            )
            
            # Agentes ativos hoje
            agentes_ativos = Ticket.objects.filter(
                atualizado_em__date=hoje,
                agente__isnull=False
            ).values('agente').distinct().count()
            
            return {
                'criados': criados,
                'resolvidos': resolvidos,
                'fechados': fechados,
                'abertos_ativos': abertos_ativos,
                'por_prioridade': por_prioridade,
                'agentes_ativos': agentes_ativos,
            }
        
        s = await get_summary()
        
        response_text = "📋 **Resumo do Dia**\n\n"
        response_text += f"🆕 Tickets criados hoje: **{s['criados']}**\n"
        response_text += f"✅ Resolvidos hoje: **{s['resolvidos']}**\n"
        response_text += f"🔒 Fechados hoje: **{s['fechados']}**\n"
        response_text += f"📂 Ativos no momento: **{s['abertos_ativos']}**\n"
        response_text += f"👥 Agentes ativos hoje: **{s['agentes_ativos']}**\n"
        
        pp = s['por_prioridade']
        if pp:
            response_text += "\n**Ativos por prioridade:**\n"
            prio_labels = {'critica': '🔴 Crítica', 'alta': '🟠 Alta', 'media': '🟡 Média', 'baixa': '🟢 Baixa'}
            for pk, label in prio_labels.items():
                if pp.get(pk, 0) > 0:
                    response_text += f"  {label}: {pp[pk]}\n"
        
        # Taxa de resolução
        if s['criados'] > 0:
            taxa = round((s['resolvidos'] / s['criados']) * 100)
            response_text += f"\n📈 Taxa de resolução: **{taxa}%**"
        
        return ChatbotResponse(
            message=response_text,
            intent=IntentType.DAILY_SUMMARY,
            confidence=0.95,
            quick_replies=["Tickets abertos", "Tempo de resposta", "Clientes urgentes", "Criar ticket"]
        )
    
    async def _handle_agent_performance(self, user_id: int, message: str) -> ChatbotResponse:
        """Retorna métricas de performance dos agentes"""
        
        @sync_to_async
        def get_performance():
            hoje = timezone.now().date()
            semana = hoje - timedelta(days=7)
            
            # Tickets resolvidos por agente esta semana
            agentes = list(
                Ticket.objects.filter(
                    agente__isnull=False,
                    atualizado_em__date__gte=semana
                ).values(
                    'agente__first_name', 'agente__last_name', 'agente__username'
                ).annotate(
                    total=Count('id'),
                    resolvidos=Count('id', filter=Q(status=StatusTicket.RESOLVIDO)),
                ).order_by('-resolvidos')[:5]
            )
            
            # Tempo médio de primeira resposta (se disponível)
            tickets_com_resposta = Ticket.objects.filter(
                first_response_at__isnull=False,
                criado_em__date__gte=semana
            )
            avg_first_response = None
            if tickets_com_resposta.exists():
                # Calcular média em Python pois F() com datetime diffs varia por DB
                total_min = 0
                count = 0
                for t in tickets_com_resposta[:100]:
                    delta = (t.first_response_at - t.criado_em).total_seconds() / 60
                    if delta > 0:
                        total_min += delta
                        count += 1
                if count > 0:
                    avg_first_response = total_min / count
            
            return {
                'agentes': agentes,
                'avg_first_response': avg_first_response,
            }
        
        perf = await get_performance()
        
        response_text = "⏱️ **Performance dos Agentes** (últimos 7 dias)\n\n"
        
        if perf['avg_first_response'] is not None:
            mins = int(perf['avg_first_response'])
            if mins >= 60:
                response_text += f"📨 Tempo médio de primeira resposta: **{mins // 60}h {mins % 60}min**\n\n"
            else:
                response_text += f"📨 Tempo médio de primeira resposta: **{mins} min**\n\n"
        
        if perf['agentes']:
            response_text += "**Top agentes:**\n"
            for i, a in enumerate(perf['agentes'], 1):
                nome = a.get('agente__first_name') or a.get('agente__username', 'N/A')
                sobrenome = a.get('agente__last_name', '')
                nome_completo = f"{nome} {sobrenome}".strip()
                response_text += f"  {i}. {nome_completo}: {a['resolvidos']}/{a['total']} resolvidos\n"
        else:
            response_text += "Nenhum agente com atividade registrada."
        
        return ChatbotResponse(
            message=response_text,
            intent=IntentType.AGENT_PERFORMANCE,
            confidence=0.9,
            quick_replies=["Tickets abertos", "Resumo do dia", "Clientes urgentes"]
        )
    
    async def _handle_client_attention(self, user_id: int, message: str) -> ChatbotResponse:
        """Retorna clientes que precisam de atenção imediata"""
        
        @sync_to_async
        def get_clients():
            agora = timezone.now()
            
            # Tickets críticos/altos abertos, ordenados por antiguidade
            tickets_urgentes = list(
                Ticket.objects.filter(
                    status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO],
                    prioridade__in=[PrioridadeTicket.CRITICA, PrioridadeTicket.ALTA]
                ).select_related('cliente').order_by('criado_em')[:10]
            )
            
            # Tickets com SLA prestes a vencer
            sla_risco = list(
                Ticket.objects.filter(
                    sla_deadline__isnull=False,
                    sla_deadline__lte=agora + timedelta(hours=2),
                    sla_deadline__gt=agora,
                    status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO]
                ).select_related('cliente').order_by('sla_deadline')[:5]
            )
            
            # Tickets sem resposta há mais de 24h
            sem_resposta = list(
                Ticket.objects.filter(
                    status=StatusTicket.ABERTO,
                    first_response_at__isnull=True,
                    criado_em__lte=agora - timedelta(hours=24)
                ).select_related('cliente').order_by('criado_em')[:5]
            )
            
            return {
                'urgentes': tickets_urgentes,
                'sla_risco': sla_risco,
                'sem_resposta': sem_resposta,
            }
        
        data = await get_clients()
        
        response_text = "🚨 **Clientes que Precisam de Atenção**\n\n"
        
        if data['urgentes']:
            response_text += "**Tickets críticos/alta prioridade:**\n"
            for t in data['urgentes'][:5]:
                prio_emoji = '🔴' if t.prioridade == PrioridadeTicket.CRITICA else '🟠'
                cliente_nome = t.cliente.nome if t.cliente else 'N/A'
                tempo = timezone.now() - t.criado_em
                horas = int(tempo.total_seconds() / 3600)
                response_text += f"  {prio_emoji} #{t.numero} - {cliente_nome} ({t.titulo[:40]})"
                response_text += f" — há {horas}h\n"
        else:
            response_text += "✅ Nenhum ticket crítico/alto no momento.\n"
        
        if data['sem_resposta']:
            response_text += f"\n⚠️ **{len(data['sem_resposta'])} ticket(s) sem resposta há +24h:**\n"
            for t in data['sem_resposta'][:3]:
                cliente_nome = t.cliente.nome if t.cliente else 'N/A'
                response_text += f"  📭 #{t.numero} - {cliente_nome}\n"
        
        if data['sla_risco']:
            response_text += f"\n⏰ **{len(data['sla_risco'])} ticket(s) com SLA prestes a vencer:**\n"
            for t in data['sla_risco'][:3]:
                cliente_nome = t.cliente.nome if t.cliente else 'N/A'
                response_text += f"  ⏳ #{t.numero} - {cliente_nome}\n"
        
        if not data['urgentes'] and not data['sem_resposta'] and not data['sla_risco']:
            response_text = "✅ **Tudo em dia!** Nenhum cliente precisa de atenção imediata no momento."
        
        return ChatbotResponse(
            message=response_text,
            intent=IntentType.CLIENT_ATTENTION,
            confidence=0.9,
            quick_replies=["Tickets abertos", "Resumo do dia", "Tempo de resposta"]
        )
    
    # ====================================
    # HANDLERS ORIGINAIS
    # ====================================
    
    async def _handle_ticket_status(self, user_id: int, message: str, customer_id: int, context: Dict) -> ChatbotResponse:
        """Lida com consulta de status de ticket"""
        
        # Extrair número do ticket da mensagem
        ticket_number = self._extract_ticket_number(message)
        
        if ticket_number:
            @sync_to_async
            def find_ticket():
                try:
                    return Ticket.objects.select_related('cliente', 'agente').get(numero=ticket_number)
                except Ticket.DoesNotExist:
                    return None
            
            ticket = await find_ticket()
            
            if ticket:
                response_text = f"📋 **Ticket #{ticket.numero}**\n\n"
                response_text += f"**Status:** {ticket.get_status_display()}\n"
                response_text += f"**Título:** {ticket.titulo}\n"
                response_text += f"**Prioridade:** {ticket.get_prioridade_display()}\n"
                response_text += f"**Criado em:** {ticket.criado_em.strftime('%d/%m/%Y às %H:%M')}\n"
                
                if ticket.agente:
                    response_text += f"**Agente:** {ticket.agente.get_full_name() or ticket.agente.username}\n"
                
                quick_replies = ["Tickets abertos", "Resumo do dia", "Criar ticket"]
                
                return ChatbotResponse(
                    message=response_text,
                    intent=IntentType.TICKET_STATUS,
                    confidence=0.9,
                    quick_replies=quick_replies,
                    context={'current_ticket': ticket.id}
                )
            else:
                return ChatbotResponse(
                    message=f"Não encontrei o ticket #{ticket_number}. Verifique se o número está correto.",
                    intent=IntentType.TICKET_STATUS,
                    confidence=0.8,
                    quick_replies=["Tickets abertos", "Criar ticket"]
                )
        else:
            # Mostrar tickets recentes abertos
            @sync_to_async
            def get_tickets():
                return list(
                    Ticket.objects.filter(
                        status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO]
                    ).select_related('cliente').order_by('-criado_em')[:5]
                )
            
            tickets = await get_tickets()
            
            if tickets:
                response_text = "🎫 **Tickets abertos recentes:**\n\n"
                
                for ticket in tickets:
                    status_emoji = self._get_status_emoji(ticket.status)
                    cliente_nome = ticket.cliente.nome if ticket.cliente else 'N/A'
                    response_text += f"{status_emoji} **#{ticket.numero}** — {ticket.titulo[:50]}\n"
                    response_text += f"   Cliente: {cliente_nome} | {ticket.get_prioridade_display()}\n\n"
                
                return ChatbotResponse(
                    message=response_text,
                    intent=IntentType.TICKET_STATUS,
                    confidence=0.8,
                    quick_replies=[f"Ver #{t.numero}" for t in tickets[:3]]
                )
            else:
                return ChatbotResponse(
                    message="✅ Não há tickets abertos no momento!",
                    intent=IntentType.TICKET_STATUS,
                    confidence=0.7,
                    quick_replies=["Criar ticket", "Resumo do dia"]
                )
    
    async def _handle_create_ticket(self, user_id: int, message: str, customer_id: int, context: Dict) -> ChatbotResponse:
        """Lida com criação de novo ticket"""
        
        # Iniciar fluxo de criação
        response_text = "📝 **Criar Novo Ticket**\n\n"
        response_text += "Para criar um ticket, acesse a página de criação:\n\n"
        response_text += "👉 [Dashboard → Tickets → Novo Ticket](/dashboard/tickets/criar/)\n\n"
        response_text += "Ou me diga o que está acontecendo e eu posso ajudar a classificar o problema."
        
        return ChatbotResponse(
            message=response_text,
            intent=IntentType.CREATE_TICKET,
            confidence=0.8,
            quick_replies=["Problema técnico", "Reclamação", "Dúvida", "Voltar"]
        )
    
    async def _handle_technical_support(self, user_id: int, message: str, context: Dict) -> ChatbotResponse:
        """Lida com suporte técnico"""
        
        problem_keywords = {
            'lento': 'performance',
            'travou': 'crash',
            'não carrega': 'loading',
            'erro': 'error',
            'bug': 'bug',
            'não funciona': 'malfunction'
        }
        
        detected_problem = None
        for keyword, problem_type in problem_keywords.items():
            if keyword in message.lower():
                detected_problem = problem_type
                break
        
        suggestions = {
            'performance': [
                "• Tente fechar outros aplicativos\n",
                "• Verifique sua conexão de internet\n",
                "• Limpe o cache do navegador\n"
            ],
            'loading': [
                "• Recarregue a página (F5)\n",
                "• Verifique sua conexão\n",
                "• Tente em uma aba anônima\n"
            ],
            'error': [
                "• Anote a mensagem de erro completa\n",
                "• Tente fazer logout e login novamente\n",
                "• Verifique se o problema persiste\n"
            ]
        }
        
        if detected_problem and detected_problem in suggestions:
            response_text = "🔧 **Suporte Técnico**\n\n"
            response_text += f"Entendi que você está com problemas. Tente estas soluções:\n\n"
            response_text += "".join(suggestions[detected_problem])
            response_text += "\nSe o problema persistir, posso criar um ticket para você!"
            
            quick_replies = ["Funcionou!", "Não resolveu", "Criar ticket"]
        else:
            response_text = "🔧 **Suporte Técnico**\n\n"
            response_text += "Para te ajudar melhor, preciso de mais detalhes:\n\n"
            response_text += "• Que tipo de problema está acontecendo?\n"
            response_text += "• Quando começou?\n"
            response_text += "• Você recebeu alguma mensagem de erro?\n"
            
            quick_replies = ["Sistema lento", "Erro na tela", "Não carrega", "Criar ticket"]
        
        return ChatbotResponse(
            message=response_text,
            intent=IntentType.TECHNICAL_SUPPORT,
            confidence=0.8,
            quick_replies=quick_replies
        )
    
    async def _handle_escalation(self, user_id: int, message: str, context: Dict) -> ChatbotResponse:
        """Lida com escalonamento para agente humano"""
        
        response_text = "🤝 **Transferindo para Agente Humano**\n\n"
        response_text += "Entendo que você precisa falar com uma pessoa. "
        response_text += "Estou conectando você com um de nossos agentes.\n\n"
        response_text += "⏱️ **Tempo estimado de espera:** 2-5 minutos\n\n"
        response_text += "Enquanto aguarda, você pode me contar mais detalhes sobre o que precisa?"
        
        return ChatbotResponse(
            message=response_text,
            intent=IntentType.ESCALATE,
            confidence=0.9,
            requires_human=True,
            actions=['escalate_to_human'],
            context={'escalation_requested': True}
        )
    
    # ====================================
    # HANDLER DE GUIA DO SISTEMA
    # ====================================

    def _handle_system_guide(self, message: str) -> ChatbotResponse:
        """Busca o guia mais adequado para a pergunta do usuário"""
        import difflib
        message_lower = message.lower().strip()
        
        best_match = None
        best_score = 0
        
        for guide_key, guide_data in self.intent_classifier.SYSTEM_GUIDES.items():
            score = 0
            
            # Verificar keywords diretas
            for keyword in guide_data['keywords']:
                if keyword in message_lower:
                    keyword_score = len(keyword.split()) * 0.3 + 0.4
                    score = max(score, keyword_score)
            
            # Verificar similaridade com título
            title_clean = re.sub(r'[^\w\s]', '', guide_data['title'].lower())
            title_similarity = difflib.SequenceMatcher(None, message_lower, title_clean).ratio()
            score = max(score, title_similarity)
            
            if score > best_score:
                best_score = score
                best_match = guide_data
        
        if best_match and best_score >= 0.3:
            # Sugestões contextuais
            related = self._get_related_suggestions(best_match)
            
            return ChatbotResponse(
                message=best_match['guide'],
                intent=IntentType.SYSTEM_GUIDE,
                confidence=min(best_score + 0.3, 1.0),
                quick_replies=related,
                context={'guide_key': best_match['title']}
            )
        
        # Se não encontrou match específico, retorna help geral
        return self._handle_system_help()

    def _handle_system_help(self) -> ChatbotResponse:
        """Retorna visão geral de todas as funcionalidades do sistema"""
        features_text = (
            '🗺️ **Guia Completo do Sistema iConnect**\n\n'
            'Posso te ensinar a usar qualquer funcionalidade! Aqui está tudo o que o sistema oferece:\n\n'
            '📋 **Tickets** — Criar, listar, editar, Kanban\n'
            '👥 **Clientes** — Cadastrar e gerenciar empresas\n'
            '🏪 **Pontos de Venda** — Unidades/filiais\n'
            '👤 **Usuários** — Criar, editar, permissões\n'
            '⏱️ **SLA** — Políticas e alertas de prazo\n'
            '💬 **Chat** — Comunicação interna em tempo real\n'
            '📈 **Relatórios** — Analytics e exportações\n'
            '🤖 **Automação** — Regras e workflows visuais\n'
            '📱 **WhatsApp** — Integração Business\n'
            '📚 **Base de Conhecimento** — Artigos e FAQ\n'
            '⚡ **Macros** — Respostas rápidas\n'
            '🔔 **Notificações** — Alertas em tempo real\n'
            '🔒 **Compliance** — Auditoria e LGPD\n'
            '🔍 **Pesquisa** — Busca avançada\n\n'
            'Pergunte sobre qualquer item acima! Exemplo: "Como criar um ticket?"'
        )
        return ChatbotResponse(
            message=features_text,
            intent=IntentType.SYSTEM_GUIDE,
            confidence=1.0,
            quick_replies=['Como criar um ticket?', 'Como gerenciar clientes?', 'Como usar o Kanban?'],
        )

    def _get_related_suggestions(self, current_guide: Dict) -> List[str]:
        """Retorna sugestões de guias relacionados"""
        related_map = {
            '📊 Dashboard Principal': ['Como criar um ticket?', 'Como ver relatórios?', 'O que o sistema faz?'],
            '📝 Criar Novo Ticket': ['Como ver meus tickets?', 'Como usar o Kanban?', 'Como editar um ticket?'],
            '📋 Listar e Pesquisar Tickets': ['Como criar um ticket?', 'Como usar o Kanban?', 'Como exportar dados?'],
            '📌 Quadro Kanban': ['Como criar um ticket?', 'Como ver meus tickets?', 'Como editar um ticket?'],
            '✏️ Editar Ticket': ['Como ver meus tickets?', 'Como usar o Kanban?', 'Como criar um ticket?'],
            '👥 Gestão de Clientes': ['Como cadastrar um PDV?', 'Como criar um ticket?', 'Como gerenciar usuários?'],
            '🏪 Pontos de Venda': ['Como gerenciar clientes?', 'Como criar um ticket?', 'O que o sistema faz?'],
            '👤 Gestão de Usuários': ['Como gerenciar clientes?', 'O que o sistema faz?', 'Como usar compliance?'],
            '⚙️ Meu Perfil': ['Como gerenciar usuários?', 'Como criar um ticket?', 'O que o sistema faz?'],
            '⏱️ Gestão de SLA': ['Como ver relatórios?', 'Como criar um ticket?', 'Como usar notificações?'],
            '💬 Chat Interno': ['Como criar um ticket?', 'Como usar o WhatsApp?', 'O que o sistema faz?'],
            '📈 Relatórios e Analytics': ['Como exportar dados?', 'Como gerenciar SLA?', 'O que o sistema faz?'],
            '🔔 Notificações': ['Como gerenciar SLA?', 'Como ver meus tickets?', 'O que o sistema faz?'],
            '🤖 Automação e Workflows': ['Como gerenciar SLA?', 'Como criar um ticket?', 'O que o sistema faz?'],
            '📱 WhatsApp Business': ['Como usar o chat?', 'Como criar um ticket?', 'O que o sistema faz?'],
            '📚 Base de Conhecimento': ['Como usar macros?', 'O que o sistema faz?', 'Como criar um ticket?'],
            '⚡ Respostas Rápidas (Macros)': ['Como usar a base de conhecimento?', 'Como criar um ticket?', 'O que o sistema faz?'],
            '🔒 Compliance e LGPD': ['Como gerenciar usuários?', 'O que o sistema faz?', 'Como ver relatórios?'],
            '🔍 Pesquisa Avançada': ['Como ver meus tickets?', 'Como gerenciar clientes?', 'O que o sistema faz?'],
            '📥 Exportar Dados': ['Como ver relatórios?', 'Como ver meus tickets?', 'O que o sistema faz?'],
            '🎧 Dashboard do Agente': ['Como ver meus tickets?', 'Como criar um ticket?', 'O que o sistema faz?'],
            '🏠 Portal do Cliente': ['Como criar um ticket?', 'Como ver meus tickets?', 'O que o sistema faz?'],
        }
        
        title = current_guide.get('title', '')
        return related_map.get(title, ['O que o sistema faz?', 'Como criar um ticket?', 'Como gerenciar clientes?'])

    # ====================================
    # MÉTODOS AUXILIARES
    # ====================================
    
    def _extract_ticket_number(self, message: str) -> Optional[str]:
        """Extrai número do ticket da mensagem"""
        
        patterns = [
            r'#(TK-?\d+)',
            r'(TK-\d+)',
            r'#(\d+)',
            r'ticket (\d+)',
            r'número (\d+)',
            r'protocolo (\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _get_status_emoji(self, status: str) -> str:
        """Retorna emoji baseado no status"""
        
        emoji_map = {
            'aberto': '📂',
            'em_andamento': '⚡',
            'aguardando_cliente': '⏳',
            'resolvido': '✅',
            'fechado': '🔒'
        }
        
        return emoji_map.get(status, '📋')
    
    def _error_response(self) -> ChatbotResponse:
        """Resposta de erro genérica"""
        
        return ChatbotResponse(
            message="Desculpe, ocorreu um erro ao processar sua mensagem. Tente novamente ou fale com um agente.",
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            quick_replies=["Tentar novamente", "Falar com agente"],
            requires_human=True
        )


# Instância global do serviço
chatbot_service = ChatbotService()
