"""
Modelos de Conformidade LGPD (Lei Geral de Proteção de Dados).

Implementa:
- Registro de consentimento
- Solicitações de portabilidade/exclusão de dados
- Auditoria de acesso a PII
- Base legal para tratamento de dados

Padrão: LGPD (Lei 13.709/2018) + BACEN Resolução 4.658
"""

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class LGPDConsent(models.Model):
    """Registro de consentimento LGPD por finalidade."""

    PURPOSE_CHOICES = [
        ("essential", "Essencial para prestação de serviço"),
        ("support", "Suporte técnico e atendimento"),
        ("communication", "Comunicações e notificações"),
        ("marketing", "Marketing e promoções"),
        ("analytics", "Analytics e melhoria de serviço"),
        ("third_party", "Compartilhamento com terceiros"),
        ("profiling", "Análise de perfil e personalização"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="lgpd_consents", verbose_name="Titular dos dados"
    )
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, verbose_name="Finalidade")
    granted = models.BooleanField(default=False, verbose_name="Consentimento concedido")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP do consentimento")
    user_agent = models.TextField(blank=True, verbose_name="User-Agent")
    legal_basis = models.CharField(
        max_length=50,
        default="consent",
        choices=[
            ("consent", "Consentimento do titular"),
            ("contract", "Execução de contrato"),
            ("legal_obligation", "Obrigação legal"),
            ("legitimate_interest", "Interesse legítimo"),
            ("vital_interest", "Proteção da vida"),
            ("public_policy", "Políticas públicas"),
        ],
        verbose_name="Base legal",
    )
    version = models.CharField(max_length=20, default="1.0", verbose_name="Versão dos termos")
    granted_at = models.DateTimeField(auto_now_add=True, verbose_name="Data do consentimento")
    revoked_at = models.DateTimeField(null=True, blank=True, verbose_name="Data da revogação")
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Data de expiração")

    class Meta:
        verbose_name = "Consentimento LGPD"
        verbose_name_plural = "Consentimentos LGPD"
        ordering = ["-granted_at"]
        unique_together = ["user", "purpose", "version"]
        indexes = [
            models.Index(fields=["user", "purpose"]),
            models.Index(fields=["granted", "-granted_at"]),
        ]

    def __str__(self):
        status = "✓" if self.granted and not self.revoked_at else "✗"
        return f"{status} {self.user.username} — {self.get_purpose_display()}"

    @property
    def is_valid(self):
        """Verifica se o consentimento está ativo e não expirado."""
        if not self.granted or self.revoked_at:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True

    def revoke(self):
        """Revoga o consentimento."""
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked_at"])


class LGPDDataRequest(models.Model):
    """Solicitações de titular de dados (portabilidade, exclusão, acesso)."""

    REQUEST_TYPES = [
        ("access", "Acesso aos dados pessoais"),
        ("portability", "Portabilidade dos dados"),
        ("correction", "Correção de dados"),
        ("deletion", "Exclusão de dados (direito ao esquecimento)"),
        ("restriction", "Restrição de tratamento"),
        ("objection", "Oposição ao tratamento"),
        ("revoke_consent", "Revogação de consentimento"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pendente"),
        ("in_progress", "Em andamento"),
        ("completed", "Concluída"),
        ("rejected", "Rejeitada"),
        ("cancelled", "Cancelada"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="lgpd_requests", verbose_name="Titular dos dados"
    )
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPES, verbose_name="Tipo de solicitação")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True, verbose_name="Status"
    )
    description = models.TextField(blank=True, verbose_name="Descrição/justificativa")
    response = models.TextField(blank=True, verbose_name="Resposta ao titular")
    # Rastreabilidade
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP da solicitação")
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lgpd_requests_processed",
        verbose_name="Processado por",
    )
    # Arquivo de exportação (para portabilidade)
    export_file = models.FileField(
        upload_to="lgpd/exports/%Y/%m/", null=True, blank=True, verbose_name="Arquivo de exportação"
    )
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criada em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizada em")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Concluída em")
    # Prazo legal: 15 dias (LGPD Art. 18 §5)
    deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Prazo legal",
        help_text="Prazo de 15 dias úteis para resposta (LGPD Art. 18 §5)",
    )

    class Meta:
        verbose_name = "Solicitação LGPD"
        verbose_name_plural = "Solicitações LGPD"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "request_type"]),
        ]

    def __str__(self):
        return f"{self.get_request_type_display()} — {self.user.username} ({self.get_status_display()})"

    def complete(self, processed_by=None, response=""):
        """Marca a solicitação como concluída."""
        self.status = "completed"
        self.completed_at = timezone.now()
        self.processed_by = processed_by
        if response:
            self.response = response
        self.save(update_fields=["status", "completed_at", "processed_by", "response"])

    def reject(self, processed_by=None, response=""):
        """Rejeita a solicitação."""
        self.status = "rejected"
        self.processed_by = processed_by
        if response:
            self.response = response
        self.save(update_fields=["status", "processed_by", "response"])


class LGPDAccessLog(models.Model):
    """Log de acesso a dados pessoais (PII) — obrigatório para auditoria BACEN."""

    ACTION_CHOICES = [
        ("view", "Visualização"),
        ("export", "Exportação"),
        ("edit", "Edição"),
        ("delete", "Exclusão"),
        ("share", "Compartilhamento"),
        ("decrypt", "Descriptografia"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="lgpd_access_logs", verbose_name="Usuário que acessou"
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, verbose_name="Ação")
    resource_type = models.CharField(
        max_length=100, verbose_name="Tipo do recurso", help_text="Ex: Cliente, Fornecedor, PontoDeVenda"
    )
    resource_id = models.CharField(max_length=50, verbose_name="ID do recurso")
    fields_accessed = models.JSONField(
        default=list, verbose_name="Campos acessados", help_text="Lista de campos PII acessados"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP de origem")
    user_agent = models.TextField(blank=True, verbose_name="User-Agent")
    justification = models.TextField(blank=True, verbose_name="Justificativa")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Data/hora")

    class Meta:
        verbose_name = "Log de Acesso PII"
        verbose_name_plural = "Logs de Acesso PII"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["action", "-timestamp"]),
        ]

    def __str__(self):
        return f"{self.user} — {self.action} {self.resource_type}#{self.resource_id}"
