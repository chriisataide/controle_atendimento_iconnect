"""
Analytics Service - Advanced analytics and reporting
"""

import logging
from datetime import timedelta
from typing import Dict, List, Optional

from django.db.models import Avg, Count, F, Q
from django.db.models.functions import ExtractHour, TruncDate, TruncMonth, TruncWeek
from django.utils import timezone

from ..models import Cliente, InteracaoTicket, PerfilAgente, Ticket

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service para analytics avançadas"""

    def get_performance_metrics(self, date_range: Optional[int] = 30) -> Dict:
        """
        Obter métricas de performance do sistema
        """
        end_date = timezone.now()
        start_date = end_date - timedelta(days=date_range)

        tickets = Ticket.objects.filter(criado_em__range=[start_date, end_date])

        metrics = {
            "total_tickets": tickets.count(),
            "resolved_tickets": tickets.filter(status="resolvido").count(),
            "avg_resolution_time": self._calculate_avg_resolution_time(tickets),
            "sla_compliance_rate": self._calculate_sla_compliance(tickets),
            "customer_satisfaction": self._calculate_satisfaction_score(tickets),
            "agent_utilization": self._calculate_agent_utilization(start_date, end_date),
            "first_response_time": self._calculate_first_response_time(tickets),
            "escalation_rate": self._calculate_escalation_rate(tickets),
        }

        return metrics

    def get_trend_analysis(self, period: str = "daily", days: int = 30) -> Dict:
        """
        Análise de tendências por período
        """
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        if period == "daily":
            truncate_func = TruncDate
        elif period == "weekly":
            truncate_func = TruncWeek
        else:
            truncate_func = TruncMonth

        ticket_trends = (
            Ticket.objects.filter(criado_em__range=[start_date, end_date])
            .annotate(period=truncate_func("criado_em"))
            .values("period")
            .annotate(
                total=Count("id"),
                resolved=Count("id", filter=Q(status="resolvido")),
                high_priority=Count("id", filter=Q(prioridade="alta")),
            )
            .order_by("period")
        )

        # Tendências de satisfação
        satisfaction_trends = self._get_satisfaction_trends(start_date, end_date, truncate_func)

        return {
            "ticket_trends": list(ticket_trends),
            "satisfaction_trends": satisfaction_trends,
            "period": period,
            "date_range": {"start": start_date, "end": end_date},
        }

    def get_agent_performance(self, agent_id: Optional[int] = None) -> Dict:
        """
        Análise de performance por agente
        """
        agents_query = PerfilAgente.objects.select_related("user")

        if agent_id:
            agents_query = agents_query.filter(id=agent_id)

        agent_stats = []

        for agent in agents_query:
            tickets = Ticket.objects.filter(agente=agent.user)

            stats = {
                "agent_id": agent.id,
                "agent_name": agent.user.get_full_name() or agent.user.username,
                "total_tickets": tickets.count(),
                "resolved_tickets": tickets.filter(status="resolvido").count(),
                "avg_resolution_time": self._calculate_avg_resolution_time(tickets),
                "customer_satisfaction": self._calculate_satisfaction_score(tickets),
                "sla_compliance": self._calculate_sla_compliance(tickets),
                "workload_distribution": self._get_workload_distribution(agent.user),
            }

            # Calcular taxa de resolução
            if stats["total_tickets"] > 0:
                stats["resolution_rate"] = (stats["resolved_tickets"] / stats["total_tickets"]) * 100
            else:
                stats["resolution_rate"] = 0

            agent_stats.append(stats)

        return {"agent_stats": agent_stats, "team_average": self._calculate_team_averages(agent_stats)}

    def get_customer_insights(self, customer_id: Optional[int] = None) -> Dict:
        """
        Insights sobre clientes
        """
        customers_query = Cliente.objects.all()

        if customer_id:
            customers_query = customers_query.filter(id=customer_id)

        customer_insights = []

        for customer in customers_query:
            tickets = Ticket.objects.filter(cliente=customer)

            insights = {
                "customer_id": customer.id,
                "customer_name": customer.nome,
                "total_tickets": tickets.count(),
                "avg_tickets_per_month": self._calculate_monthly_ticket_average(tickets),
                "most_common_issues": self._get_common_issues(tickets),
                "satisfaction_score": self._calculate_satisfaction_score(tickets),
                "escalation_history": tickets.filter(is_escalated=True).count(),
                "preferred_contact_time": self._analyze_contact_patterns(tickets),
            }

            customer_insights.append(insights)

        return {"customer_insights": customer_insights, "total_customers": customers_query.count()}

    def get_category_analysis(self) -> Dict:
        """
        Análise por categoria de tickets
        """
        category_stats = (
            Ticket.objects.values("categoria__nome")
            .annotate(
                total=Count("id"),
                resolved=Count("id", filter=Q(status="resolvido")),
                avg_resolution_time=Avg(F("resolvido_em") - F("criado_em"), filter=Q(resolvido_em__isnull=False)),
                high_priority_count=Count("id", filter=Q(prioridade="alta")),
                escalation_count=Count("id", filter=Q(is_escalated=True)),
            )
            .order_by("-total")
        )

        # Calcular percentuais
        total_tickets = Ticket.objects.count()
        for stat in category_stats:
            if total_tickets > 0:
                stat["percentage"] = (stat["total"] / total_tickets) * 100
                stat["resolution_rate"] = (stat["resolved"] / stat["total"]) * 100 if stat["total"] > 0 else 0
            else:
                stat["percentage"] = 0
                stat["resolution_rate"] = 0

        return {"category_stats": list(category_stats), "total_categories": len(category_stats)}

    def _calculate_avg_resolution_time(self, tickets) -> Optional[float]:
        """Calcular tempo médio de resolução em horas"""
        resolved_tickets = tickets.filter(resolvido_em__isnull=False, criado_em__isnull=False)

        if not resolved_tickets.exists():
            return None

        total_time = 0
        count = 0

        for ticket in resolved_tickets:
            resolution_time = ticket.resolvido_em - ticket.criado_em
            total_time += resolution_time.total_seconds()
            count += 1

        return (total_time / count) / 3600 if count > 0 else None  # Converter para horas

    def _calculate_sla_compliance(self, tickets) -> float:
        """Calcular taxa de compliance com SLA"""
        sla_tickets = tickets.filter(sla_deadline__isnull=False)

        if not sla_tickets.exists():
            return 0.0

        compliant = sla_tickets.filter(resolvido_em__lte=F("sla_deadline")).count()

        return (compliant / sla_tickets.count()) * 100

    def _calculate_satisfaction_score(self, tickets) -> Optional[float]:
        """Calcular score médio de satisfação"""
        from .models import AvaliacaoSatisfacao

        avg = AvaliacaoSatisfacao.objects.filter(ticket__in=tickets).aggregate(avg=Avg("nota"))["avg"]
        return float(avg) if avg is not None else None

    def _calculate_agent_utilization(self, start_date, end_date) -> Dict:
        """Calcular utilização dos agentes"""
        agents = PerfilAgente.objects.filter(user__is_active=True)
        utilization = {}

        for agent in agents:
            total_tickets = Ticket.objects.filter(agente=agent.user, criado_em__range=[start_date, end_date]).count()

            utilization[agent.user.username] = {
                "total_tickets": total_tickets,
                "avg_daily_tickets": total_tickets / max(1, (end_date - start_date).days),
            }

        return utilization

    def _calculate_first_response_time(self, tickets) -> Optional[float]:
        """Calcular tempo médio de primeira resposta"""
        total_time = 0
        count = 0

        for ticket in tickets:
            first_response = (
                InteracaoTicket.objects.filter(ticket=ticket, tipo="resposta").order_by("criado_em").first()
            )

            if first_response:
                response_time = first_response.criado_em - ticket.criado_em
                total_time += response_time.total_seconds()
                count += 1

        return (total_time / count) / 3600 if count > 0 else None

    def _calculate_escalation_rate(self, tickets) -> float:
        """Calcular taxa de escalação"""
        total = tickets.count()
        escalated = tickets.filter(is_escalated=True).count()

        return (escalated / total) * 100 if total > 0 else 0

    def _get_satisfaction_trends(self, start_date, end_date, truncate_func) -> List:
        """Obter tendências de satisfação"""
        from .models import AvaliacaoSatisfacao

        return list(
            AvaliacaoSatisfacao.objects.filter(criado_em__range=[start_date, end_date])
            .annotate(period=truncate_func("criado_em"))
            .values("period")
            .annotate(avg_score=Avg("nota"), count=Count("id"))
            .order_by("period")
        )

    def _calculate_team_averages(self, agent_stats: List[Dict]) -> Dict:
        """Calcular médias da equipe"""
        if not agent_stats:
            return {}

        total_agents = len(agent_stats)

        return {
            "avg_resolution_rate": sum(s["resolution_rate"] for s in agent_stats) / total_agents,
            "avg_tickets_per_agent": sum(s["total_tickets"] for s in agent_stats) / total_agents,
            "avg_sla_compliance": sum(s["sla_compliance"] for s in agent_stats if s["sla_compliance"]) / total_agents,
        }

    def _calculate_monthly_ticket_average(self, tickets) -> float:
        """Calcular média mensal de tickets"""
        if not tickets.exists():
            return 0

        first_ticket = tickets.order_by("criado_em").first()
        if not first_ticket:
            return 0

        months_active = max(1, (timezone.now() - first_ticket.criado_em).days / 30)
        return tickets.count() / months_active

    def _get_common_issues(self, tickets) -> List[Dict]:
        """Obter problemas mais comuns"""
        return list(tickets.values("categoria__nome").annotate(count=Count("id")).order_by("-count")[:5])

    def _analyze_contact_patterns(self, tickets) -> Dict:
        """Analisar padrões de contato"""
        # Análise por hora do dia (ORM puro, sem .extra())
        hour_patterns = (
            tickets.annotate(hour=ExtractHour("criado_em"))
            .values("hour")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        most_common_hour = hour_patterns.first()

        return {
            "preferred_hour": most_common_hour["hour"] if most_common_hour else None,
            "hour_distribution": list(hour_patterns),
        }

    def _get_workload_distribution(self, agent) -> Dict:
        """Obter distribuição da carga de trabalho do agente"""
        tickets = Ticket.objects.filter(agente=agent)

        return {
            "by_priority": list(tickets.values("prioridade").annotate(count=Count("id"))),
            "by_status": list(tickets.values("status").annotate(count=Count("id"))),
            "by_category": list(tickets.values("categoria__nome").annotate(count=Count("id"))),
        }


# Instância global do service
analytics_service = AnalyticsService()
