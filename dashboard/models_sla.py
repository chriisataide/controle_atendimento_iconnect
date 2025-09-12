# Sistema de SLA
from django.db import models
from datetime import timedelta

class SLA(models.Model):
    PRIORIDADES = [
        ('baixa', 'Baixa - 72h'),
        ('media', 'Média - 24h'), 
        ('alta', 'Alta - 8h'),
        ('critica', 'Crítica - 2h'),
    ]
    
    prioridade = models.CharField(max_length=10, choices=PRIORIDADES, unique=True)
    tempo_primeira_resposta = models.DurationField()  # Tempo para primeira resposta
    tempo_resolucao = models.DurationField()  # Tempo total para resolução
    ativo = models.BooleanField(default=True)
    
    def __str__(self):
        return f"SLA {self.get_prioridade_display()}"

class MetricaSLA(models.Model):
    ticket = models.OneToOneField('Ticket', on_delete=models.CASCADE)
    sla = models.ForeignKey(SLA, on_delete=models.CASCADE)
    primeira_resposta_em = models.DateTimeField(null=True, blank=True)
    tempo_primeira_resposta = models.DurationField(null=True, blank=True)
    tempo_resolucao = models.DurationField(null=True, blank=True)
    sla_primeira_resposta_ok = models.BooleanField(null=True)
    sla_resolucao_ok = models.BooleanField(null=True)
    
    @property
    def status_sla(self):
        if self.sla_resolucao_ok is False:
            return "VIOLADO"
        elif self.sla_primeira_resposta_ok is False:
            return "RISCO"
        return "OK"
