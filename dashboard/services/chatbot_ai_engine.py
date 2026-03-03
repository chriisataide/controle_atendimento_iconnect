import json
import re
import difflib
from typing import Dict, List, Tuple, Optional
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from ..models import ChatbotKnowledgeBase, ChatbotConversation, ChatbotMessage, ChatbotConfiguration
from ..models import Ticket, PerfilUsuario, Cliente
import logging

logger = logging.getLogger(__name__)


class ChatbotAIEngine:
    """Engine principal do chatbot com IA"""
    
    def __init__(self):
        self.confidence_threshold = 0.7
        self.max_suggestions = 3
        self.load_configurations()
    
    def load_configurations(self):
        """Carrega configurações do banco"""
        try:
            configs = ChatbotConfiguration.objects.filter(ativo=True)
            for config in configs:
                if config.nome == 'confidence_threshold':
                    self.confidence_threshold = config.get_value()
                elif config.nome == 'max_suggestions':
                    self.max_suggestions = config.get_value()
        except Exception as e:
            logger.warning(f"Erro ao carregar configurações: {e}")
    
    def process_message(self, message: str, session_id: str, user=None) -> Dict:
        """Processa uma mensagem do usuário"""
        try:
            # Obter ou criar conversa
            conversation = self._get_or_create_conversation(session_id, user)
            
            # Salvar mensagem do usuário
            user_message = ChatbotMessage.objects.create(
                conversa=conversation,
                tipo='user',
                conteudo=message,
                metadados={'processed_at': timezone.now().isoformat()}
            )
            
            # Analisar intenção
            intent = self._analyze_intent(message)
            
            # Gerar resposta
            response_data = self._generate_response(message, intent, conversation)
            
            # Salvar resposta do bot
            bot_message = ChatbotMessage.objects.create(
                conversa=conversation,
                tipo='bot',
                conteudo=response_data['text'],
                confianca=response_data['confidence'],
                metadados={
                    'intent': intent,
                    'suggestions': response_data.get('suggestions', []),
                    'processed_at': timezone.now().isoformat()
                }
            )
            
            return {
                'success': True,
                'response': response_data['text'],
                'confidence': response_data['confidence'],
                'intent': intent,
                'suggestions': response_data.get('suggestions', []),
                'conversation_id': str(conversation.uuid),
                'should_transfer': response_data.get('should_transfer', False)
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}")
            return {
                'success': False,
                'response': 'Desculpe, ocorreu um erro interno. Tente novamente.',
                'error': str(e)
            }
    
    def _get_or_create_conversation(self, session_id: str, user=None) -> ChatbotConversation:
        """Obtém ou cria uma conversa"""
        conversation, created = ChatbotConversation.objects.get_or_create(
            session_id=session_id,
            ativa=True,
            defaults={
                'usuario': user,
                'contexto': {}
            }
        )
        return conversation
    
    # Mapa completo de funcionalidades do sistema com roteiros passo a passo
    SYSTEM_GUIDES = {
        'dashboard': {
            'keywords': ['dashboard', 'painel', 'início', 'home', 'tela inicial', 'página inicial', 'visão geral'],
            'title': '📊 Dashboard Principal',
            'path': '/dashboard/',
            'guide': (
                '**Como acessar o Dashboard:**\n\n'
                '1. Faça login no sistema\n'
                '2. Você será redirecionado automaticamente para o **Dashboard**\n'
                '3. Ou acesse pelo menu lateral clicando em **"Dashboard"**\n\n'
                '**O que você encontra no Dashboard:**\n'
                '• Resumo de tickets abertos, em andamento e resolvidos\n'
                '• Gráficos de desempenho\n'
                '• Alertas de SLA\n'
                '• Atividades recentes\n\n'
                '📍 **Acesse em:** `/dashboard/`'
            ),
        },
        'criar_ticket': {
            'keywords': ['criar ticket', 'novo ticket', 'abrir ticket', 'novo chamado', 'abrir chamado', 'criar chamado', 'registrar chamado', 'registrar ticket'],
            'title': '📝 Criar Novo Ticket',
            'path': '/dashboard/tickets/novo/',
            'guide': (
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
                '💡 **Dica:** Quanto mais detalhes na descrição, mais rápido será o atendimento!\n\n'
                '📍 **Acesse em:** `/dashboard/tickets/novo/`'
            ),
        },
        'listar_tickets': {
            'keywords': ['listar tickets', 'ver tickets', 'meus tickets', 'todos tickets', 'lista de tickets', 'lista de chamados', 'pesquisar ticket', 'buscar ticket', 'encontrar ticket'],
            'title': '📋 Listar e Pesquisar Tickets',
            'path': '/dashboard/tickets/',
            'guide': (
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
                '📍 **Acesse em:** `/dashboard/tickets/`'
            ),
        },
        'kanban': {
            'keywords': ['kanban', 'quadro kanban', 'board', 'arrastar ticket', 'mover ticket', 'visualização kanban'],
            'title': '📌 Quadro Kanban',
            'path': '/dashboard/tickets/kanban/',
            'guide': (
                '**Como usar o Quadro Kanban:**\n\n'
                '1. No menu lateral, clique em **"Tickets"** → **"Kanban"**\n'
                '2. Os tickets são organizados em colunas por status:\n'
                '   • **Aberto** → **Em Andamento** → **Aguardando** → **Resolvido**\n'
                '3. **Arraste e solte** os cards para mudar o status\n'
                '4. Clique em um card para ver detalhes completos\n\n'
                '💡 **Dica:** O Kanban é ideal para ter uma visão rápida do fluxo de trabalho!\n\n'
                '📍 **Acesse em:** `/dashboard/tickets/kanban/`'
            ),
        },
        'editar_ticket': {
            'keywords': ['editar ticket', 'alterar ticket', 'modificar ticket', 'atualizar ticket', 'mudar status', 'alterar chamado', 'editar chamado'],
            'title': '✏️ Editar Ticket',
            'path': '/dashboard/tickets/{id}/editar/',
            'guide': (
                '**Como editar um ticket:**\n\n'
                '1. Acesse a **lista de tickets** (`/dashboard/tickets/`)\n'
                '2. Clique no ticket que deseja editar\n'
                '3. Na página de detalhes, clique em **"Editar"**\n'
                '4. Modifique os campos desejados:\n'
                '   • Status, prioridade, categoria\n'
                '   • Descrição, agente responsável\n'
                '5. Clique em **"Salvar"** para aplicar as alterações\n\n'
                '💡 **Dica:** Você também pode alterar o status rapidamente pelo Kanban!'
            ),
        },
        'clientes': {
            'keywords': ['cliente', 'clientes', 'cadastrar cliente', 'novo cliente', 'listar clientes', 'gestão de clientes', 'gerenciar clientes'],
            'title': '👥 Gestão de Clientes',
            'path': '/dashboard/clientes/',
            'guide': (
                '**Como gerenciar clientes:**\n\n'
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
                '📍 **Acesse em:** `/dashboard/clientes/`'
            ),
        },
        'pontos_de_venda': {
            'keywords': ['ponto de venda', 'pontos de venda', 'pdv', 'unidade', 'filial', 'cadastrar pdv', 'uniorg'],
            'title': '🏪 Pontos de Venda',
            'path': '/dashboard/pontosdevenda/',
            'guide': (
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
                '📍 **Acesse em:** `/dashboard/pontosdevenda/`'
            ),
        },
        'usuarios': {
            'keywords': ['usuário', 'usuarios', 'criar usuário', 'novo usuário', 'editar usuário', 'gerenciar usuários', 'listar usuários', 'permissões', 'nível de acesso', 'role'],
            'title': '👤 Gestão de Usuários',
            'path': '/dashboard/users/',
            'guide': (
                '**Como gerenciar usuários:**\n\n'
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
                '📍 **Acesse em:** `/dashboard/users/`'
            ),
        },
        'perfil': {
            'keywords': ['meu perfil', 'perfil', 'minha conta', 'alterar minha senha', 'trocar senha', 'meus dados', 'configurar perfil'],
            'title': '⚙️ Meu Perfil',
            'path': '/dashboard/profile/',
            'guide': (
                '**Como editar seu perfil:**\n\n'
                '1. Clique no seu **nome/avatar** no canto superior direito\n'
                '2. Selecione **"Perfil"**\n'
                '3. Edite suas informações pessoais\n'
                '4. Clique em **"Salvar"**\n\n'
                '📍 **Acesse em:** `/dashboard/profile/`'
            ),
        },
        'sla': {
            'keywords': ['sla', 'acordo de nível', 'tempo de resposta', 'tempo de resolução', 'prazo', 'políticas sla', 'alertas sla'],
            'title': '⏱️ Gestão de SLA',
            'path': '/dashboard/sla/',
            'guide': (
                '**Como gerenciar SLAs:**\n\n'
                '**Dashboard SLA:**\n'
                '1. No menu lateral, clique em **"SLA"**\n'
                '2. Veja o painel com métricas de cumprimento\n\n'
                '**Criar política de SLA:**\n'
                '1. Acesse **"SLA"** → **"Políticas"**\n'
                '2. Defina tempos de resposta e resolução por prioridade\n\n'
                '**Alertas de SLA:**\n'
                '1. Acesse **"SLA"** → **"Alertas"**\n'
                '2. Veja tickets que estão próximos ou além do prazo\n\n'
                '📍 **Acesse em:** `/dashboard/sla/`'
            ),
        },
        'chat': {
            'keywords': ['chat', 'conversa', 'mensagem', 'conversar', 'chat interno', 'sala de chat'],
            'title': '💬 Chat Interno',
            'path': '/dashboard/chat/',
            'guide': (
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
                '📍 **Acesse em:** `/dashboard/chat/`'
            ),
        },
        'relatorios': {
            'keywords': ['relatório', 'relatorios', 'exportar', 'gerar relatório', 'report', 'analytics', 'análise', 'estatísticas', 'dados', 'métricas'],
            'title': '📈 Relatórios e Analytics',
            'path': '/dashboard/reports/',
            'guide': (
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
                '**Analytics avançado:**\n'
                '• Acesse `/dashboard/analytics/` para dashboards interativos\n\n'
                '**Dashboard Executivo:**\n'
                '• Acesse `/dashboard/executive/` para visão estratégica\n\n'
                '📍 **Acesse em:** `/dashboard/reports/`'
            ),
        },
        'notificacoes': {
            'keywords': ['notificação', 'notificações', 'alerta', 'alertas', 'avisos', 'push'],
            'title': '🔔 Notificações',
            'path': '/dashboard/notifications/',
            'guide': (
                '**Como gerenciar notificações:**\n\n'
                '1. Clique no **ícone do sino** 🔔 no topo da página\n'
                '2. Veja notificações recentes\n'
                '3. Clique em **"Ver todas"** para a lista completa\n\n'
                '**Tipos de notificação:**\n'
                '• Novo ticket atribuído a você\n'
                '• Atualização de status de ticket\n'
                '• Alertas de SLA\n'
                '• Mensagens no chat\n\n'
                '📍 **Acesse em:** `/dashboard/notifications/`'
            ),
        },
        'automacao': {
            'keywords': ['automação', 'automatizar', 'regra', 'regras', 'workflow', 'fluxo', 'automático'],
            'title': '🤖 Automação e Workflows',
            'path': '/dashboard/automation/',
            'guide': (
                '**Como configurar automações:**\n\n'
                '**Regras de automação:**\n'
                '1. No menu, acesse **"Automação"** → **"Regras"**\n'
                '2. Crie regras como: "Se ticket urgente, atribuir ao supervisor"\n\n'
                '**Workflow Builder (Visual):**\n'
                '1. Acesse **"Automação"** → **"Workflows"**\n'
                '2. Use o editor visual para criar fluxos\n'
                '3. Arraste e conecte blocos de ação\n'
                '4. Ative o workflow quando pronto\n\n'
                '📍 **Acesse em:** `/dashboard/automation/`\n'
                '📍 **Workflow Builder:** `/dashboard/workflows/builder/`'
            ),
        },
        'whatsapp': {
            'keywords': ['whatsapp', 'wpp', 'zap', 'mensagem whatsapp', 'integração whatsapp'],
            'title': '📱 WhatsApp Business',
            'path': '/dashboard/whatsapp/',
            'guide': (
                '**Como usar o WhatsApp Business:**\n\n'
                '1. No menu lateral, clique em **"WhatsApp"**\n'
                '2. Configure sua conta Business\n'
                '3. Gerencie contatos e conversas\n'
                '4. Configure respostas automáticas\n'
                '5. Envie e receba mensagens pelo sistema\n\n'
                '📍 **Acesse em:** `/dashboard/whatsapp/`'
            ),
        },
        'base_conhecimento': {
            'keywords': ['base de conhecimento', 'knowledge', 'artigo', 'artigos', 'documentação', 'faq', 'perguntas frequentes', 'manual'],
            'title': '📚 Base de Conhecimento',
            'path': '/dashboard/knowledge/',
            'guide': (
                '**Como usar a Base de Conhecimento:**\n\n'
                '1. No menu lateral, clique em **"Base de Conhecimento"**\n'
                '2. Pesquise artigos por palavra-chave\n'
                '3. Navegue por categorias\n'
                '4. Vote em artigos úteis (👍/👎)\n\n'
                '📍 **Acesse em:** `/dashboard/knowledge/`'
            ),
        },
        'macros': {
            'keywords': ['macro', 'macros', 'resposta rápida', 'respostas rápidas', 'template de resposta', 'modelo de resposta'],
            'title': '⚡ Respostas Rápidas (Macros)',
            'path': '/dashboard/macros/',
            'guide': (
                '**Como usar Respostas Rápidas:**\n\n'
                '1. No menu lateral, clique em **"Macros"**\n'
                '2. Veja as respostas prontas disponíveis\n\n'
                '**Criar nova macro:**\n'
                '1. Clique em **"+ Nova Macro"**\n'
                '2. Defina um título e o texto da resposta\n'
                '3. Salve para usar em tickets\n\n'
                '💡 **Dica:** Use macros nos tickets para responder mais rápido!\n\n'
                '📍 **Acesse em:** `/dashboard/macros/`'
            ),
        },
        'compliance': {
            'keywords': ['compliance', 'auditoria', 'lgpd', 'dados pessoais', 'privacidade', 'audit trail', 'trilha de auditoria'],
            'title': '🔒 Compliance e LGPD',
            'path': '/dashboard/compliance/audit/',
            'guide': (
                '**Como acessar Compliance:**\n\n'
                '**Trilha de Auditoria:**\n'
                '1. No menu, acesse **"Compliance"** → **"Auditoria"**\n'
                '2. Veja o log de todas as ações no sistema\n'
                '3. Exporte para CSV se necessário\n\n'
                '**Painel LGPD:**\n'
                '1. Acesse **"Compliance"** → **"LGPD"**\n'
                '2. Gerencie solicitações de dados pessoais\n'
                '3. Processe pedidos de exclusão/portabilidade\n\n'
                '📍 **Auditoria:** `/dashboard/compliance/audit/`\n'
                '📍 **LGPD:** `/dashboard/compliance/lgpd/`'
            ),
        },
        'pesquisa': {
            'keywords': ['pesquisar', 'buscar', 'procurar', 'search', 'encontrar'],
            'title': '🔍 Pesquisa Avançada',
            'path': '/dashboard/search/',
            'guide': (
                '**Como pesquisar no sistema:**\n\n'
                '1. Use a **barra de pesquisa** no topo da página\n'
                '2. Ou acesse **"Pesquisa Avançada"** no menu\n'
                '3. Pesquise por:\n'
                '   • Tickets (título, descrição, número)\n'
                '   • Clientes (nome, CNPJ, e-mail)\n'
                '   • Usuários\n'
                '4. Use filtros para refinar os resultados\n\n'
                '📍 **Acesse em:** `/dashboard/search/`'
            ),
        },
        'exportar': {
            'keywords': ['exportar', 'export', 'download', 'baixar', 'csv', 'excel', 'pdf'],
            'title': '📥 Exportar Dados',
            'path': '/dashboard/export/tickets/',
            'guide': (
                '**Como exportar dados:**\n\n'
                '**Exportar tickets:**\n'
                '1. Acesse a **lista de tickets**\n'
                '2. Aplique os filtros desejados\n'
                '3. Clique em **"Exportar"** (ícone de download)\n'
                '4. Escolha o formato (CSV)\n\n'
                '**Exportar relatórios:**\n'
                '1. Acesse **"Relatórios"**\n'
                '2. Gere o relatório desejado\n'
                '3. Clique em **"Download"**\n\n'
                '📍 **Acesse em:** `/dashboard/export/tickets/`'
            ),
        },
        'agente_dashboard': {
            'keywords': ['dashboard agente', 'painel do agente', 'meus atendimentos', 'fila de atendimento', 'agente'],
            'title': '🎧 Dashboard do Agente',
            'path': '/dashboard/agente/',
            'guide': (
                '**Como usar o Dashboard do Agente:**\n\n'
                '1. No menu lateral, clique em **"Agente"**\n'
                '2. Veja seus tickets atribuídos\n'
                '3. Acompanhe sua fila de atendimento\n'
                '4. Altere seu status (Online, Ausente, Ocupado)\n\n'
                '**Seus tickets:**\n'
                '1. Acesse **"Agente"** → **"Meus Tickets"**\n'
                '2. Veja e gerencie os chamados atribuídos a você\n\n'
                '📍 **Acesse em:** `/dashboard/agente/`'
            ),
        },
        'portal_cliente': {
            'keywords': ['portal do cliente', 'portal cliente', 'área do cliente', 'meus chamados como cliente'],
            'title': '🏠 Portal do Cliente',
            'path': '/dashboard/cliente/',
            'guide': (
                '**Como usar o Portal do Cliente:**\n\n'
                '1. Faça login com sua conta de cliente\n'
                '2. Veja o painel com seus tickets\n'
                '3. Acompanhe o status dos chamados\n'
                '4. Abra novos chamados\n\n'
                '📍 **Acesse em:** `/dashboard/cliente/`'
            ),
        },
    }

    def _analyze_intent(self, message: str) -> str:
        """Analisa a intenção da mensagem"""
        message_lower = message.lower()
        
        # Verificar se é uma pergunta sobre como usar o sistema (prioridade alta)
        system_guide_patterns = [
            r'\b(como|onde|aonde|qual|quero|preciso|gostaria|me ensina|me mostra|me ajuda)\b.*(fazer|acessar|criar|editar|ver|listar|configurar|usar|mexer|navegar|abrir|encontrar|pesquisar|buscar|exportar|gerenciar|cadastrar|alterar|excluir|deletar)',
            r'\b(onde fica|como faço|como eu|como faz|me explica|me diz|tutorial|passo a passo|roteiro|instruções)\b',
            r'\b(quero|preciso|gostaria de)\b.*(criar|editar|ver|listar|acessar|abrir|cadastrar|exportar|gerar|configurar)',
            r'\b(funcionalidade|função|módulo|seção|página|menu|tela)\b',
            r'\bpara que serve\b',
            r'\bcomo funciona\b',
        ]
        
        for pattern in system_guide_patterns:
            if re.search(pattern, message_lower):
                return 'system_guide'
        
        # Verificar match direto com keywords dos guias
        for guide_key, guide_data in self.SYSTEM_GUIDES.items():
            for keyword in guide_data['keywords']:
                if keyword in message_lower:
                    return 'system_guide'
        
        # Padrões de intenção
        intent_patterns = {
            'greeting': [
                r'\b(oi|olá|bom dia|boa tarde|boa noite|hello|hi)\b',
                r'^(oi|olá)',
            ],
            'farewell': [
                r'\b(tchau|adeus|até logo|obrigad[oa]|valeu)\b',
                r'\b(bye|goodbye)\b',
            ],
            'ticket_status': [
                r'\b(status|situação|andamento).*(ticket|chamado)\b',
                r'\b(como está|qual).*(ticket|chamado)\b',
                r'\bmeu.*(ticket|chamado)\b',
            ],
            'create_ticket': [
                r'\b(criar|abrir|novo).*(ticket|chamado)\b',
                r'\b(problema|issue|bug|erro)\b',
                r'\bpreciso.*(ajuda|suporte)\b',
            ],
            'help': [
                r'\b(ajuda|help|socorro|como)\b',
                r'\b(não sei|não entendo)\b',
            ],
            'complaint': [
                r'\b(reclamação|reclamar|insatisfeito|problema)\b',
                r'\b(ruim|péssimo|horrível)\b',
            ],
            'compliment': [
                r'\b(obrigad[oa]|valeu|legal|bom|ótimo|excelente)\b',
                r'\b(parabéns|muito bom)\b',
            ]
        }
        
        for intent, patterns in intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return intent
        
        return 'general'
    
    def _generate_response(self, message: str, intent: str, conversation: ChatbotConversation) -> Dict:
        """Gera resposta baseada na intenção"""
        
        # Respostas específicas por intenção
        if intent == 'system_guide':
            return self._handle_system_guide(message)
        
        elif intent == 'greeting':
            return {
                'text': 'Olá! 👋 Sou o assistente virtual da iConnect. Posso te ajudar a usar o sistema! Pergunte qualquer coisa, como:\n\n• "Como crio um ticket?"\n• "Onde vejo meus clientes?"\n• "Como funciona o SLA?"\n\nOu escolha uma opção abaixo:',
                'confidence': 1.0,
                'suggestions': [
                    'Como criar um ticket?',
                    'Como gerenciar clientes?',
                    'O que o sistema faz?'
                ]
            }
        
        elif intent == 'farewell':
            return {
                'text': 'Até logo! 👋 Se precisar de ajuda para usar o sistema, estarei aqui.',
                'confidence': 1.0
            }
        
        elif intent == 'help':
            return self._handle_system_help()
        
        elif intent == 'ticket_status':
            return self._handle_ticket_status(message, conversation)
        
        elif intent == 'create_ticket':
            return self._handle_create_ticket(message, conversation)
        
        # Buscar na base de conhecimento
        kb_response = self._search_knowledge_base(message)
        if kb_response['confidence'] >= self.confidence_threshold:
            return kb_response
        
        # Tentar encontrar guia do sistema antes de dar resposta padrão
        guide_response = self._handle_system_guide(message)
        if guide_response['confidence'] >= 0.5:
            return guide_response
        
        # Resposta padrão
        return {
            'text': 'Não encontrei uma resposta específica para isso. Posso te ajudar com:\n\n📋 **Sobre o sistema:** pergunte "o que o sistema faz?"\n📝 **Roteiros:** pergunte "como criar um ticket?"\n👨‍💼 **Atendente:** posso te conectar com um humano\n\nOu tente reformular sua pergunta!',
            'confidence': 0.3,
            'should_transfer': False,
            'suggestions': [
                'O que o sistema faz?',
                'Falar com atendente',
                'Ver funcionalidades'
            ]
        }
    
    def _handle_system_help(self) -> Dict:
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
            '**Pergunte sobre qualquer item acima!** Exemplo: _"Como criar um ticket?"_'
        )
        return {
            'text': features_text,
            'confidence': 1.0,
            'suggestions': [
                'Como criar um ticket?',
                'Como gerenciar clientes?',
                'Como usar o Kanban?',
            ]
        }

    def _handle_system_guide(self, message: str) -> Dict:
        """Busca o guia mais adequado para a pergunta do usuário"""
        message_lower = message.lower()
        
        best_match = None
        best_score = 0
        
        for guide_key, guide_data in self.SYSTEM_GUIDES.items():
            score = 0
            
            # Verificar keywords diretas
            for keyword in guide_data['keywords']:
                if keyword in message_lower:
                    # Score proporcional ao tamanho da keyword (mais específica = melhor)
                    keyword_score = len(keyword.split()) * 0.3 + 0.4
                    score = max(score, keyword_score)
            
            # Verificar similaridade com título do guia
            title_clean = re.sub(r'[^\w\s]', '', guide_data['title'].lower())
            title_similarity = difflib.SequenceMatcher(None, message_lower, title_clean).ratio()
            score = max(score, title_similarity)
            
            if score > best_score:
                best_score = score
                best_match = guide_data
        
        if best_match and best_score >= 0.3:
            return {
                'text': f'**{best_match["title"]}**\n\n{best_match["guide"]}',
                'confidence': min(best_score + 0.3, 1.0),
                'suggestions': self._get_related_suggestions(best_match),
            }
        
        # Se não encontrou match específico, retorna o help geral
        return self._handle_system_help()
    
    def _get_related_suggestions(self, current_guide: Dict) -> List[str]:
        """Retorna sugestões de guias relacionados"""
        # Mapeamento de guias relacionados
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
            '🔒 Compliance e LGPD': ['Como ver auditoria?', 'Como gerenciar usuários?', 'O que o sistema faz?'],
            '🔍 Pesquisa Avançada': ['Como ver meus tickets?', 'Como gerenciar clientes?', 'O que o sistema faz?'],
            '📥 Exportar Dados': ['Como ver relatórios?', 'Como ver meus tickets?', 'O que o sistema faz?'],
            '🎧 Dashboard do Agente': ['Como ver meus tickets?', 'Como criar um ticket?', 'O que o sistema faz?'],
            '🏠 Portal do Cliente': ['Como criar um ticket?', 'Como ver meus tickets?', 'O que o sistema faz?'],
        }
        
        title = current_guide.get('title', '')
        return related_map.get(title, ['O que o sistema faz?', 'Como criar um ticket?', 'Como gerenciar clientes?'])

    def _handle_ticket_status(self, message: str, conversation: ChatbotConversation) -> Dict:
        """Lida com consultas de status de ticket"""
        user = conversation.usuario
        
        if not user:
            return {
                'text': 'Para verificar o status dos seus tickets, preciso que você faça login. Você pode fazer isso clicando no botão "Entrar" no topo da página.',
                'confidence': 0.8,
                'suggestions': ['Fazer login', 'Falar com atendente']
            }
        
        # Buscar tickets do usuário
        tickets = Ticket.objects.filter(cliente__usuario=user).order_by('-criado_em')[:5]
        
        if not tickets.exists():
            return {
                'text': 'Você não possui tickets abertos no momento. Posso ajudá-lo a criar um novo chamado?',
                'confidence': 0.9,
                'suggestions': ['Criar novo ticket', 'Falar com atendente']
            }
        
        response_text = "Aqui estão seus tickets mais recentes:\n\n"
        for ticket in tickets:
            status_emoji = {
                'aberto': '🔴',
                'em_andamento': '🟡',
                'aguardando': '🟠',
                'resolvido': '🟢',
                'fechado': '✅'
            }.get(ticket.status, '⚪')
            
            response_text += f"{status_emoji} **#{ticket.id}** - {ticket.titulo}\n"
            response_text += f"   Status: {ticket.get_status_display()}\n"
            response_text += f"   Criado: {ticket.criado_em.strftime('%d/%m/%Y')}\n\n"
        
        return {
            'text': response_text,
            'confidence': 0.95,
            'suggestions': [
                'Ver detalhes de um ticket',
                'Criar novo ticket',
                'Falar com atendente'
            ]
        }
    
    def _handle_create_ticket(self, message: str, conversation: ChatbotConversation) -> Dict:
        """Lida com criação de tickets"""
        user = conversation.usuario
        
        if not user:
            return {
                'text': 'Para criar um ticket, preciso que você faça login primeiro. Após o login, posso ajudá-lo a criar um chamado.',
                'confidence': 0.8,
                'suggestions': ['Fazer login', 'Falar com atendente']
            }
        
        # Salvar contexto para criação de ticket
        conversation.contexto['creating_ticket'] = True
        conversation.contexto['ticket_description'] = message
        conversation.save()
        
        return {
            'text': 'Vou ajudá-lo a criar um novo ticket! 📝\n\nBaseado na sua mensagem, entendo que você tem um problema. Para acelerar o atendimento, você pode:\n\n1. **Criar agora** - Vou criar um ticket com as informações que você forneceu\n2. **Mais detalhes** - Adicionar mais informações antes de criar\n3. **Falar com atendente** - Ser direcionado para um humano',
            'confidence': 0.9,
            'suggestions': [
                'Criar ticket agora',
                'Adicionar mais detalhes',
                'Falar com atendente'
            ]
        }
    
    def _search_knowledge_base(self, message: str) -> Dict:
        """Busca na base de conhecimento"""
        try:
            # Buscar por similaridade de texto
            kb_items = ChatbotKnowledgeBase.objects.filter(ativo=True)
            
            best_match = None
            best_score = 0
            
            for item in kb_items:
                # Calcular similaridade com a pergunta
                score = difflib.SequenceMatcher(
                    None, 
                    message.lower(), 
                    item.pergunta.lower()
                ).ratio()
                
                # Também verificar tags
                if item.tags:
                    for tag in item.tags.split(','):
                        tag_score = difflib.SequenceMatcher(
                            None, 
                            message.lower(), 
                            tag.strip().lower()
                        ).ratio()
                        score = max(score, tag_score)
                
                if score > best_score:
                    best_score = score
                    best_match = item
            
            if best_match and best_score >= 0.6:
                return {
                    'text': best_match.resposta,
                    'confidence': min(best_score * best_match.confianca, 1.0),
                    'source': 'knowledge_base'
                }
            
        except Exception as e:
            logger.error(f"Erro ao buscar na base de conhecimento: {e}")
        
        return {'text': '', 'confidence': 0.0}
    
    def add_training_data(self, question: str, bot_response: str, expected_response: str = None, 
                         positive_feedback: bool = None, user=None):
        """Adiciona dados de treinamento"""
        from ..models import ChatbotTraining
        
        ChatbotTraining.objects.create(
            pergunta_original=question,
            resposta_bot=bot_response,
            resposta_esperada=expected_response or '',
            feedback_positivo=positive_feedback,
            usuario=user
        )
    
    def get_analytics(self, days: int = 30) -> Dict:
        """Obtém analytics do chatbot"""
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count, Avg
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        conversations = ChatbotConversation.objects.filter(
            iniciada_em__date__range=[start_date, end_date]
        )
        
        messages = ChatbotMessage.objects.filter(
            conversa__in=conversations
        )
        
        return {
            'total_conversations': conversations.count(),
            'total_messages': messages.count(),
            'avg_messages_per_conversation': messages.count() / max(conversations.count(), 1),
            'bot_messages': messages.filter(tipo='bot').count(),
            'user_messages': messages.filter(tipo='user').count(),
            'avg_confidence': messages.filter(tipo='bot', confianca__isnull=False).aggregate(
                avg=Avg('confianca')
            )['avg'] or 0,
            'active_conversations': conversations.filter(ativa=True).count(),
        }


# Instância global do engine
chatbot_engine = ChatbotAIEngine()