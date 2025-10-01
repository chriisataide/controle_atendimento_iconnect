"""
Advanced Audit System - Enhanced security monitoring
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class AuditEvent(models.Model):
    """Eventos de auditoria avançados"""
    
    EVENT_TYPES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('create', 'Criação'),
        ('update', 'Atualização'),
        ('delete', 'Exclusão'),
        ('view', 'Visualização'),
        ('export', 'Exportação'),
        ('import', 'Importação'),
        ('permission_change', 'Mudança de Permissão'),
        ('security_event', 'Evento de Segurança'),
        ('system_event', 'Evento do Sistema'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Baixa'),
        ('medium', 'Média'),
        ('high', 'Alta'),
        ('critical', 'Crítica'),
    ]
    
    # Evento
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default='low')
    timestamp = models.DateTimeField(default=timezone.now)
    
    # Usuário e sessão
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    
    # Objeto afetado (generic foreign key)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Detalhes do evento
    action = models.CharField(max_length=100)
    description = models.TextField()
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    additional_data = models.JSONField(default=dict, blank=True)
    
    # Status e flags
    is_suspicious = models.BooleanField(default=False)
    is_resolved = models.BooleanField(default=False)
    requires_review = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Evento de Auditoria"
        verbose_name_plural = "Eventos de Auditoria"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp', 'event_type']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['is_suspicious']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.user} - {self.timestamp}"


class SecurityAlert(models.Model):
    """Alertas de segurança"""
    
    ALERT_TYPES = [
        ('brute_force', 'Tentativa de Força Bruta'),
        ('suspicious_login', 'Login Suspeito'),
        ('privilege_escalation', 'Escalação de Privilégios'),
        ('data_breach', 'Possível Vazamento de Dados'),
        ('unusual_activity', 'Atividade Incomum'),
        ('failed_authentication', 'Falha de Autenticação'),
        ('permission_denied', 'Acesso Negado'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Aberto'),
        ('investigating', 'Investigando'),
        ('resolved', 'Resolvido'),
        ('false_positive', 'Falso Positivo'),
    ]
    
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=AuditEvent.SEVERITY_LEVELS)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='open')
    
    # Detalhes
    title = models.CharField(max_length=200)
    description = models.TextField()
    evidence = models.JSONField(default=dict)
    
    # Relacionamentos
    related_events = models.ManyToManyField(AuditEvent, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_alerts')
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Alerta de Segurança"
        verbose_name_plural = "Alertas de Segurança"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.alert_type} - {self.severity} - {self.status}"


class ComplianceReport(models.Model):
    """Relatórios de compliance"""
    
    REPORT_TYPES = [
        ('gdpr', 'GDPR'),
        ('lgpd', 'LGPD'),
        ('sox', 'SOX'),
        ('iso27001', 'ISO 27001'),
        ('custom', 'Personalizado'),
    ]
    
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Período do relatório
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    # Dados do relatório
    report_data = models.JSONField(default=dict)
    compliance_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Status
    is_published = models.BooleanField(default=False)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Relatório de Compliance"
        verbose_name_plural = "Relatórios de Compliance"
        ordering = ['-generated_at']
    
    def __str__(self):
        return f"{self.report_type} - {self.title} - {self.generated_at.date()}"


class DataAccessLog(models.Model):
    """Log de acesso a dados sensíveis"""
    
    ACCESS_TYPES = [
        ('view', 'Visualização'),
        ('export', 'Exportação'),
        ('download', 'Download'),
        ('print', 'Impressão'),
        ('copy', 'Cópia'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    access_type = models.CharField(max_length=10, choices=ACCESS_TYPES)
    
    # Dados acessados
    data_type = models.CharField(max_length=50)  # 'customer_data', 'financial_data', etc.
    record_count = models.PositiveIntegerField(default=1)
    sensitive_fields = models.JSONField(default=list)
    
    # Justificativa
    business_justification = models.TextField(blank=True)
    authorized_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='authorized_accesses'
    )
    
    # Contexto
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(default=timezone.now)
    session_id = models.CharField(max_length=40, blank=True)
    
    class Meta:
        verbose_name = "Log de Acesso a Dados"
        verbose_name_plural = "Logs de Acesso a Dados"
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user} - {self.access_type} - {self.data_type}"


class AdvancedAuditService:
    """Service para auditoria avançada"""
    
    @staticmethod
    def log_event(
        event_type: str,
        user: Optional[User] = None,
        action: str = "",
        description: str = "",
        content_object: Any = None,
        old_values: Dict = None,
        new_values: Dict = None,
        severity: str = 'low',
        ip_address: str = "",
        user_agent: str = "",
        additional_data: Dict = None
    ) -> AuditEvent:
        """
        Registrar evento de auditoria
        """
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
                ip_address=ip_address,
                user_agent=user_agent,
                additional_data=additional_data or {}
            )
            
            # Análise de segurança automática
            AdvancedAuditService._analyze_security_event(event)
            
            return event
            
        except Exception as e:
            logger.error(f"Erro ao registrar evento de auditoria: {str(e)}")
            raise
    
    @staticmethod
    def create_security_alert(
        alert_type: str,
        title: str,
        description: str,
        severity: str = 'medium',
        evidence: Dict = None,
        related_events: list = None
    ) -> SecurityAlert:
        """
        Criar alerta de segurança
        """
        try:
            alert = SecurityAlert.objects.create(
                alert_type=alert_type,
                title=title,
                description=description,
                severity=severity,
                evidence=evidence or {}
            )
            
            if related_events:
                alert.related_events.set(related_events)
            
            # Notificar equipe de segurança
            AdvancedAuditService._notify_security_team(alert)
            
            return alert
            
        except Exception as e:
            logger.error(f"Erro ao criar alerta de segurança: {str(e)}")
            raise
    
    @staticmethod
    def log_data_access(
        user: User,
        access_type: str,
        data_type: str,
        record_count: int = 1,
        sensitive_fields: list = None,
        ip_address: str = "",
        business_justification: str = ""
    ) -> DataAccessLog:
        """
        Registrar acesso a dados sensíveis
        """
        try:
            return DataAccessLog.objects.create(
                user=user,
                access_type=access_type,
                data_type=data_type,
                record_count=record_count,
                sensitive_fields=sensitive_fields or [],
                ip_address=ip_address,
                business_justification=business_justification
            )
            
        except Exception as e:
            logger.error(f"Erro ao registrar acesso a dados: {str(e)}")
            raise
    
    @staticmethod
    def generate_compliance_report(
        report_type: str,
        start_date,
        end_date,
        generated_by: User
    ) -> ComplianceReport:
        """
        Gerar relatório de compliance
        """
        try:
            # Coletar dados do período
            events = AuditEvent.objects.filter(
                timestamp__range=[start_date, end_date]
            )
            
            data_accesses = DataAccessLog.objects.filter(
                timestamp__range=[start_date, end_date]
            )
            
            security_alerts = SecurityAlert.objects.filter(
                created_at__range=[start_date, end_date]
            )
            
            # Calcular métricas de compliance
            report_data = {
                'total_events': events.count(),
                'security_events': events.filter(event_type='security_event').count(),
                'data_accesses': data_accesses.count(),
                'security_alerts': security_alerts.count(),
                'resolved_alerts': security_alerts.filter(status='resolved').count(),
                'compliance_violations': events.filter(is_suspicious=True).count(),
            }
            
            # Calcular score de compliance
            total_possible = report_data['total_events']
            violations = report_data['compliance_violations']
            compliance_score = ((total_possible - violations) / total_possible * 100) if total_possible > 0 else 100
            
            return ComplianceReport.objects.create(
                report_type=report_type,
                title=f"Relatório de Compliance {report_type.upper()}",
                description=f"Relatório gerado para o período de {start_date.date()} a {end_date.date()}",
                start_date=start_date,
                end_date=end_date,
                report_data=report_data,
                compliance_score=compliance_score,
                generated_by=generated_by
            )
            
        except Exception as e:
            logger.error(f"Erro ao gerar relatório de compliance: {str(e)}")
            raise
    
    @staticmethod
    def _analyze_security_event(event: AuditEvent):
        """
        Analisar evento para detectar atividade suspeita
        """
        try:
            suspicious_conditions = []
            
            # Verificar múltiplas tentativas de login
            if event.event_type == 'login' and event.user:
                recent_failures = AuditEvent.objects.filter(
                    user=event.user,
                    event_type='login',
                    additional_data__success=False,
                    timestamp__gte=timezone.now() - timezone.timedelta(minutes=15)
                ).count()
                
                if recent_failures >= 5:
                    suspicious_conditions.append('Multiple failed login attempts')
            
            # Verificar acesso fora do horário comercial
            if event.timestamp.hour < 6 or event.timestamp.hour > 22:
                suspicious_conditions.append('Access outside business hours')
            
            # Verificar mudanças de privilégios
            if event.event_type == 'permission_change':
                suspicious_conditions.append('Permission changes require review')
            
            # Marcar como suspeito se houver condições
            if suspicious_conditions:
                event.is_suspicious = True
                event.requires_review = True
                event.additional_data['suspicious_reasons'] = suspicious_conditions
                event.save()
                
                # Criar alerta de segurança se necessário
                if len(suspicious_conditions) > 1 or 'Multiple failed login attempts' in suspicious_conditions:
                    AdvancedAuditService.create_security_alert(
                        alert_type='suspicious_login' if 'login' in event.event_type else 'unusual_activity',
                        title=f"Atividade Suspeita Detectada - {event.user}",
                        description=f"Condições suspeitas: {', '.join(suspicious_conditions)}",
                        severity='high' if len(suspicious_conditions) > 2 else 'medium',
                        evidence={'event_id': event.id, 'conditions': suspicious_conditions},
                        related_events=[event]
                    )
            
        except Exception as e:
            logger.error(f"Erro na análise de segurança: {str(e)}")
    
    @staticmethod
    def _notify_security_team(alert: SecurityAlert):
        """
        Notificar equipe de segurança sobre alerta
        """
        try:
            # TODO: Implementar notificação para equipe de segurança
            # Pode ser email, Slack, etc.
            logger.warning(f"Alerta de segurança criado: {alert.title} - Severidade: {alert.severity}")
            
        except Exception as e:
            logger.error(f"Erro ao notificar equipe de segurança: {str(e)}")


# Instância global do service
advanced_audit_service = AdvancedAuditService()