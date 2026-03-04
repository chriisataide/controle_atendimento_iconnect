"""
Ticket Service - Centralized business logic for tickets
"""

import logging
from typing import Dict, List, Optional

from django.db.models import Avg, Count, Q
from django.utils import timezone

from ..models import PerfilAgente, Ticket
from .ml_engine import ml_predictor
from .notifications import NotificationService

logger = logging.getLogger(__name__)


class TicketService:
    """Service para gerenciar operações de tickets"""

    def __init__(self):
        self.notification_service = NotificationService()

    def create_ticket(self, ticket_data: Dict, user=None) -> Ticket:
        """
        Criar novo ticket com lógica de negócio
        """
        try:
            # Predição ML para prioridade e categoria
            if "titulo" in ticket_data and "descricao" in ticket_data:
                predictions = ml_predictor.predict_ticket_properties(
                    ticket_data["titulo"], ticket_data["descricao"], ticket_data.get("cliente_id")
                )

                if predictions:
                    if not ticket_data.get("prioridade"):
                        ticket_data["prioridade"] = predictions.get("prioridade", "media")
                    if not ticket_data.get("categoria"):
                        ticket_data["categoria"] = predictions.get("categoria")

            # Auto-assignment se não especificado
            if not ticket_data.get("agente") and ticket_data.get("categoria"):
                agente = self._auto_assign_agent(ticket_data["categoria"])
                if agente:
                    ticket_data["agente"] = agente

            # Criar ticket
            ticket = Ticket.objects.create(**ticket_data)

            # Notificações
            self._send_creation_notifications(ticket)

            logger.info(f"Ticket {ticket.id} criado com sucesso")
            return ticket

        except Exception as e:
            logger.error(f"Erro ao criar ticket: {str(e)}")
            raise

    def update_ticket_status(self, ticket_id: int, new_status: str, user=None) -> Ticket:
        """
        Atualizar status do ticket com validações
        """
        try:
            ticket = Ticket.objects.get(id=ticket_id)
            old_status = ticket.status

            # Validações de negócio
            self._validate_status_change(ticket, old_status, new_status, user)

            ticket.status = new_status
            ticket.atualizado_em = timezone.now()

            # Timestamps específicos
            if new_status == "resolvido" and not ticket.resolvido_em:
                ticket.resolvido_em = timezone.now()
            elif new_status == "fechado" and not ticket.fechado_em:
                ticket.fechado_em = timezone.now()

            ticket.save()

            # Notificações
            self._send_status_change_notifications(ticket, old_status, new_status)

            logger.info(f"Ticket {ticket.id} status alterado de {old_status} para {new_status}")
            return ticket

        except Exception as e:
            logger.error(f"Erro ao atualizar status do ticket {ticket_id}: {str(e)}")
            raise

    def get_dashboard_stats(self, user=None) -> Dict:
        """
        Obter estatísticas do dashboard
        """
        base_query = Ticket.objects.all()

        # Filtrar por agente se não for admin
        if user and not user.is_staff:
            base_query = base_query.filter(agente=user)

        stats = base_query.aggregate(
            total=Count("id"),
            abertos=Count("id", filter=Q(status="aberto")),
            em_andamento=Count("id", filter=Q(status="em_andamento")),
            resolvidos=Count("id", filter=Q(status="resolvido")),
            fechados=Count("id", filter=Q(status="fechado")),
            alta_prioridade=Count("id", filter=Q(prioridade="alta")),
            tempo_medio_resolucao=Avg("resolution_time"),
        )

        return stats

    def get_tickets_with_filters(self, filters: Dict, user=None) -> List[Ticket]:
        """
        Buscar tickets com filtros otimizados
        """
        queryset = Ticket.objects.select_related("cliente", "agente", "categoria", "sla_policy").prefetch_related(
            "interacoes", "anexos"
        )

        # Aplicar filtros
        if filters.get("status"):
            queryset = queryset.filter(status=filters["status"])

        if filters.get("prioridade"):
            queryset = queryset.filter(prioridade=filters["prioridade"])

        if filters.get("categoria"):
            queryset = queryset.filter(categoria=filters["categoria"])

        if filters.get("search"):
            search = filters["search"]
            queryset = queryset.filter(
                Q(titulo__icontains=search) | Q(descricao__icontains=search) | Q(cliente__nome__icontains=search)
            )

        # Filtrar por usuário se não for admin
        if user and not user.is_staff:
            queryset = queryset.filter(agente=user)

        return queryset.order_by("-criado_em")

    def _auto_assign_agent(self, categoria: str) -> Optional[PerfilAgente]:
        """
        Auto-assignment de agente baseado na categoria
        """
        try:
            # Buscar agentes disponíveis com menor carga de trabalho
            agentes = (
                PerfilAgente.objects.filter(status="online", especialidades__nome__icontains=categoria)
                .annotate(
                    ticket_count=Count(
                        "user__assigned_tickets",
                        filter=Q(user__assigned_tickets__status__in=["aberto", "em_andamento"]),
                    )
                )
                .order_by("ticket_count")
            )

            return agentes.first()

        except Exception as e:
            logger.warning(f"Erro no auto-assignment: {str(e)}")
            return None

    def _validate_status_change(self, ticket: Ticket, old_status: str, new_status: str, user):
        """
        Validar mudança de status
        """
        # Regras de negócio para mudanças de status
        valid_transitions = {
            "aberto": ["em_andamento", "aguardando_cliente", "resolvido"],
            "em_andamento": ["aguardando_cliente", "resolvido", "aberto"],
            "aguardando_cliente": ["em_andamento", "resolvido"],
            "resolvido": ["fechado", "em_andamento"],  # Pode reabrir
            "fechado": [],  # Ticket fechado não pode ser alterado
        }

        if old_status == "fechado":
            raise ValueError("Ticket fechado não pode ter status alterado")

        if new_status not in valid_transitions.get(old_status, []):
            raise ValueError(f"Transição de {old_status} para {new_status} não é permitida")

    def _send_creation_notifications(self, ticket: Ticket):
        """
        Enviar notificações de criação de ticket
        """
        try:
            # Notificar agente atribuído
            if ticket.agente:
                self.notification_service.send_notification(
                    user=ticket.agente,
                    title="Novo Ticket Atribuído",
                    message=f"Ticket #{ticket.id}: {ticket.titulo}",
                    notification_type="ticket_assigned",
                )

            # Notificar cliente via email
            if ticket.cliente and ticket.cliente.email:
                self.notification_service.send_notification(
                    user=None,
                    title="Ticket Criado",
                    message=f"Seu ticket #{ticket.id} ({ticket.titulo}) foi registrado com sucesso.",
                    notification_type="ticket_created",
                    email=ticket.cliente.email,
                )

        except Exception as e:
            logger.error(f"Erro ao enviar notificações: {str(e)}")

    def _send_status_change_notifications(self, ticket: Ticket, old_status: str, new_status: str):
        """
        Enviar notificações de mudança de status
        """
        try:
            # Notificar cliente
            if ticket.cliente:
                status_messages = {
                    "em_andamento": f"Seu ticket #{ticket.id} está sendo atendido",
                    "resolvido": f"Seu ticket #{ticket.id} foi resolvido",
                    "fechado": f"Seu ticket #{ticket.id} foi finalizado",
                }

                if new_status in status_messages:
                    self.notification_service.send_notification(
                        user=None,
                        title="Atualização de Ticket",
                        message=status_messages[new_status],
                        notification_type="status_change",
                        email=ticket.cliente.email if ticket.cliente and ticket.cliente.email else None,
                    )

            # Notificar supervisores em casos específicos
            if new_status == "resolvido" and ticket.prioridade == "alta":
                from django.contrib.auth.models import User

                supervisors = User.objects.filter(is_staff=True, is_superuser=True, is_active=True)
                for sup in supervisors:
                    self.notification_service.send_notification(
                        user=sup,
                        title="Ticket Alta Prioridade Resolvido",
                        message=f"Ticket #{ticket.id} (prioridade alta) foi resolvido.",
                        notification_type="supervisor_alert",
                    )

        except Exception as e:
            logger.error(f"Erro ao enviar notificações de status: {str(e)}")


# Instância global do service
ticket_service = TicketService()
