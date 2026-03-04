"""
Sistema de Relatórios Avançados para iConnect
Gera relatórios detalhados e análises de performance
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from io import BytesIO
from typing import Any, Dict

import pandas as pd
from django.contrib.auth.models import User as Agent
from django.db.models import Avg, Count, F, Q
from django.db.models.functions import TruncDate, TruncWeek
from django.utils import timezone

from ..models import Cliente, Ticket

# Alias para compatibilidade
Customer = Cliente

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Tipos de relatório disponíveis"""

    PERFORMANCE_AGENT = "performance_agent"
    TICKETS_SUMMARY = "tickets_summary"
    SLA_ANALYSIS = "sla_analysis"
    CUSTOMER_SATISFACTION = "customer_satisfaction"
    WORKLOAD_DISTRIBUTION = "workload_distribution"
    RESPONSE_TIME_ANALYSIS = "response_time_analysis"
    ESCALATION_REPORT = "escalation_report"
    TREND_ANALYSIS = "trend_analysis"
    PRODUCTIVITY_REPORT = "productivity_report"
    CUSTOMER_BEHAVIOR = "customer_behavior"


class ReportFormat(Enum):
    """Formatos de exportação"""

    JSON = "json"
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"


@dataclass
class ReportConfig:
    """Configuração de relatório"""

    report_type: ReportType
    start_date: datetime
    end_date: datetime
    filters: Dict[str, Any] = None
    format: ReportFormat = ReportFormat.JSON
    include_charts: bool = True
    group_by: str = None


class AdvancedReportsService:
    """Serviço de relatórios avançados"""

    def __init__(self):
        self.report_generators = {
            ReportType.PERFORMANCE_AGENT: self._generate_agent_performance,
            ReportType.TICKETS_SUMMARY: self._generate_tickets_summary,
            ReportType.SLA_ANALYSIS: self._generate_sla_analysis,
            ReportType.CUSTOMER_SATISFACTION: self._generate_satisfaction_report,
            ReportType.WORKLOAD_DISTRIBUTION: self._generate_workload_report,
            ReportType.RESPONSE_TIME_ANALYSIS: self._generate_response_time_report,
            ReportType.ESCALATION_REPORT: self._generate_escalation_report,
            ReportType.TREND_ANALYSIS: self._generate_trend_analysis,
            ReportType.PRODUCTIVITY_REPORT: self._generate_productivity_report,
            ReportType.CUSTOMER_BEHAVIOR: self._generate_customer_behavior,
        }

    async def generate_report(self, config: ReportConfig) -> Dict[str, Any]:
        """Gera relatório baseado na configuração"""

        try:
            generator = self.report_generators.get(config.report_type)
            if not generator:
                raise ValueError(f"Tipo de relatório não suportado: {config.report_type}")

            # Gerar dados do relatório
            report_data = await generator(config)

            # Adicionar metadados
            report_data["metadata"] = {
                "report_type": config.report_type.value,
                "period": {"start": config.start_date.isoformat(), "end": config.end_date.isoformat()},
                "filters": config.filters or {},
                "generated_at": timezone.now().isoformat(),
                "total_records": report_data.get("summary", {}).get("total_records", 0),
            }

            return report_data

        except Exception as e:
            logger.error(f"Erro ao gerar relatório: {e}")
            raise

    # ====================================
    # GERADORES DE RELATÓRIOS ESPECÍFICOS
    # ====================================

    async def _generate_agent_performance(self, config: ReportConfig) -> Dict[str, Any]:
        """Relatório de performance dos agentes"""

        from django.db import sync_to_async

        @sync_to_async
        def get_agent_stats():
            # Query base com filtros de data
            tickets = Ticket.objects.filter(created_at__range=[config.start_date, config.end_date])

            if config.filters:
                if "agent_ids" in config.filters:
                    tickets = tickets.filter(assigned_to_id__in=config.filters["agent_ids"])
                if "status" in config.filters:
                    tickets = tickets.filter(status__in=config.filters["status"])
                if "priority" in config.filters:
                    tickets = tickets.filter(priority__in=config.filters["priority"])

            # Estatísticas por agente
            agent_stats = []
            agents = Agent.objects.filter(is_active=True)

            for agent in agents:
                agent_tickets = tickets.filter(assigned_to=agent)

                resolved_tickets = agent_tickets.filter(status="FECHADO")
                total_tickets = agent_tickets.count()

                # Calcular métricas
                resolution_rate = (resolved_tickets.count() / total_tickets * 100) if total_tickets > 0 else 0

                # Tempo médio de resolução
                avg_resolution_time = 0
                if resolved_tickets.exists():
                    resolution_times = []
                    for ticket in resolved_tickets:
                        if ticket.resolved_at and ticket.created_at:
                            resolution_time = (ticket.resolved_at - ticket.created_at).total_seconds() / 3600
                            resolution_times.append(resolution_time)

                    if resolution_times:
                        avg_resolution_time = sum(resolution_times) / len(resolution_times)

                # Tempo médio de primeira resposta
                avg_first_response = 0
                first_response_tickets = agent_tickets.filter(first_response_at__isnull=False)
                if first_response_tickets.exists():
                    response_times = []
                    for ticket in first_response_tickets:
                        response_time = (ticket.first_response_at - ticket.created_at).total_seconds() / 3600
                        response_times.append(response_time)

                    if response_times:
                        avg_first_response = sum(response_times) / len(response_times)

                # Satisfação do cliente
                satisfaction_tickets = agent_tickets.exclude(customer_satisfaction__isnull=True)
                avg_satisfaction = 0
                if satisfaction_tickets.exists():
                    avg_satisfaction = satisfaction_tickets.aggregate(avg=Avg("customer_satisfaction"))["avg"] or 0

                # Tickets por prioridade
                priority_breakdown = {
                    "BAIXA": agent_tickets.filter(priority="BAIXA").count(),
                    "MEDIA": agent_tickets.filter(priority="MEDIA").count(),
                    "ALTA": agent_tickets.filter(priority="ALTA").count(),
                    "CRITICA": agent_tickets.filter(priority="CRITICA").count(),
                }

                agent_stats.append(
                    {
                        "agent_id": agent.id,
                        "agent_name": agent.user.get_full_name() or agent.user.username,
                        "agent_email": agent.user.email,
                        "total_tickets": total_tickets,
                        "resolved_tickets": resolved_tickets.count(),
                        "pending_tickets": agent_tickets.filter(status__in=["NOVO", "ABERTO", "EM_ANDAMENTO"]).count(),
                        "resolution_rate": round(resolution_rate, 2),
                        "avg_resolution_time_hours": round(avg_resolution_time, 2),
                        "avg_first_response_hours": round(avg_first_response, 2),
                        "avg_customer_satisfaction": round(avg_satisfaction, 2),
                        "escalated_tickets": agent_tickets.filter(escalated=True).count(),
                        "priority_breakdown": priority_breakdown,
                        "sla_compliance": self._calculate_sla_compliance(agent_tickets),
                    }
                )

            return agent_stats

        agent_stats = await get_agent_stats()

        # Calcular estatísticas gerais
        total_tickets = sum(stat["total_tickets"] for stat in agent_stats)
        total_resolved = sum(stat["resolved_tickets"] for stat in agent_stats)
        overall_resolution_rate = (total_resolved / total_tickets * 100) if total_tickets > 0 else 0

        # Rankings
        top_performers = sorted(agent_stats, key=lambda x: x["resolution_rate"], reverse=True)[:5]
        fastest_resolvers = sorted(
            [s for s in agent_stats if s["avg_resolution_time_hours"] > 0], key=lambda x: x["avg_resolution_time_hours"]
        )[:5]

        return {
            "summary": {
                "total_agents": len(agent_stats),
                "total_tickets": total_tickets,
                "total_resolved": total_resolved,
                "overall_resolution_rate": round(overall_resolution_rate, 2),
                "period_days": (config.end_date - config.start_date).days,
            },
            "agent_statistics": agent_stats,
            "rankings": {"top_performers": top_performers, "fastest_resolvers": fastest_resolvers},
            "charts": {
                "resolution_rate_comparison": {
                    "labels": [stat["agent_name"] for stat in agent_stats],
                    "data": [stat["resolution_rate"] for stat in agent_stats],
                },
                "workload_distribution": {
                    "labels": [stat["agent_name"] for stat in agent_stats],
                    "data": [stat["total_tickets"] for stat in agent_stats],
                },
            },
        }

    async def _generate_tickets_summary(self, config: ReportConfig) -> Dict[str, Any]:
        """Relatório resumo de tickets"""

        from django.db import sync_to_async

        @sync_to_async
        def get_tickets_data():
            tickets = Ticket.objects.filter(created_at__range=[config.start_date, config.end_date])

            # Aplicar filtros
            if config.filters:
                if "status" in config.filters:
                    tickets = tickets.filter(status__in=config.filters["status"])
                if "priority" in config.filters:
                    tickets = tickets.filter(priority__in=config.filters["priority"])
                if "category" in config.filters:
                    tickets = tickets.filter(category__in=config.filters["category"])

            total_tickets = tickets.count()

            # Distribuição por status
            status_distribution = tickets.values("status").annotate(count=Count("id")).order_by("-count")

            # Distribuição por prioridade
            priority_distribution = tickets.values("priority").annotate(count=Count("id")).order_by("-count")

            # Distribuição por categoria
            category_distribution = tickets.values("category").annotate(count=Count("id")).order_by("-count")

            # Tickets por dia
            daily_tickets = (
                tickets.annotate(date=TruncDate("created_at"))
                .values("date")
                .annotate(count=Count("id"))
                .order_by("date")
            )

            # Métricas de tempo
            resolved_tickets = tickets.filter(status="FECHADO", resolved_at__isnull=False)

            avg_resolution_time = 0
            if resolved_tickets.exists():
                resolution_times = []
                for ticket in resolved_tickets:
                    time_diff = (ticket.resolved_at - ticket.created_at).total_seconds() / 3600
                    resolution_times.append(time_diff)
                avg_resolution_time = sum(resolution_times) / len(resolution_times)

            # Top clientes por tickets
            top_customers = (
                tickets.values("customer__name", "customer__email")
                .annotate(ticket_count=Count("id"))
                .order_by("-ticket_count")[:10]
            )

            return {
                "total_tickets": total_tickets,
                "resolved_tickets": resolved_tickets.count(),
                "pending_tickets": tickets.filter(status__in=["NOVO", "ABERTO", "EM_ANDAMENTO"]).count(),
                "escalated_tickets": tickets.filter(escalated=True).count(),
                "avg_resolution_time_hours": round(avg_resolution_time, 2),
                "status_distribution": list(status_distribution),
                "priority_distribution": list(priority_distribution),
                "category_distribution": list(category_distribution),
                "daily_tickets": list(daily_tickets),
                "top_customers": list(top_customers),
            }

        data = await get_tickets_data()

        # Calcular tendências
        resolution_rate = (data["resolved_tickets"] / data["total_tickets"] * 100) if data["total_tickets"] > 0 else 0

        return {
            "summary": {
                "total_records": data["total_tickets"],
                "resolution_rate": round(resolution_rate, 2),
                "escalation_rate": (
                    round((data["escalated_tickets"] / data["total_tickets"] * 100), 2)
                    if data["total_tickets"] > 0
                    else 0
                ),
                "avg_resolution_time_hours": data["avg_resolution_time_hours"],
            },
            "distributions": {
                "status": data["status_distribution"],
                "priority": data["priority_distribution"],
                "category": data["category_distribution"],
            },
            "trends": {"daily_creation": data["daily_tickets"]},
            "top_customers": data["top_customers"],
            "charts": {
                "status_pie": {
                    "labels": [item["status"] for item in data["status_distribution"]],
                    "data": [item["count"] for item in data["status_distribution"]],
                },
                "daily_trend": {
                    "labels": [item["date"].isoformat() for item in data["daily_tickets"]],
                    "data": [item["count"] for item in data["daily_tickets"]],
                },
            },
        }

    async def _generate_sla_analysis(self, config: ReportConfig) -> Dict[str, Any]:
        """Análise de SLA e compliance"""

        from django.db import sync_to_async

        @sync_to_async
        def get_sla_data():
            tickets = Ticket.objects.filter(
                created_at__range=[config.start_date, config.end_date], sla_deadline__isnull=False
            )

            total_with_sla = tickets.count()

            # Tickets que cumpriram SLA
            met_sla = tickets.filter(status="FECHADO", resolved_at__lte=F("sla_deadline")).count()

            # Tickets que violaram SLA
            breached_sla = tickets.filter(
                Q(status="FECHADO", resolved_at__gt=F("sla_deadline"))
                | Q(status__in=["NOVO", "ABERTO", "EM_ANDAMENTO"], sla_deadline__lt=timezone.now())
            ).count()

            # SLA por prioridade
            sla_by_priority = {}
            priorities = ["BAIXA", "MEDIA", "ALTA", "CRITICA"]

            for priority in priorities:
                priority_tickets = tickets.filter(priority=priority)
                priority_total = priority_tickets.count()

                if priority_total > 0:
                    priority_met = priority_tickets.filter(status="FECHADO", resolved_at__lte=F("sla_deadline")).count()

                    compliance_rate = priority_met / priority_total * 100

                    sla_by_priority[priority] = {
                        "total": priority_total,
                        "met": priority_met,
                        "breached": priority_total - priority_met,
                        "compliance_rate": round(compliance_rate, 2),
                    }

            # SLA por agente
            sla_by_agent = []
            agents = Agent.objects.filter(is_active=True)

            for agent in agents:
                agent_tickets = tickets.filter(assigned_to=agent)
                agent_total = agent_tickets.count()

                if agent_total > 0:
                    agent_met = agent_tickets.filter(status="FECHADO", resolved_at__lte=F("sla_deadline")).count()

                    compliance_rate = agent_met / agent_total * 100

                    sla_by_agent.append(
                        {
                            "agent_name": agent.user.get_full_name(),
                            "total": agent_total,
                            "met": agent_met,
                            "breached": agent_total - agent_met,
                            "compliance_rate": round(compliance_rate, 2),
                        }
                    )

            # Tendência de SLA ao longo do tempo
            sla_trend = (
                tickets.filter(status="FECHADO")
                .annotate(week=TruncWeek("resolved_at"))
                .values("week")
                .annotate(total=Count("id"), met=Count("id", filter=Q(resolved_at__lte=F("sla_deadline"))))
                .order_by("week")
            )

            return {
                "total_with_sla": total_with_sla,
                "met_sla": met_sla,
                "breached_sla": breached_sla,
                "overall_compliance_rate": (met_sla / total_with_sla * 100) if total_with_sla > 0 else 0,
                "sla_by_priority": sla_by_priority,
                "sla_by_agent": sla_by_agent,
                "sla_trend": list(sla_trend),
            }

        data = await get_sla_data()

        return {
            "summary": {
                "total_records": data["total_with_sla"],
                "overall_compliance_rate": round(data["overall_compliance_rate"], 2),
                "tickets_met_sla": data["met_sla"],
                "tickets_breached_sla": data["breached_sla"],
            },
            "breakdown": {"by_priority": data["sla_by_priority"], "by_agent": data["sla_by_agent"]},
            "trends": {"weekly_compliance": data["sla_trend"]},
            "charts": {
                "compliance_overview": {
                    "labels": ["SLA Cumprido", "SLA Violado"],
                    "data": [data["met_sla"], data["breached_sla"]],
                },
                "priority_compliance": {
                    "labels": list(data["sla_by_priority"].keys()),
                    "data": [item["compliance_rate"] for item in data["sla_by_priority"].values()],
                },
            },
        }

    # ====================================
    # MÉTODOS AUXILIARES
    # ====================================

    def _calculate_sla_compliance(self, tickets_queryset) -> float:
        """Calcula taxa de compliance de SLA"""

        total_with_sla = tickets_queryset.filter(sla_deadline__isnull=False).count()

        if total_with_sla == 0:
            return 100.0

        met_sla = tickets_queryset.filter(status="FECHADO", resolved_at__lte=F("sla_deadline")).count()

        return round((met_sla / total_with_sla * 100), 2)

    # ====================================
    # EXPORTADORES
    # ====================================

    def export_to_excel(self, report_data: Dict[str, Any], filename: str = None) -> BytesIO:
        """Exporta relatório para Excel"""

        output = BytesIO()

        try:
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                # Aba resumo
                if "summary" in report_data:
                    summary_df = pd.DataFrame([report_data["summary"]])
                    summary_df.to_excel(writer, sheet_name="Resumo", index=False)

                # Dados principais
                if "agent_statistics" in report_data:
                    agents_df = pd.DataFrame(report_data["agent_statistics"])
                    agents_df.to_excel(writer, sheet_name="Agentes", index=False)

                if "distributions" in report_data:
                    for dist_name, dist_data in report_data["distributions"].items():
                        df = pd.DataFrame(dist_data)
                        df.to_excel(writer, sheet_name=f"Distribuição_{dist_name}", index=False)

            output.seek(0)
            return output

        except Exception as e:
            logger.error(f"Erro ao exportar para Excel: {e}")
            raise

    def export_to_csv(self, report_data: Dict[str, Any]) -> str:
        """Exporta dados principais para CSV"""

        try:
            # Determinar dados principais baseado no tipo de relatório
            main_data = None

            if "agent_statistics" in report_data:
                main_data = report_data["agent_statistics"]
            elif "distributions" in report_data and "status" in report_data["distributions"]:
                main_data = report_data["distributions"]["status"]
            elif "breakdown" in report_data:
                # Para relatórios de SLA
                main_data = report_data["breakdown"].get("by_agent", [])

            if main_data:
                df = pd.DataFrame(main_data)
                return df.to_csv(index=False)
            else:
                return "Nenhum dado principal encontrado para exportação CSV"

        except Exception as e:
            logger.error(f"Erro ao exportar CSV: {e}")
            return f"Erro na exportação: {str(e)}"


# Instância global do serviço
reports_service = AdvancedReportsService()
