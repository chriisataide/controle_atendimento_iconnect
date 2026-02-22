"""
Advanced Audit Service - Enhanced security monitoring
Models moved to dashboard/audit_models.py
"""
import logging
from typing import Dict, Any, Optional

from django.contrib.auth.models import User
from django.utils import timezone

from dashboard.audit_models import (
    AuditEvent,
    SecurityAlert,
    ComplianceReport,
    DataAccessLog,
)

logger = logging.getLogger(__name__)


class AdvancedAuditService:
    """Service para auditoria avancada"""

    @staticmethod
    def log_event(
        event_type: str,
        user: Optional[User] = None,
        action: str = "",
        description: str = "",
        content_object: Any = None,
        old_values: Dict = None,
        new_values: Dict = None,
        severity: str = "low",
        ip_address: str = "",
        user_agent: str = "",
        additional_data: Dict = None,
    ) -> AuditEvent:
        """Registrar evento de auditoria"""
        try:
            event = AuditEvent.objects.create(
                event_type=event_type,
                severity=severity,
                user=user,
                action=action,
                description=description,
                content_object=content_object,
                old_values=old_values or {},
                new_values=new_values or {},
                ip_address=ip_address or "0.0.0.0",
                user_agent=user_agent,
                additional_data=additional_data or {},
            )
            AdvancedAuditService._analyze_security_event(event)
            return event
        except Exception as e:
            logger.error(f"Erro ao registrar evento de auditoria: {e}")
            raise

    @staticmethod
    def create_security_alert(
        alert_type: str,
        title: str,
        description: str,
        severity: str = "medium",
        evidence: Dict = None,
        related_events: list = None,
    ) -> SecurityAlert:
        """Criar alerta de seguranca"""
        try:
            alert = SecurityAlert.objects.create(
                alert_type=alert_type,
                title=title,
                description=description,
                severity=severity,
                evidence=evidence or {},
            )
            if related_events:
                alert.related_events.set(related_events)
            AdvancedAuditService._notify_security_team(alert)
            return alert
        except Exception as e:
            logger.error(f"Erro ao criar alerta de seguranca: {e}")
            raise

    @staticmethod
    def log_data_access(
        user: User,
        access_type: str,
        data_type: str,
        record_count: int = 1,
        sensitive_fields: list = None,
        ip_address: str = "",
        business_justification: str = "",
    ) -> DataAccessLog:
        """Registrar acesso a dados sensiveis"""
        try:
            return DataAccessLog.objects.create(
                user=user,
                access_type=access_type,
                data_type=data_type,
                record_count=record_count,
                sensitive_fields=sensitive_fields or [],
                ip_address=ip_address or "0.0.0.0",
                business_justification=business_justification,
            )
        except Exception as e:
            logger.error(f"Erro ao registrar acesso a dados: {e}")
            raise

    @staticmethod
    def generate_compliance_report(
        report_type: str,
        start_date,
        end_date,
        generated_by: User,
    ) -> ComplianceReport:
        """Gerar relatorio de compliance"""
        try:
            events = AuditEvent.objects.filter(
                timestamp__range=[start_date, end_date]
            )
            data_accesses = DataAccessLog.objects.filter(
                timestamp__range=[start_date, end_date]
            )
            security_alerts = SecurityAlert.objects.filter(
                created_at__range=[start_date, end_date]
            )

            report_data = {
                "total_events": events.count(),
                "security_events": events.filter(event_type="security_event").count(),
                "data_accesses": data_accesses.count(),
                "security_alerts": security_alerts.count(),
                "resolved_alerts": security_alerts.filter(status="resolved").count(),
                "compliance_violations": events.filter(is_suspicious=True).count(),
            }

            total = report_data["total_events"]
            violations = report_data["compliance_violations"]
            score = ((total - violations) / total * 100) if total > 0 else 100

            return ComplianceReport.objects.create(
                report_type=report_type,
                title=f"Relatorio de Compliance {report_type.upper()}",
                description=f"Relatorio gerado para o periodo de {start_date.date()} a {end_date.date()}",
                start_date=start_date,
                end_date=end_date,
                report_data=report_data,
                compliance_score=score,
                generated_by=generated_by,
            )
        except Exception as e:
            logger.error(f"Erro ao gerar relatorio de compliance: {e}")
            raise

    @staticmethod
    def _analyze_security_event(event: AuditEvent):
        """Analisar evento para detectar atividade suspeita"""
        try:
            suspicious_conditions = []

            # Multiplas tentativas de login
            if event.event_type == "login" and event.user:
                recent_failures = AuditEvent.objects.filter(
                    user=event.user,
                    event_type="login",
                    additional_data__success=False,
                    timestamp__gte=timezone.now() - timezone.timedelta(minutes=15),
                ).count()
                if recent_failures >= 5:
                    suspicious_conditions.append("Multiple failed login attempts")

            # Acesso fora do horario comercial
            if event.timestamp.hour < 6 or event.timestamp.hour > 22:
                suspicious_conditions.append("Access outside business hours")

            # Mudancas de privilegios
            if event.event_type == "permission_change":
                suspicious_conditions.append("Permission changes require review")

            if suspicious_conditions:
                event.is_suspicious = True
                event.requires_review = True
                event.additional_data["suspicious_reasons"] = suspicious_conditions
                event.save()

                if len(suspicious_conditions) > 1 or "Multiple failed login attempts" in suspicious_conditions:
                    AdvancedAuditService.create_security_alert(
                        alert_type="suspicious_login" if "login" in event.event_type else "unusual_activity",
                        title=f"Atividade Suspeita Detectada - {event.user}",
                        description=f"Condicoes suspeitas: {', '.join(suspicious_conditions)}",
                        severity="high" if len(suspicious_conditions) > 2 else "medium",
                        evidence={"event_id": event.id, "conditions": suspicious_conditions},
                        related_events=[event],
                    )
        except Exception as e:
            logger.error(f"Erro na analise de seguranca: {e}")

    @staticmethod
    def _notify_security_team(alert: SecurityAlert):
        """Notificar equipe de seguranca sobre alerta"""
        try:
            logger.warning(f"Alerta de seguranca criado: {alert.title} - Severidade: {alert.severity}")
        except Exception as e:
            logger.error(f"Erro ao notificar equipe de seguranca: {e}")


# Instancia global do service
advanced_audit_service = AdvancedAuditService()
