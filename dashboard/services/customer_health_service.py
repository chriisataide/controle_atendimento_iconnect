"""
Customer Health Score Service — Calcular e monitorar saude dos clientes
"""

import logging

from django.db.models import Avg

logger = logging.getLogger(__name__)


class CustomerHealthService:
    """Servico para calcular health scores de clientes"""

    def calculate_all(self):
        """Recalcular health score de todos os clientes"""
        from dashboard.models import Cliente, CustomerHealthScore

        clientes = Cliente.objects.all()
        updated = 0

        for cliente in clientes:
            hs, created = CustomerHealthScore.objects.get_or_create(
                cliente=cliente,
            )
            hs.calculate()
            updated += 1

        logger.info(f"Health scores recalculados para {updated} clientes")
        return updated

    def get_at_risk_clients(self, threshold: float = 60.0):
        """Retornar clientes com score abaixo do threshold"""
        from dashboard.models import CustomerHealthScore

        return CustomerHealthScore.objects.filter(score__lt=threshold).select_related("cliente").order_by("score")

    def get_summary(self):
        """Resumo dos health scores"""
        from dashboard.models import CustomerHealthScore

        scores = CustomerHealthScore.objects.all()
        total = scores.count()
        if total == 0:
            return {"total": 0, "avg_score": 0, "at_risk": 0, "critical": 0}

        return {
            "total": total,
            "avg_score": round(scores.aggregate(avg=Avg("score"))["avg"] or 0, 1),
            "healthy": scores.filter(risk_level="low").count(),
            "medium_risk": scores.filter(risk_level="medium").count(),
            "high_risk": scores.filter(risk_level="high").count(),
            "critical": scores.filter(risk_level="critical").count(),
        }


customer_health_service = CustomerHealthService()
