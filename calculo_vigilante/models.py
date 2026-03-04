"""
Modelos do app Cálculo de Implantação de Vigilante.
"""

from django.conf import settings
from django.db import models


class ProcessamentoHistorico(models.Model):
    """Registra cada processamento de planilha realizado."""

    STATUS_CHOICES = [
        ("sucesso", "Sucesso"),
        ("erro", "Erro"),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="processamentos_vigilante",
        verbose_name="Usuário",
    )
    arquivo_nome = models.CharField("Nome do arquivo", max_length=255)
    arquivo_tamanho = models.PositiveIntegerField("Tamanho (bytes)", default=0)
    linhas_total = models.PositiveIntegerField("Total de linhas", default=0)
    linhas_processadas = models.PositiveIntegerField("Linhas processadas", default=0)
    linhas_com_valor = models.PositiveIntegerField("Linhas com valor", default=0)
    linhas_sem_match = models.PositiveIntegerField("Linhas sem match", default=0)
    valor_total = models.DecimalField("Valor total calculado", max_digits=14, decimal_places=2, default=0)
    status = models.CharField("Status", max_length=10, choices=STATUS_CHOICES, default="sucesso")
    erro_mensagem = models.TextField("Mensagem de erro", blank=True, default="")
    criado_em = models.DateTimeField("Data do processamento", auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Processamento"
        verbose_name_plural = "Processamentos"

    def __str__(self):
        return f"{self.arquivo_nome} — {self.get_status_display()} ({self.criado_em:%d/%m/%Y %H:%M})"
