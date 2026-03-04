# Modelos para Push Notifications - iConnect PWA
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class PushSubscription(models.Model):
    """Modelo para armazenar inscrições de push notification"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh_key = models.CharField(max_length=255)
    auth_key = models.CharField(max_length=255)
    user_agent = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(default=timezone.now)
    last_notification_at = models.DateTimeField(null=True, blank=True)
    notifications_sent = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "dashboard_push_subscription"
        verbose_name = "Push Subscription"
        verbose_name_plural = "Push Subscriptions"
        ordering = ["-subscribed_at"]

    def __str__(self):
        return f"{self.user.username} - {self.endpoint[:50]}..."

    @property
    def is_valid(self):
        """Verifica se a inscrição ainda é válida"""
        return self.is_active and self.endpoint

    def deactivate(self):
        """Desativa a inscrição"""
        self.is_active = False
        self.save()


class NotificationPreference(models.Model):
    """Preferências de notificação do usuário"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="notification_preferences")

    # Tipos de notificação
    tickets = models.BooleanField(default=True, verbose_name="Notificações de Tickets")
    chat = models.BooleanField(default=True, verbose_name="Notificações de Chat")
    system = models.BooleanField(default=True, verbose_name="Notificações do Sistema")

    # Configurações de horário silencioso
    quiet_hours = models.BooleanField(default=False, verbose_name="Horário Silencioso")
    quiet_start = models.TimeField(null=True, blank=True, verbose_name="Início do Silêncio")
    quiet_end = models.TimeField(null=True, blank=True, verbose_name="Fim do Silêncio")

    # Configurações avançadas
    sound_enabled = models.BooleanField(default=True, verbose_name="Som Habilitado")
    vibration_enabled = models.BooleanField(default=True, verbose_name="Vibração Habilitada")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dashboard_notification_preference"
        verbose_name = "Preferência de Notificação"
        verbose_name_plural = "Preferências de Notificação"

    def __str__(self):
        return f"Preferências de {self.user.username}"

    def get_preferences_dict(self):
        """Retorna as preferências como dicionário"""
        return {
            "tickets": self.tickets,
            "chat": self.chat,
            "system": self.system,
            "quiet_hours": self.quiet_hours,
            "quiet_start": self.quiet_start.strftime("%H:%M") if self.quiet_start else None,
            "quiet_end": self.quiet_end.strftime("%H:%M") if self.quiet_end else None,
            "sound_enabled": self.sound_enabled,
            "vibration_enabled": self.vibration_enabled,
        }


class PushNotificationLog(models.Model):
    """Log de notificações push enviadas"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notification_logs")
    subscription = models.ForeignKey(PushSubscription, on_delete=models.CASCADE, null=True, blank=True)

    title = models.CharField(max_length=255)
    body = models.TextField()
    notification_type = models.CharField(max_length=50, default="system")

    # Status da notificação
    STATUS_CHOICES = [
        ("pending", "Pendente"),
        ("sent", "Enviada"),
        ("failed", "Falhou"),
        ("clicked", "Clicada"),
        ("dismissed", "Dispensada"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Metadados
    extra_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "dashboard_notification_log"
        verbose_name = "Log de Notificação"
        verbose_name_plural = "Logs de Notificação"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["notification_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.username} ({self.status})"

    def mark_as_sent(self):
        """Marca a notificação como enviada"""
        self.status = "sent"
        self.sent_at = timezone.now()
        self.save()

    def mark_as_failed(self, error_message=""):
        """Marca a notificação como falhou"""
        self.status = "failed"
        self.error_message = error_message
        self.save()

    def mark_as_clicked(self):
        """Marca a notificação como clicada"""
        self.status = "clicked"
        self.clicked_at = timezone.now()
        self.save()


# Sinais para integração automática
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=User)
def create_notification_preferences(sender, instance, created, **kwargs):
    """Cria preferências padrão para novos usuários"""
    if created:
        NotificationPreference.objects.create(user=instance)
