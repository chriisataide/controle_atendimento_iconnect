"""
Sistema de Automação e IA para o iConnect.
Inclui auto-assignment, chatbot e análise de sentimento.
"""
import logging
import re
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from .models import Ticket, PerfilAgente, Cliente, InteracaoTicket

logger = logging.getLogger(__name__)


class AutoAssignmentEngine:
    """Engine para distribuição automática de tickets"""
    
    def __init__(self):
        self.ai_config = getattr(settings, 'AI_CONFIG', {})
    
    def assign_ticket(self, ticket):
        """Atribui automaticamente um ticket ao melhor agente disponível"""
        if not self.ai_config.get('AUTO_ASSIGNMENT', True):
            return None
        
        try:
            # Buscar agentes disponíveis
            agentes_disponiveis = self._get_available_agents(ticket.categoria)
            
            if not agentes_disponiveis:
                logger.warning(f"Nenhum agente disponível para ticket #{ticket.numero}")
                return None
            
            # Calcular score para cada agente
            best_agent = self._calculate_best_agent(agentes_disponiveis, ticket)
            
            if best_agent:
                ticket.agente = best_agent
                ticket.status = 'em_andamento'
                ticket.save()
                
                logger.info(f"Ticket #{ticket.numero} atribuído automaticamente a {best_agent.username}")
                return best_agent
            
        except Exception as e:
            logger.error(f"Erro na atribuição automática: {str(e)}")
        
        return None
    
    def _get_available_agents(self, categoria):
        """Retorna agentes disponíveis para uma categoria"""
        try:
            perfis_agentes = PerfilAgente.objects.filter(
                status__in=['online', 'ocupado'],
                user__is_active=True
            ).select_related('user')
            
            agentes_disponiveis = []
            
            for perfil in perfis_agentes:
                # Contar tickets ativos do agente
                tickets_ativos = Ticket.objects.filter(
                    agente=perfil.user,
                    status__in=['aberto', 'em_andamento', 'aguardando_cliente']
                ).count()
                
                # Verificar se agente não excedeu limite
                if tickets_ativos < perfil.max_tickets_simultaneos:
                    agentes_disponiveis.append(perfil)
            
            return agentes_disponiveis
            
        except Exception as e:
            logger.error(f"Erro ao buscar agentes disponíveis: {str(e)}")
            return []
    
    def _calculate_best_agent(self, agentes, ticket):
        """Calcula o melhor agente baseado em vários fatores"""
        best_agent = None
        best_score = -1
        
        for perfil_agente in agentes:
            score = 0
            
            # Fator 1: Carga de trabalho atual (peso: 30%)
            tickets_ativos = Ticket.objects.filter(
                agente=perfil_agente.user,
                status__in=['aberto', 'em_andamento']
            ).count()
            
            carga_percentual = tickets_ativos / perfil_agente.max_tickets_simultaneos
            score += (1 - carga_percentual) * 30
            
            # Fator 2: Especialização na categoria (peso: 25%)
            tickets_categoria = Ticket.objects.filter(
                agente=perfil_agente.user,
                categoria=ticket.categoria,
                status='fechado'
            ).count()
            
            if tickets_categoria > 0:
                score += min(tickets_categoria / 10, 1) * 25
            
            # Fator 3: Performance histórica (peso: 25%)
            tickets_resolvidos = Ticket.objects.filter(
                agente=perfil_agente.user,
                status='fechado'
            ).count()
            
            if tickets_resolvidos > 0:
                score += min(tickets_resolvidos / 50, 1) * 25
            
            # Fator 4: Status atual (peso: 20%)
            if perfil_agente.status == 'online':
                score += 20
            elif perfil_agente.status == 'ocupado':
                score += 10
            
            if score > best_score:
                best_score = score
                best_agent = perfil_agente.user
        
        return best_agent


class SentimentAnalyzer:
    """Analisador de sentimento para interações"""
    
    def __init__(self):
        self.ai_config = getattr(settings, 'AI_CONFIG', {})
        self.negative_words = [
            'ruim', 'péssimo', 'horrível', 'terrível', 'ódio', 'raiva',
            'irritado', 'frustrado', 'decepcionado', 'insatisfeito',
            'problema', 'erro', 'falha', 'bug', 'defeito'
        ]
        self.positive_words = [
            'bom', 'ótimo', 'excelente', 'maravilhoso', 'perfeito',
            'satisfeito', 'feliz', 'contente', 'agradecido', 'obrigado',
            'parabéns', 'sucesso', 'funcionou', 'resolvido', 'solucionado'
        ]
    
    def analyze_sentiment(self, text):
        """Analisa o sentimento de um texto"""
        if not self.ai_config.get('SENTIMENT_ANALYSIS', False):
            return 'neutral'
        
        try:
            text_lower = text.lower()
            
            # Contagem simples de palavras positivas/negativas
            positive_count = sum(1 for word in self.positive_words if word in text_lower)
            negative_count = sum(1 for word in self.negative_words if word in text_lower)
            
            # Análise por intensificadores
            intensifiers = ['muito', 'extremamente', 'super', 'bastante']
            for intensifier in intensifiers:
                if intensifier in text_lower:
                    positive_count *= 1.5
                    negative_count *= 1.5
            
            # Determinar sentimento
            if negative_count > positive_count:
                return 'negative'
            elif positive_count > negative_count:
                return 'positive'
            else:
                return 'neutral'
                
        except Exception as e:
            logger.error(f"Erro na análise de sentimento: {str(e)}")
            return 'neutral'


class ChatbotService:
    """Serviço de chatbot para primeiro atendimento"""
    
    def __init__(self):
        self.ai_config = getattr(settings, 'AI_CONFIG', {})
        self.knowledge_base = {
            'login': {
                'keywords': ['login', 'entrar', 'senha', 'acesso', 'logar'],
                'response': 'Para problemas de login, tente: 1) Verificar se o email está correto, 2) Usar a opção "Esqueci minha senha", 3) Limpar o cache do navegador. Se o problema persistir, nosso time de suporte irá ajudá-lo.'
            },
            'precos': {
                'keywords': ['preço', 'valor', 'custo', 'plano', 'assinatura'],
                'response': 'Nossos planos começam em R$ 99/mês. Temos opções para empresas de todos os tamanhos. Um consultor entrará em contato em breve para apresentar a melhor opção para seu negócio.'
            },
            'suporte': {
                'keywords': ['ajuda', 'suporte', 'problema', 'erro', 'dúvida'],
                'response': 'Estou aqui para ajudar! Descreva seu problema com detalhes e nosso time de suporte técnico irá analisá-lo. Qual a urgência: Baixa, Média, Alta ou Crítica?'
            },
            'funcionalidade': {
                'keywords': ['como', 'funciona', 'usar', 'tutorial', 'manual'],
                'response': 'Vou direcionar você para nosso material de treinamento. Enquanto isso, pode descrever especificamente o que precisa aprender? Nossa documentação completa está disponível na área do cliente.'
            }
        }
    
    def get_bot_response(self, user_message, ticket=None):
        """Gera resposta automática do chatbot"""
        if not self.ai_config.get('ENABLE_CHATBOT', False):
            return None
        
        try:
            message_lower = user_message.lower()
            
            # Buscar categoria mais relevante
            best_category = None
            best_match_count = 0
            
            for category, data in self.knowledge_base.items():
                match_count = sum(1 for keyword in data['keywords'] if keyword in message_lower)
                if match_count > best_match_count:
                    best_match_count = match_count
                    best_category = category
            
            if best_category and best_match_count > 0:
                response = self.knowledge_base[best_category]['response']
                
                # Personalizar resposta se ticket disponível
                if ticket:
                    response += f"\n\nRef: Ticket #{ticket.numero}"
                
                return response
            
            # Resposta padrão
            return "Obrigado por entrar em contato! Analisei sua mensagem e vou direcionar para um especialista que poderá ajudá-lo melhor. Você receberá uma resposta em breve."
            
        except Exception as e:
            logger.error(f"Erro no chatbot: {str(e)}")
            return None


class WorkflowAutomation:
    """Sistema de automação de workflows"""
    
    def __init__(self):
        self.workflow_config = getattr(settings, 'WORKFLOW_CONFIG', {})
    
    def process_ticket_automation(self, ticket):
        """Processa automações baseadas no ticket"""
        try:
            # Auto-escalação por tempo
            self._check_escalation_rules(ticket)
            
            # Atribuição automática se não tem agente
            if not ticket.agente:
                auto_assignment = AutoAssignmentEngine()
                auto_assignment.assign_ticket(ticket)
            
            # Análise de sentimento na última interação
            self._analyze_latest_interaction(ticket)
            
        except Exception as e:
            logger.error(f"Erro na automação do workflow: {str(e)}")
    
    def _check_escalation_rules(self, ticket):
        """Verifica regras de escalação por tempo"""
        if ticket.status in ['fechado', 'resolvido']:
            return
        
        escalation_levels = self.workflow_config.get('ESCALATION_LEVELS', [])
        time_since_creation = timezone.now() - ticket.criado_em
        
        for level_config in escalation_levels:
            threshold = timedelta(hours=level_config['delay_hours'])
            
            if time_since_creation > threshold:
                # Verificar se já foi escalado para este nível
                escalation_key = f'escalation_level_{level_config["level"]}'
                
                if not hasattr(ticket, escalation_key):
                    self._escalate_ticket(ticket, level_config['level'])
    
    def _escalate_ticket(self, ticket, level):
        """Escala ticket para nível superior"""
        try:
            # Atualizar prioridade se necessário
            if level >= 2 and ticket.prioridade != 'critica':
                ticket.prioridade = 'alta' if level == 2 else 'critica'
                ticket.save()
            
            # Registrar escalação
            InteracaoTicket.objects.create(
                ticket=ticket,
                usuario=None,  # Sistema
                tipo='sistema',
                conteudo=f'Ticket escalado automaticamente para nível {level} devido ao tempo de resposta.',
                publico=False
            )
            
            logger.info(f"Ticket #{ticket.numero} escalado para nível {level}")
            
        except Exception as e:
            logger.error(f"Erro ao escalar ticket: {str(e)}")
    
    def _analyze_latest_interaction(self, ticket):
        """Analisa sentimento da última interação"""
        try:
            latest_interaction = ticket.interacoes.filter(publico=True).last()
            
            if latest_interaction and latest_interaction.usuario:
                sentiment_analyzer = SentimentAnalyzer()
                sentiment = sentiment_analyzer.analyze_sentiment(latest_interaction.conteudo)
                
                # Se sentimento negativo, aumentar prioridade
                if sentiment == 'negative' and ticket.prioridade == 'baixa':
                    ticket.prioridade = 'media'
                    ticket.save()
                    
                    logger.info(f"Prioridade do ticket #{ticket.numero} aumentada devido ao sentimento negativo")
                    
        except Exception as e:
            logger.error(f"Erro na análise de sentimento: {str(e)}")


# Instâncias globais dos serviços
auto_assignment_engine = AutoAssignmentEngine()
sentiment_analyzer = SentimentAnalyzer()
chatbot_service = ChatbotService()
workflow_automation = WorkflowAutomation()
