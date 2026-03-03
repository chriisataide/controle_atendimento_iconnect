"""
Sistema de Automação de Tickets para iConnect
Implementa regras de negócio, auto-assignment e workflows automatizados
"""

import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from django.core.mail import send_mail
from django.utils import timezone

from ..models import Ticket
from .notifications import NotificationService

# Aliases para compatibilidade (modelos renomeados)
Agent = None  # Usar User do django.contrib.auth
Customer = None  # Usar Cliente de .models

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    """Tipos de trigger para automação"""

    TICKET_CREATED = "ticket_created"
    TICKET_UPDATED = "ticket_updated"
    STATUS_CHANGED = "status_changed"
    PRIORITY_CHANGED = "priority_changed"
    ASSIGNED = "assigned"
    ESCALATED = "escalated"
    SLA_WARNING = "sla_warning"
    SLA_BREACH = "sla_breach"
    CUSTOMER_REPLY = "customer_reply"
    AGENT_REPLY = "agent_reply"
    TIME_BASED = "time_based"


class ActionType(Enum):
    """Tipos de ação automatizada"""

    AUTO_ASSIGN = "auto_assign"
    CHANGE_STATUS = "change_status"
    CHANGE_PRIORITY = "change_priority"
    ESCALATE = "escalate"
    SEND_EMAIL = "send_email"
    CREATE_NOTIFICATION = "create_notification"
    ADD_TAG = "add_tag"
    SET_SLA = "set_sla"
    SCHEDULE_CALLBACK = "schedule_callback"
    CLOSE_TICKET = "close_ticket"


@dataclass
class AutomationRule:
    """Regra de automação"""

    id: str
    name: str
    description: str
    trigger_type: TriggerType
    conditions: List[Dict[str, Any]]
    actions: List[Dict[str, Any]]
    is_active: bool = True
    priority: int = 0
    created_by: str = "system"


class AutomationEngine:
    """Engine principal de automação"""

    def __init__(self):
        self.rules = []
        self.notification_service = NotificationService()
        self.load_default_rules()

    def load_default_rules(self):
        """Carrega regras padrão do sistema"""

        # Regra 1: Auto-assignment baseado em palavras-chave
        self.add_rule(
            AutomationRule(
                id="auto_assign_technical",
                name="Auto-atribuição Técnica",
                description="Atribui tickets técnicos automaticamente",
                trigger_type=TriggerType.TICKET_CREATED,
                conditions=[
                    {
                        "field": "title",
                        "operator": "contains_any",
                        "value": ["erro", "bug", "falha", "sistema", "login"],
                    },
                    {"field": "category", "operator": "equals", "value": "TECNICO"},
                ],
                actions=[
                    {"type": ActionType.AUTO_ASSIGN.value, "params": {"skill": "technical"}},
                    {"type": ActionType.SET_SLA.value, "params": {"hours": 24}},
                ],
                priority=10,
            )
        )

        # Regra 2: Escalação por SLA
        self.add_rule(
            AutomationRule(
                id="sla_escalation",
                name="Escalação por SLA",
                description="Escala tickets que violam SLA",
                trigger_type=TriggerType.SLA_BREACH,
                conditions=[{"field": "status", "operator": "in", "value": ["NOVO", "ABERTO", "EM_ANDAMENTO"]}],
                actions=[
                    {"type": ActionType.ESCALATE.value, "params": {"level": "supervisor"}},
                    {"type": ActionType.CHANGE_PRIORITY.value, "params": {"priority": "ALTA"}},
                    {
                        "type": ActionType.SEND_EMAIL.value,
                        "params": {"template": "sla_breach", "recipients": ["supervisor"]},
                    },
                ],
                priority=20,
            )
        )

        # Regra 3: Tickets de alta prioridade
        self.add_rule(
            AutomationRule(
                id="high_priority_alert",
                name="Alerta Alta Prioridade",
                description="Notificações para tickets críticos",
                trigger_type=TriggerType.TICKET_CREATED,
                conditions=[{"field": "priority", "operator": "in", "value": ["ALTA", "CRITICA"]}],
                actions=[
                    {"type": ActionType.CREATE_NOTIFICATION.value, "params": {"type": "urgent", "all_agents": True}},
                    {"type": ActionType.SET_SLA.value, "params": {"hours": 4}},
                ],
                priority=15,
            )
        )

        # Regra 4: Auto-fechamento por inatividade
        self.add_rule(
            AutomationRule(
                id="auto_close_resolved",
                name="Fechamento Automático",
                description="Fecha tickets resolvidos após 72h sem resposta",
                trigger_type=TriggerType.TIME_BASED,
                conditions=[
                    {"field": "status", "operator": "equals", "value": "RESOLVIDO"},
                    {"field": "hours_since_update", "operator": "greater_than", "value": 72},
                    {"field": "awaiting_customer", "operator": "equals", "value": True},
                ],
                actions=[
                    {"type": ActionType.CHANGE_STATUS.value, "params": {"status": "FECHADO"}},
                    {
                        "type": ActionType.SEND_EMAIL.value,
                        "params": {"template": "auto_closed", "recipients": ["customer"]},
                    },
                ],
                priority=5,
            )
        )

        # Regra 5: Detecção de spam/duplicatas
        self.add_rule(
            AutomationRule(
                id="spam_detection",
                name="Detecção de Spam",
                description="Identifica e marca possível spam",
                trigger_type=TriggerType.TICKET_CREATED,
                conditions=[
                    {"field": "similar_tickets_24h", "operator": "greater_than", "value": 3},
                    {"field": "description_length", "operator": "less_than", "value": 20},
                ],
                actions=[
                    {"type": ActionType.ADD_TAG.value, "params": {"tag": "possivel_spam"}},
                    {
                        "type": ActionType.CREATE_NOTIFICATION.value,
                        "params": {"type": "spam_alert", "supervisors": True},
                    },
                ],
                priority=25,
            )
        )

    def add_rule(self, rule: AutomationRule):
        """Adiciona nova regra de automação"""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    async def process_trigger(self, trigger_type: TriggerType, context: Dict[str, Any]):
        """Processa trigger e executa regras aplicáveis"""

        applicable_rules = [rule for rule in self.rules if rule.is_active and rule.trigger_type == trigger_type]

        for rule in applicable_rules:
            try:
                if await self._evaluate_conditions(rule.conditions, context):
                    logger.info(f"Executando regra: {rule.name}")
                    await self._execute_actions(rule.actions, context)

            except Exception as e:
                logger.error(f"Erro ao executar regra {rule.name}: {e}")

    async def _evaluate_conditions(self, conditions: List[Dict[str, Any]], context: Dict[str, Any]) -> bool:
        """Avalia se todas as condições são atendidas"""

        for condition in conditions:
            field = condition.get("field")
            operator = condition.get("operator")
            expected_value = condition.get("value")

            # Obter valor atual do contexto
            actual_value = await self._get_field_value(field, context)

            # Avaliar condição
            if not self._compare_values(actual_value, operator, expected_value):
                return False

        return True

    async def _get_field_value(self, field: str, context: Dict[str, Any]) -> Any:
        """Obtém valor de campo do contexto ou banco de dados"""

        # Valores diretos do contexto
        if field in context:
            return context[field]

        ticket = context.get("ticket")
        if not ticket:
            return None

        # Campos especiais calculados
        if field == "hours_since_update":
            if ticket.updated_at:
                delta = timezone.now() - ticket.updated_at
                return delta.total_seconds() / 3600
            return 0

        elif field == "similar_tickets_24h":
            return await self._count_similar_tickets(ticket)

        elif field == "description_length":
            return len(ticket.description) if ticket.description else 0

        elif field == "awaiting_customer":
            return await self._is_awaiting_customer(ticket)

        # Campos do modelo
        return getattr(ticket, field, None)

    def _compare_values(self, actual: Any, operator: str, expected: Any) -> bool:
        """Compara valores usando operador especificado"""

        try:
            if operator == "equals":
                return actual == expected

            elif operator == "not_equals":
                return actual != expected

            elif operator == "greater_than":
                return float(actual) > float(expected)

            elif operator == "less_than":
                return float(actual) < float(expected)

            elif operator == "greater_equal":
                return float(actual) >= float(expected)

            elif operator == "less_equal":
                return float(actual) <= float(expected)

            elif operator == "contains":
                return str(expected).lower() in str(actual).lower()

            elif operator == "contains_any":
                actual_str = str(actual).lower()
                return any(str(item).lower() in actual_str for item in expected)

            elif operator == "in":
                return actual in expected

            elif operator == "not_in":
                return actual not in expected

            elif operator == "regex":
                return bool(re.search(str(expected), str(actual), re.IGNORECASE))

            else:
                logger.warning(f"Operador desconhecido: {operator}")
                return False

        except (ValueError, TypeError) as e:
            logger.error(f"Erro ao comparar valores: {e}")
            return False

    async def _execute_actions(self, actions: List[Dict[str, Any]], context: Dict[str, Any]):
        """Executa lista de ações"""

        for action in actions:
            action_type = action.get("type")
            params = action.get("params", {})

            try:
                if action_type == ActionType.AUTO_ASSIGN.value:
                    await self._action_auto_assign(context, params)

                elif action_type == ActionType.CHANGE_STATUS.value:
                    await self._action_change_status(context, params)

                elif action_type == ActionType.CHANGE_PRIORITY.value:
                    await self._action_change_priority(context, params)

                elif action_type == ActionType.ESCALATE.value:
                    await self._action_escalate(context, params)

                elif action_type == ActionType.SEND_EMAIL.value:
                    await self._action_send_email(context, params)

                elif action_type == ActionType.CREATE_NOTIFICATION.value:
                    await self._action_create_notification(context, params)

                elif action_type == ActionType.ADD_TAG.value:
                    await self._action_add_tag(context, params)

                elif action_type == ActionType.SET_SLA.value:
                    await self._action_set_sla(context, params)

                elif action_type == ActionType.CLOSE_TICKET.value:
                    await self._action_close_ticket(context, params)

                else:
                    logger.warning(f"Tipo de ação desconhecido: {action_type}")

            except Exception as e:
                logger.error(f"Erro ao executar ação {action_type}: {e}")

    # ====================================
    # IMPLEMENTAÇÕES DE AÇÕES
    # ====================================

    async def _action_auto_assign(self, context: Dict[str, Any], params: Dict[str, Any]):
        """Atribui ticket automaticamente para melhor agente"""

        ticket = context.get("ticket")
        if not ticket or ticket.assigned_to:
            return

        skill = params.get("skill")
        agent = await self._find_best_agent(ticket, skill)

        if agent:
            from django.db import sync_to_async

            @sync_to_async
            def assign_ticket():
                ticket.assigned_to = agent
                ticket.status = "ABERTO"
                ticket.save()
                return True

            success = await assign_ticket()

            if success:
                logger.info(f"Ticket {ticket.ticket_number} atribuído para {agent.user.username}")

                # Notificar agente
                await self.notification_service.create_notification(
                    user=agent.user,
                    type="ticket_assigned",
                    title=f"Ticket #{ticket.ticket_number} atribuído",
                    message=f"Você recebeu um novo ticket: {ticket.title}",
                    url=f"/tickets/{ticket.id}/",
                )

    async def _action_change_status(self, context: Dict[str, Any], params: Dict[str, Any]):
        """Altera status do ticket"""

        ticket = context.get("ticket")
        new_status = params.get("status")

        if ticket and new_status:
            from django.db import sync_to_async

            @sync_to_async
            def update_status():
                old_status = ticket.status
                ticket.status = new_status

                if new_status == "FECHADO":
                    ticket.resolved_at = timezone.now()

                ticket.save()
                return old_status

            old_status = await update_status()
            logger.info(f"Status do ticket {ticket.ticket_number} alterado de {old_status} para {new_status}")

    async def _action_change_priority(self, context: Dict[str, Any], params: Dict[str, Any]):
        """Altera prioridade do ticket"""

        ticket = context.get("ticket")
        new_priority = params.get("priority")

        if ticket and new_priority:
            from django.db import sync_to_async

            @sync_to_async
            def update_priority():
                old_priority = ticket.priority
                ticket.priority = new_priority
                ticket.save()
                return old_priority

            old_priority = await update_priority()
            logger.info(f"Prioridade do ticket {ticket.ticket_number} alterada de {old_priority} para {new_priority}")

    async def _action_escalate(self, context: Dict[str, Any], params: Dict[str, Any]):
        """Escala ticket para nível superior"""

        ticket = context.get("ticket")
        level = params.get("level", "supervisor")

        if ticket:
            from django.db import sync_to_async

            @sync_to_async
            def escalate_ticket():
                ticket.escalated = True
                ticket.escalation_level = level
                ticket.escalated_at = timezone.now()
                ticket.save()
                return True

            await escalate_ticket()
            logger.info(f"Ticket {ticket.ticket_number} escalado para {level}")

            # Notificar supervisores
            supervisors = await self._get_supervisors()
            for supervisor in supervisors:
                await self.notification_service.create_notification(
                    user=supervisor.user,
                    type="ticket_escalated",
                    title=f"Ticket escalado: #{ticket.ticket_number}",
                    message=f"Ticket escalado: {ticket.title}",
                    url=f"/tickets/{ticket.id}/",
                )

    async def _action_send_email(self, context: Dict[str, Any], params: Dict[str, Any]):
        """Envia email automatizado"""

        ticket = context.get("ticket")
        template = params.get("template")
        recipients = params.get("recipients", [])

        if not ticket or not template:
            return

        # Determinar destinatários
        email_list = []
        for recipient in recipients:
            if recipient == "customer" and ticket.customer:
                email_list.append(ticket.customer.email)
            elif recipient == "agent" and ticket.assigned_to:
                email_list.append(ticket.assigned_to.user.email)
            elif recipient == "supervisor":
                supervisors = await self._get_supervisors()
                email_list.extend([s.user.email for s in supervisors])

        if email_list:
            # Carregar template e enviar email
            subject = f"iConnect - Ticket #{ticket.ticket_number}"

            try:
                from django.db import sync_to_async

                @sync_to_async
                def send_emails():
                    send_mail(
                        subject=subject,
                        message=f"Atualização do ticket: {ticket.title}",
                        from_email="noreply@iconnect.com",
                        recipient_list=email_list,
                        fail_silently=False,
                    )
                    return True

                await send_emails()
                logger.info(f"Email enviado para {len(email_list)} destinatários")

            except Exception as e:
                logger.error(f"Erro ao enviar email: {e}")

    async def _action_create_notification(self, context: Dict[str, Any], params: Dict[str, Any]):
        """Cria notificação no sistema"""

        ticket = context.get("ticket")
        notif_type = params.get("type", "info")
        all_agents = params.get("all_agents", False)
        supervisors = params.get("supervisors", False)

        if not ticket:
            return

        title = f"Ticket #{ticket.ticket_number}"
        message = params.get("message", f"Atualização: {ticket.title}")

        recipients = []

        if all_agents:
            agents = await self._get_all_agents()
            recipients.extend([agent.user for agent in agents])

        if supervisors:
            supervisor_list = await self._get_supervisors()
            recipients.extend([supervisor.user for supervisor in supervisor_list])

        # Criar notificações
        for user in recipients:
            await self.notification_service.create_notification(
                user=user, type=notif_type, title=title, message=message, url=f"/tickets/{ticket.id}/"
            )

    async def _action_set_sla(self, context: Dict[str, Any], params: Dict[str, Any]):
        """Define SLA para o ticket"""

        ticket = context.get("ticket")
        hours = params.get("hours", 24)

        if ticket:
            from django.db import sync_to_async

            @sync_to_async
            def set_sla():
                sla_deadline = timezone.now() + timedelta(hours=hours)
                ticket.sla_deadline = sla_deadline
                ticket.save()
                return sla_deadline

            deadline = await set_sla()
            logger.info(f"SLA definido para ticket {ticket.ticket_number}: {deadline}")

    # ====================================
    # MÉTODOS AUXILIARES
    # ====================================

    async def _find_best_agent(self, ticket: Ticket, skill: str = None) -> Optional[Agent]:
        """Encontra o melhor agente para atribuir o ticket"""

        from django.db import sync_to_async

        @sync_to_async
        def get_best_agent():
            # Agentes ativos disponíveis
            agents = Agent.objects.filter(is_active=True)

            if skill:
                # Filtrar por habilidade específica
                agents = agents.filter(skills__icontains=skill)

            # Calcular carga de trabalho
            agent_workload = []
            for agent in agents:
                current_tickets = Ticket.objects.filter(
                    assigned_to=agent, status__in=["NOVO", "ABERTO", "EM_ANDAMENTO"]
                ).count()

                agent_workload.append((agent, current_tickets))

            # Retornar agente com menor carga
            if agent_workload:
                return min(agent_workload, key=lambda x: x[1])[0]

            return None

        return await get_best_agent()

    async def _count_similar_tickets(self, ticket: Ticket) -> int:
        """Conta tickets similares nas últimas 24h"""

        from django.db import sync_to_async

        @sync_to_async
        def count_similar():
            since = timezone.now() - timedelta(hours=24)

            return Ticket.objects.filter(
                customer=ticket.customer,
                created_at__gte=since,
                title__icontains=ticket.title[:20],  # Primeiras 20 palavras
            ).count()

        return await count_similar()

    async def _is_awaiting_customer(self, ticket: Ticket) -> bool:
        """Verifica se ticket está aguardando resposta do cliente"""

        # Implementar lógica baseada no último comentário/interação
        return ticket.status == "RESOLVIDO"

    async def _get_supervisors(self) -> List[Agent]:
        """Busca lista de supervisores"""

        from django.db import sync_to_async

        @sync_to_async
        def get_supervisors():
            return list(Agent.objects.filter(is_supervisor=True, is_active=True))

        return await get_supervisors()

    async def _get_all_agents(self) -> List[Agent]:
        """Busca todos os agentes ativos"""

        from django.db import sync_to_async

        @sync_to_async
        def get_agents():
            return list(Agent.objects.filter(is_active=True))

        return await get_agents()


# ====================================
# SCHEDULER PARA AUTOMAÇÕES BASEADAS EM TEMPO
# ====================================


class AutomationScheduler:
    """Agendador para automações baseadas em tempo"""

    def __init__(self):
        self.automation_engine = AutomationEngine()

    async def run_periodic_checks(self):
        """Executa verificações periódicas"""

        logger.info("Executando verificações de automação periódicas")

        # Verificar SLA
        await self._check_sla_violations()

        # Verificar tickets para fechamento automático
        await self._check_auto_close()

        # Verificar escalonamentos por tempo
        await self._check_time_based_escalations()

    async def _check_sla_violations(self):
        """Verifica violações de SLA"""

        from django.db import sync_to_async

        @sync_to_async
        def get_sla_violations():
            now = timezone.now()
            return list(
                Ticket.objects.filter(
                    sla_deadline__lt=now, status__in=["NOVO", "ABERTO", "EM_ANDAMENTO"], sla_breached=False
                )
            )

        violations = await get_sla_violations()

        for ticket in violations:
            # Marcar como violado
            from django.db import sync_to_async

            @sync_to_async
            def mark_breached():
                ticket.sla_breached = True
                ticket.save()

            await mark_breached()

            # Triggerar automação
            await self.automation_engine.process_trigger(TriggerType.SLA_BREACH, {"ticket": ticket})

    async def _check_auto_close(self):
        """Verifica tickets para fechamento automático"""

        from django.db import sync_to_async

        @sync_to_async
        def get_auto_close_candidates():
            cutoff = timezone.now() - timedelta(hours=72)
            return list(Ticket.objects.filter(status="RESOLVIDO", updated_at__lt=cutoff))

        candidates = await get_auto_close_candidates()

        for ticket in candidates:
            await self.automation_engine.process_trigger(TriggerType.TIME_BASED, {"ticket": ticket})


# Instâncias globais
automation_engine = AutomationEngine()
automation_scheduler = AutomationScheduler()
