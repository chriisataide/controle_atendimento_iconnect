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
            
            else:
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
