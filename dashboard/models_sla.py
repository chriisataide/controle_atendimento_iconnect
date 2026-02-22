"""
DEPRECADO - Use models.SLAPolicy, models.SLAHistory, models.SLAAlert em vez destes models.
Este arquivo sera removido em versao futura.
Os models SLAPolicy (mais completo) estao em dashboard/models.py.
"""
import warnings
warnings.warn(
    "models_sla.py esta deprecado. Use SLAPolicy/SLAHistory/SLAAlert de dashboard.models",
    DeprecationWarning,
    stacklevel=2,
)

# Mantido apenas para compatibilidade de migracao
from django.db import models


class SLA(models.Model):
    """DEPRECADO - use SLAPolicy de dashboard.models"""
    PRIORIDADES = [
        ('baixa', 'Baixa - 72h'),
        ('media', 'Media - 24h'),
        ('alta', 'Alta - 8h'),
        ('critica', 'Critica - 2h'),
    ]
    prioridade = models.CharField(max_length=10, choices=PRIORIDADES, unique=True)
    tempo_primeira_resposta = models.DurationField()
    tempo_resolucao = models.DurationField()
    ativo = models.BooleanField(default=True)

    class Meta:
        managed = False  # Nao gerenciar mais esta tabela
        verbose_name = "SLA (Deprecado)"

    def __str__(self):
        return f"SLA {self.get_prioridade_display()}"


class MetricaSLA(models.Model):
    """DEPRECADO - use SLAHistory de dashboard.models"""
    ticket = models.OneToOneField('Ticket', on_delete=models.CASCADE)
    sla = models.ForeignKey(SLA, on_delete=models.CASCADE)
    primeira_resposta_em = models.DateTimeField(null=True, blank=True)
    tempo_primeira_resposta = models.DurationField(null=True, blank=True)
    tempo_resolucao = models.DurationField(null=True, blank=True)
    sla_primeira_resposta_ok = models.BooleanField(null=True)
    sla_resolucao_ok = models.BooleanField(null=True)

    class Meta:
        managed = False  # Nao gerenciar mais esta tabela
        verbose_name = "Metrica SLA (Deprecado)"

    @property
    def status_sla(self):
        if self.sla_resolucao_ok is False:
            return "VIOLADO"
        elif self.sla_primeira_resposta_ok is False:
            return "RISCO"
        return "OK"
