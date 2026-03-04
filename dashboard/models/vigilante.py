# =============================================================================
# Models para Dashboard de Implantação / Pronta Resposta de Vigilante
# =============================================================================
from django.conf import settings
from django.db import models


class RegistroVigilante(models.Model):
    """Registro individual de período de vigilante (implantação ou pronta resposta)."""

    TIPO_CHOICES = [
        ("implantacao", "Implantação"),
        ("pronta-resposta", "Pronta Resposta"),
    ]

    ticket = models.ForeignKey(
        "dashboard.Ticket",
        on_delete=models.CASCADE,
        related_name="registros_vigilante",
        verbose_name="Ticket",
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, db_index=True)
    empresa = models.CharField(max_length=100, db_index=True)
    uf = models.CharField(max_length=2, db_index=True)
    inicio = models.DateTimeField(verbose_name="Data/Hora Início")
    fim = models.DateTimeField(verbose_name="Data/Hora Fim")
    duracao_minutos = models.FloatField(verbose_name="Duração (minutos)")
    valor = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor (R$)")
    detalhes = models.TextField(blank=True, verbose_name="Detalhamento do cálculo")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registros_vigilante_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Registro de Vigilante"
        verbose_name_plural = "Registros de Vigilante"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["tipo", "criado_em"]),
            models.Index(fields=["empresa", "uf"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.empresa}/{self.uf} — R$ {self.valor}"

    @property
    def duracao_formatada(self):
        h = int(self.duracao_minutos // 60)
        m = int(self.duracao_minutos % 60)
        return f"{h}h {m}min"
