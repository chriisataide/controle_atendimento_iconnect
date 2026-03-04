"""
SLA Calculator Service
Calcula prazos de SLA considerando horário comercial, feriados e finais de semana
"""

from datetime import datetime, time, timedelta
from typing import Optional, Tuple

from django.conf import settings
from django.utils import timezone

from ..models import SLAHistory, SLAPolicy, Ticket


class SLACalculator:
    """Classe para cálculos de SLA"""

    def __init__(self):
        self.holidays = self._get_holidays()

    def _get_holidays(self) -> list:
        """Retorna lista de feriados configurados"""
        # Pode ser configurado via settings ou banco de dados
        return getattr(settings, "HOLIDAYS", [])

    def is_business_day(self, dt: datetime) -> bool:
        """Verifica se é dia útil"""
        return dt.weekday() < 5  # 0-4 = segunda a sexta

    def is_holiday(self, dt: datetime) -> bool:
        """Verifica se é feriado"""
        return dt.date() in self.holidays

    def is_business_hour(self, dt: datetime, start_hour: time, end_hour: time) -> bool:
        """Verifica se está no horário comercial"""
        current_time = dt.time()
        return start_hour <= current_time <= end_hour

    def get_sla_policy(self, ticket: Ticket) -> Optional[SLAPolicy]:
        """Obtém a política de SLA aplicável ao ticket"""
        try:
            # Busca política específica por categoria e prioridade
            if ticket.categoria:
                policy = SLAPolicy.objects.filter(
                    categoria=ticket.categoria, prioridade=ticket.prioridade, is_active=True
                ).first()
                if policy:
                    return policy

            # Busca política por prioridade (sem categoria específica)
            policy = SLAPolicy.objects.filter(
                categoria__isnull=True, prioridade=ticket.prioridade, is_active=True
            ).first()

            return policy
        except Exception:
            return None

    def calculate_deadline(self, start_time: datetime, minutes: int, policy: SLAPolicy) -> datetime:
        """
        Calcula o prazo final considerando horário comercial
        """
        if not policy.business_hours_only:
            # SLA 24/7 - simplesmente adiciona os minutos
            return start_time + timedelta(minutes=minutes)

        current_time = start_time
        remaining_minutes = minutes

        while remaining_minutes > 0:
            # Se não é dia útil ou é feriado, pula para o próximo dia útil
            if not self.is_business_day(current_time) or self.is_holiday(current_time):
                current_time = self._next_business_day(current_time, policy.start_hour)
                continue

            # Se está fora do horário comercial, pula para o início do próximo dia útil
            if not self.is_business_hour(current_time, policy.start_hour, policy.end_hour):
                if current_time.time() < policy.start_hour:
                    # Antes do expediente - vai para o início
                    current_time = current_time.replace(
                        hour=policy.start_hour.hour, minute=policy.start_hour.minute, second=0, microsecond=0
                    )
                else:
                    # Depois do expediente - vai para o próximo dia útil
                    current_time = self._next_business_day(current_time, policy.start_hour)
                continue

            # Calcula quanto tempo resta no dia atual
            end_of_day = current_time.replace(
                hour=policy.end_hour.hour, minute=policy.end_hour.minute, second=0, microsecond=0
            )

            minutes_left_today = int((end_of_day - current_time).total_seconds() / 60)

            if remaining_minutes <= minutes_left_today:
                # Termina hoje
                return current_time + timedelta(minutes=remaining_minutes)
            else:
                # Usa todo o tempo de hoje e continua amanhã
                remaining_minutes -= minutes_left_today
                current_time = self._next_business_day(current_time, policy.start_hour)

        return current_time

    def _next_business_day(self, dt: datetime, start_hour: time) -> datetime:
        """Retorna o próximo dia útil no horário de início"""
        next_day = dt + timedelta(days=1)

        while not self.is_business_day(next_day) or self.is_holiday(next_day):
            next_day += timedelta(days=1)

        return next_day.replace(hour=start_hour.hour, minute=start_hour.minute, second=0, microsecond=0)

    def calculate_sla_deadlines(self, ticket: Ticket) -> Optional[Tuple[datetime, datetime, datetime]]:
        """
        Calcula todos os prazos de SLA para um ticket
        Retorna: (first_response_deadline, resolution_deadline, escalation_deadline)
        """
        policy = self.get_sla_policy(ticket)
        if not policy:
            return None

        start_time = ticket.criado_em

        # Calcula prazo de primeira resposta
        first_response_deadline = self.calculate_deadline(start_time, policy.first_response_time, policy)

        # Calcula prazo de resolução
        resolution_deadline = self.calculate_deadline(start_time, policy.resolution_time, policy)

        # Calcula prazo de escalação
        escalation_deadline = self.calculate_deadline(start_time, policy.escalation_time, policy)

        return first_response_deadline, resolution_deadline, escalation_deadline

    def create_sla_history(self, ticket: Ticket) -> Optional[SLAHistory]:
        """Cria o histórico de SLA para um ticket"""
        deadlines = self.calculate_sla_deadlines(ticket)
        if not deadlines:
            return None

        policy = self.get_sla_policy(ticket)
        first_response_deadline, resolution_deadline, escalation_deadline = deadlines

        sla_history = SLAHistory.objects.create(
            ticket=ticket,
            sla_policy=policy,
            first_response_deadline=first_response_deadline,
            resolution_deadline=resolution_deadline,
            escalation_deadline=escalation_deadline,
            status="on_track",
        )

        # Atualiza o ticket com os prazos
        ticket.sla_policy = policy
        ticket.sla_deadline = first_response_deadline
        ticket.sla_resolution_deadline = resolution_deadline
        ticket.save(update_fields=["sla_policy", "sla_deadline", "sla_resolution_deadline"])

        return sla_history

    def get_sla_status(self, sla_history: SLAHistory) -> str:
        """Determina o status atual do SLA"""
        now = timezone.now()
        ticket = sla_history.ticket

        # Se o ticket já foi resolvido
        if ticket.status in ["resolvido", "fechado"]:
            return "completed"

        # Se já foi escalado
        if sla_history.escalated:
            return "escalated"

        # Verifica violações
        if now > sla_history.resolution_deadline:
            return "breached"

        if now > sla_history.first_response_deadline and not ticket.first_response_at:
            return "breached"

        # Verifica alertas (80% do tempo decorrido)
        warning_threshold = sla_history.sla_policy.warning_percentage / 100.0

        # Para primeira resposta
        if not ticket.first_response_at:
            total_time = (sla_history.first_response_deadline - ticket.criado_em).total_seconds()
            elapsed_time = (now - ticket.criado_em).total_seconds()
            if elapsed_time / total_time >= warning_threshold:
                return "warning"

        # Para resolução
        total_time = (sla_history.resolution_deadline - ticket.criado_em).total_seconds()
        elapsed_time = (now - ticket.criado_em).total_seconds()
        if elapsed_time / total_time >= warning_threshold:
            return "warning"

        return "on_track"

    def calculate_sla_metrics(self, sla_history: SLAHistory) -> dict:
        """Calcula métricas de performance do SLA"""
        ticket = sla_history.ticket
        now = timezone.now()

        metrics = {
            "first_response_time": None,
            "resolution_time": None,
            "first_response_sla_met": None,
            "resolution_sla_met": None,
            "overall_sla_compliance": None,
            "time_to_breach": None,  # tempo restante até violação
            "sla_percentage_elapsed": 0,  # % do tempo de SLA já transcorrido
        }

        # Tempo de primeira resposta
        if ticket.first_response_at:
            metrics["first_response_time"] = ticket.first_response_at - ticket.criado_em
            metrics["first_response_sla_met"] = ticket.first_response_at <= sla_history.first_response_deadline

        # Tempo de resolução
        if ticket.resolvido_em:
            metrics["resolution_time"] = ticket.resolvido_em - ticket.criado_em
            metrics["resolution_sla_met"] = ticket.resolvido_em <= sla_history.resolution_deadline

        # SLA geral
        if metrics["first_response_sla_met"] is not None and metrics["resolution_sla_met"] is not None:
            metrics["overall_sla_compliance"] = metrics["first_response_sla_met"] and metrics["resolution_sla_met"]

        # Tempo até violação
        if ticket.status not in ["resolvido", "fechado"]:
            if not ticket.first_response_at:
                metrics["time_to_breach"] = max(timedelta(0), sla_history.first_response_deadline - now)
            else:
                metrics["time_to_breach"] = max(timedelta(0), sla_history.resolution_deadline - now)

        # Percentual transcorrido
        if ticket.status not in ["resolvido", "fechado"]:
            if not ticket.first_response_at:
                total_time = (sla_history.first_response_deadline - ticket.criado_em).total_seconds()
                elapsed_time = (now - ticket.criado_em).total_seconds()
            else:
                total_time = (sla_history.resolution_deadline - ticket.criado_em).total_seconds()
                elapsed_time = (now - ticket.criado_em).total_seconds()

            metrics["sla_percentage_elapsed"] = min(100, (elapsed_time / total_time) * 100)

        return metrics


# Instância global do calculador
sla_calculator = SLACalculator()
