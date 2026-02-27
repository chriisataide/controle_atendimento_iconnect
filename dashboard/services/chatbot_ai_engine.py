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
    
    def _analyze_intent(self, message: str) -> str:
        """Analisa a intenção da mensagem"""
        message_lower = message.lower()
        
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
        if intent == 'greeting':
            return {
                'text': 'Olá! 👋 Sou o assistente virtual da iConnect. Como posso ajudá-lo hoje?',
                'confidence': 1.0,
                'suggestions': [
                    'Verificar status do meu ticket',
                    'Criar um novo chamado',
                    'Falar com um atendente'
                ]
            }
        
        elif intent == 'farewell':
            return {
                'text': 'Até logo! 👋 Se precisar de mais alguma coisa, estarei aqui.',
                'confidence': 1.0
            }
        
        elif intent == 'help':
            return {
                'text': 'Posso ajudá-lo com várias coisas:\n\n• Verificar status de tickets\n• Criar novos chamados\n• Fornecer informações sobre nossos serviços\n• Conectá-lo com um atendente\n\nO que você gostaria de fazer?',
                'confidence': 1.0,
                'suggestions': [
                    'Status do ticket',
                    'Novo chamado',
                    'Falar com atendente'
                ]
            }
        
        elif intent == 'ticket_status':
            return self._handle_ticket_status(message, conversation)
        
        elif intent == 'create_ticket':
            return self._handle_create_ticket(message, conversation)
        
        # Buscar na base de conhecimento
        kb_response = self._search_knowledge_base(message)
        if kb_response['confidence'] >= self.confidence_threshold:
            return kb_response
        
        # Resposta padrão
        return {
            'text': 'Entendo sua pergunta, mas não tenho uma resposta específica para isso. Posso conectá-lo com um de nossos atendentes que poderá ajudá-lo melhor.',
            'confidence': 0.3,
            'should_transfer': True,
            'suggestions': [
                'Falar com atendente',
                'Ver perguntas frequentes',
                'Tentar reformular a pergunta'
            ]
        }
    
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