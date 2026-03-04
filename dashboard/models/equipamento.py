"""
Modelos para Gestão de Equipamentos / Ativos (Asset Management).

Controle de equipamentos instalados em clientes, histórico de trocas,
vinculação com chamados e alertas automáticos.
"""

import logging

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

logger = logging.getLogger("dashboard")


class Equipamento(models.Model):
    """Equipamento/ativo instalado em um ponto de venda."""

    class StatusEquipamento(models.TextChoices):
        ATIVO = "ativo", "Ativo"
        EM_MANUTENCAO = "em_manutencao", "Em Manutenção"
        DESATIVADO = "desativado", "Desativado"
        EM_ESTOQUE = "em_estoque", "Em Estoque"

    # Identificação
    numero_serie = models.CharField(
        "Número de Série", max_length=100, unique=True, db_index=True, help_text="Identificador único do equipamento"
    )
    modelo = models.CharField("Modelo", max_length=100)
    marca = models.CharField("Marca", max_length=100, blank=True)
    tipo = models.CharField(
        "Tipo de Equipamento", max_length=100, db_index=True, help_text="Ex: Roteador, Switch, ONT, Cabo, OLT, etc."
    )
    descricao = models.TextField("Descrição", blank=True)
    patrimonio = models.CharField("Nº Patrimônio", max_length=50, blank=True, help_text="Código interno de patrimônio")

    # Localização
    ponto_de_venda = models.ForeignKey(
        "PontoDeVenda",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipamentos",
        verbose_name="Ponto de Venda",
        help_text="Ponto de venda onde o equipamento está instalado (vazio = em estoque)",
    )
    local_instalacao = models.CharField(
        "Local de Instalação", max_length=200, blank=True, help_text="Detalhamento: sala, rack, posição"
    )

    # Status e datas
    status = models.CharField(
        max_length=20, choices=StatusEquipamento.choices, default=StatusEquipamento.EM_ESTOQUE, db_index=True
    )
    data_instalacao = models.DateField("Data de Instalação", null=True, blank=True)
    data_garantia = models.DateField("Garantia até", null=True, blank=True)
    data_desativacao = models.DateField("Desativado em", null=True, blank=True)

    # Contadores (desnormalizados para performance)
    total_chamados = models.PositiveIntegerField(default=0, editable=False)
    total_trocas = models.PositiveIntegerField(default=0, editable=False)

    # Observações
    observacoes = models.TextField("Observações", blank=True)

    # Auditoria
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="equipamentos_criados"
    )

    class Meta:
        verbose_name = "Equipamento"
        verbose_name_plural = "Equipamentos"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["ponto_de_venda", "status"], name="idx_equip_pdv_status"),
            models.Index(fields=["tipo", "status"], name="idx_equip_tipo_status"),
        ]

    def __str__(self):
        pdv_label = self.ponto_de_venda.nome_fantasia if self.ponto_de_venda else "Em estoque"
        return f"{self.tipo} {self.marca} {self.modelo} — {pdv_label}"

    @property
    def garantia_ativa(self):
        """Verifica se a garantia ainda está vigente."""
        if self.data_garantia:
            return self.data_garantia >= timezone.now().date()
        return False

    @property
    def chamados_recentes_30d(self):
        """Quantidade de chamados nos últimos 30 dias."""
        limite = timezone.now() - timezone.timedelta(days=30)
        return self.tickets.filter(criado_em__gte=limite).count()

    def atualizar_contadores(self):
        """Recalcula contadores desnormalizados."""
        self.total_chamados = self.tickets.count()
        self.total_trocas = self.historico.filter(tipo_movimentacao="troca").count()
        self.save(update_fields=["total_chamados", "total_trocas"])


class HistoricoEquipamento(models.Model):
    """Registro de cada movimentação de um equipamento."""

    class TipoMovimentacao(models.TextChoices):
        INSTALACAO = "instalacao", "Instalação"
        TROCA = "troca", "Troca"
        RETIRADA = "retirada", "Retirada"
        MANUTENCAO = "manutencao", "Manutenção"
        DEVOLUCAO = "devolucao", "Devolução ao Estoque"

    equipamento = models.ForeignKey(Equipamento, on_delete=models.CASCADE, related_name="historico")
    tipo_movimentacao = models.CharField("Tipo", max_length=20, choices=TipoMovimentacao.choices, db_index=True)

    # Ponto de venda (de/para)
    pdv_anterior = models.ForeignKey(
        "PontoDeVenda",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="historico_equipamento_saida",
        verbose_name="PdV Anterior",
        help_text="Ponto de venda de onde o equipamento saiu",
    )
    pdv_novo = models.ForeignKey(
        "PontoDeVenda",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="historico_equipamento_entrada",
        verbose_name="PdV Novo",
        help_text="Ponto de venda para onde o equipamento foi",
    )

    # Troca: equipamento substituído
    equipamento_substituido = models.ForeignKey(
        Equipamento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="substituido_por",
        help_text="Equipamento antigo que foi substituído (em caso de troca)",
    )

    # Vínculo com chamado
    ticket = models.ForeignKey(
        "Ticket",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimentacoes_equipamento",
        help_text="Chamado que originou esta movimentação",
    )

    motivo = models.TextField("Motivo", blank=True)
    observacoes = models.TextField("Observações", blank=True)

    # Auditoria
    realizado_em = models.DateTimeField("Realizado em", default=timezone.now)
    realizado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="movimentacoes_equipamento_realizadas"
    )

    class Meta:
        verbose_name = "Histórico de Equipamento"
        verbose_name_plural = "Histórico de Equipamentos"
        ordering = ["-realizado_em"]

    def __str__(self):
        return f"{self.get_tipo_movimentacao_display()} — {self.equipamento} ({self.realizado_em:%d/%m/%Y})"


class AlertaEquipamento(models.Model):
    """Alertas automáticos gerados para equipamentos problemáticos."""

    class TipoAlerta(models.TextChoices):
        EXCESSO_CHAMADOS = "excesso_chamados", "Excesso de Chamados"
        TROCA_FREQUENTE = "troca_frequente", "Troca Frequente"
        GARANTIA_VENCENDO = "garantia_vencendo", "Garantia Vencendo"

    class Severidade(models.TextChoices):
        INFO = "info", "Informativo"
        WARNING = "warning", "Atenção"
        CRITICAL = "critical", "Crítico"

    equipamento = models.ForeignKey(Equipamento, on_delete=models.CASCADE, related_name="alertas")
    tipo = models.CharField(max_length=30, choices=TipoAlerta.choices, db_index=True)
    severidade = models.CharField(max_length=10, choices=Severidade.choices, default=Severidade.WARNING)
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()

    # Dados do alerta
    valor_atual = models.IntegerField(
        "Valor Atual", default=0, help_text="Ex: quantidade de chamados que disparou o alerta"
    )
    limiar = models.IntegerField("Limiar", default=3, help_text="Limite configurado para este tipo de alerta")

    # Status
    resolvido = models.BooleanField(default=False, db_index=True)
    resolvido_em = models.DateTimeField(null=True, blank=True)
    resolvido_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="alertas_equipamento_resolvidos"
    )
    acao_tomada = models.TextField("Ação Tomada", blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Alerta de Equipamento"
        verbose_name_plural = "Alertas de Equipamentos"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["resolvido", "-criado_em"], name="idx_alerta_equip_pend"),
        ]

    def __str__(self):
        return f"[{self.get_severidade_display()}] {self.titulo}"

    def resolver(self, usuario, acao=""):
        """Marca o alerta como resolvido."""
        self.resolvido = True
        self.resolvido_em = timezone.now()
        self.resolvido_por = usuario
        self.acao_tomada = acao
        self.save(update_fields=["resolvido", "resolvido_em", "resolvido_por", "acao_tomada"])


class ConfiguracaoAlertaEquipamento(models.Model):
    """Configurações dos limiares de alerta para equipamentos."""

    # Limiar de chamados
    chamados_limiar = models.PositiveIntegerField(
        "Chamados para Alerta",
        default=3,
        validators=[MinValueValidator(1)],
        help_text="Gerar alerta quando equipamento atingir X chamados no período",
    )
    chamados_periodo_dias = models.PositiveIntegerField(
        "Período (dias)",
        default=30,
        validators=[MinValueValidator(1)],
        help_text="Período em dias para contagem de chamados",
    )

    # Limiar de trocas
    trocas_limiar = models.PositiveIntegerField(
        "Trocas para Alerta",
        default=2,
        validators=[MinValueValidator(1)],
        help_text="Gerar alerta quando equipamento for trocado X vezes no período",
    )
    trocas_periodo_dias = models.PositiveIntegerField(
        "Período de Trocas (dias)",
        default=90,
        validators=[MinValueValidator(1)],
        help_text="Período em dias para contagem de trocas",
    )

    # Garantia
    garantia_dias_aviso = models.PositiveIntegerField(
        "Aviso de Garantia (dias)",
        default=30,
        validators=[MinValueValidator(1)],
        help_text="Alertar X dias antes do vencimento da garantia",
    )

    ativo = models.BooleanField(default=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    atualizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Configuração de Alerta"
        verbose_name_plural = "Configurações de Alertas"

    def __str__(self):
        return f"Config Alertas (chamados≥{self.chamados_limiar}/{self.chamados_periodo_dias}d)"

    def save(self, *args, **kwargs):
        # Singleton: garantir que só existe uma configuração
        if not self.pk and ConfiguracaoAlertaEquipamento.objects.exists():
            existing = ConfiguracaoAlertaEquipamento.objects.first()
            self.pk = existing.pk
        super().save(*args, **kwargs)

    @classmethod
    def get_config(cls):
        """Retorna a configuração atual ou cria uma com valores padrão."""
        config, _ = cls.objects.get_or_create(pk=1)
        return config
