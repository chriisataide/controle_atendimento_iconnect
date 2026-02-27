"""
Modelos de Auditoria e Seguranca para iConnect
Armazena eventos, alertas, compliance e logs de acesso a dados sensiveis
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class AuditEvent(models.Model):
    """Eventos de auditoria avancados com persistencia em banco"""

    EVENT_TYPES = [
        ("login", "Login"),
        ("logout", "Logout"),
        ("create", "Criacao"),
        ("update", "Atualizacao"),
        ("delete", "Exclusao"),
        ("view", "Visualizacao"),
        ("export", "Exportacao"),
        ("import", "Importacao"),
        ("permission_change", "Mudanca de Permissao"),
        ("security_event", "Evento de Seguranca"),
        ("system_event", "Evento do Sistema"),
    ]

    SEVERITY_LEVELS = [
        ("low", "Baixa"),
        ("medium", "Media"),
        ("high", "Alta"),
        ("critical", "Critica"),
    ]

    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default="low")
    timestamp = models.DateTimeField(default=timezone.now)

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_events")
    session_key = models.CharField(max_length=40, blank=True)
    ip_address = models.GenericIPAddressField(default="0.0.0.0")
    user_agent = models.TextField(blank=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    action = models.CharField(max_length=100)
    description = models.TextField()
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    additional_data = models.JSONField(default=dict, blank=True)

    is_suspicious = models.BooleanField(default=False)
    is_resolved = models.BooleanField(default=False)
    requires_review = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Evento de Auditoria"
        verbose_name_plural = "Eventos de Auditoria"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["timestamp", "event_type"]),
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["ip_address", "timestamp"]),
            models.Index(fields=["is_suspicious"]),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.user} - {self.timestamp}"


class SecurityAlert(models.Model):
    """Alertas de seguranca"""

    ALERT_TYPES = [
        ("brute_force", "Tentativa de Forca Bruta"),
        ("suspicious_login", "Login Suspeito"),
        ("privilege_escalation", "Escalacao de Privilegios"),
        ("data_breach", "Possivel Vazamento de Dados"),
        ("unusual_activity", "Atividade Incomum"),
        ("failed_authentication", "Falha de Autenticacao"),
        ("permission_denied", "Acesso Negado"),
    ]

    STATUS_CHOICES = [
        ("open", "Aberto"),
        ("investigating", "Investigando"),
        ("resolved", "Resolvido"),
        ("false_positive", "Falso Positivo"),
    ]

    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=AuditEvent.SEVERITY_LEVELS)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="open")

    title = models.CharField(max_length=200)
    description = models.TextField()
    evidence = models.JSONField(default=dict)

    related_events = models.ManyToManyField(AuditEvent, blank=True, related_name="alerts")
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_security_alerts")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Alerta de Seguranca"
        verbose_name_plural = "Alertas de Seguranca"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.alert_type} - {self.severity} - {self.status}"


class ComplianceReport(models.Model):
    """Relatorios de compliance (LGPD, ISO, etc)"""

    REPORT_TYPES = [
        ("gdpr", "GDPR"),
        ("lgpd", "LGPD"),
        ("sox", "SOX"),
        ("iso27001", "ISO 27001"),
        ("custom", "Personalizado"),
    ]

    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    report_data = models.JSONField(default=dict)
    compliance_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    is_published = models.BooleanField(default=False)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="compliance_reports")
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Relatorio de Compliance"
        verbose_name_plural = "Relatorios de Compliance"
        ordering = ["-generated_at"]

    def __str__(self):
        return f"{self.report_type} - {self.title}"


class DataAccessLog(models.Model):
    """Log de acesso a dados sensiveis"""

    ACCESS_TYPES = [
        ("view", "Visualizacao"),
        ("export", "Exportacao"),
        ("download", "Download"),
        ("print", "Impressao"),
        ("copy", "Copia"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="data_access_logs")
    access_type = models.CharField(max_length=10, choices=ACCESS_TYPES)

    data_type = models.CharField(max_length=50)
    record_count = models.PositiveIntegerField(default=1)
    sensitive_fields = models.JSONField(default=list)

    business_justification = models.TextField(blank=True)
    authorized_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="authorized_data_accesses"
    )

    ip_address = models.GenericIPAddressField(default="0.0.0.0")
    timestamp = models.DateTimeField(default=timezone.now)
    session_id = models.CharField(max_length=40, blank=True)

    class Meta:
        verbose_name = "Log de Acesso a Dados"
        verbose_name_plural = "Logs de Acesso a Dados"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.user} - {self.access_type} - {self.data_type}"
