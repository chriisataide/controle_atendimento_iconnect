import logging
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

# Importar mixins
from ..mixins import SoftDeleteModel

# Importar modelos de estoque
from .estoque import *  # noqa: F401,F403

logger = logging.getLogger("dashboard")


# ----------------------
# Modelo de Ponto de Venda
# ----------------------
class PontoDeVenda(models.Model):
    """Ponto de venda (unidade/filial) vinculado a um Cliente (empresa)."""

    # Vínculo com Cliente (empresa)
    cliente = models.ForeignKey(
        "Cliente",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="pontos_de_venda",
        verbose_name="Cliente",
        help_text="Empresa proprietária deste ponto de venda",
    )

    # Dados da Unidade
    razao_social = models.CharField("Razão Social", max_length=150)
    nome_fantasia = models.CharField("Nome Fantasia", max_length=150)
    cnpj = models.CharField("CNPJ", max_length=18, unique=True)
    inscricao_estadual = models.CharField("Inscrição Estadual", max_length=30, blank=True)
    inscricao_municipal = models.CharField("Inscrição Municipal", max_length=30, blank=True)

    # Endereço
    cep = models.CharField("CEP", max_length=9)
    logradouro = models.CharField("Logradouro", max_length=120)
    numero = models.CharField("Número", max_length=10)
    complemento = models.CharField("Complemento", max_length=50, blank=True)
    bairro = models.CharField("Bairro", max_length=60)
    cidade = models.CharField("Cidade", max_length=60)
    estado = models.CharField("Estado", max_length=2)
    pais = models.CharField("País", max_length=40, default="Brasil")

    # Contatos
    celular = models.CharField("Celular / WhatsApp", max_length=500, help_text="Criptografado em repouso")
    email_principal = models.EmailField("E-mail principal")
    email_financeiro = models.EmailField("E-mail financeiro", blank=True)
    website = models.URLField("Website", blank=True)

    # Responsável pela Empresa — PII criptografado (LGPD Art. 46)
    responsavel_nome = models.CharField("Nome do Responsável", max_length=100)
    responsavel_cpf = models.CharField("CPF do Responsável", max_length=500, help_text="Criptografado em repouso")
    responsavel_cargo = models.CharField("Cargo / Função", max_length=60)
    responsavel_telefone = models.CharField(
        "Telefone do Responsável", max_length=500, help_text="Criptografado em repouso"
    )
    responsavel_email = models.EmailField("E-mail do Responsável", blank=True)

    # Campos de rede/regional (importação planilha)
    cod_rede = models.CharField("Código Rede", max_length=20, blank=True, default="")
    cod_regional = models.CharField("Código Regional", max_length=20, blank=True, default="")
    rede = models.CharField(
        "Rede", max_length=100, blank=True, default="",
        help_text="Nome da rede (ex: REDE - GRANDE SAO PAULO)",
    )
    regional = models.CharField(
        "Regional", max_length=100, blank=True, default="",
        help_text="Nome da regional (ex: REG SP CENTRO-NORTE)",
    )
    status_unidade = models.CharField(
        "Status Unidade", max_length=30, blank=True, default="Ativo",
        help_text="Status operacional: Ativo, Virtual, Encerrado, etc.",
    )
    tipo = models.CharField(
        "Tipo", max_length=30, blank=True, default="",
        help_text="Tipo da unidade: AG, PAB, PAE, Store, etc.",
    )
    uniorg = models.CharField(
        "UNIORG", max_length=20, blank=True, default="", db_index=True,
        help_text="Código da unidade organizacional (ex: 001-0001)",
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ponto de Venda"
        verbose_name_plural = "Pontos de Venda"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.nome_fantasia} ({self.cnpj})"

    def save(self, *args, **kwargs):
        from ..utils.crypto import encrypt_value

        if self.responsavel_cpf and not self.responsavel_cpf.startswith("enc::"):
            self.responsavel_cpf = encrypt_value(self.responsavel_cpf)
        if self.celular and not self.celular.startswith("enc::"):
            self.celular = encrypt_value(self.celular)
        if self.responsavel_telefone and not self.responsavel_telefone.startswith("enc::"):
            self.responsavel_telefone = encrypt_value(self.responsavel_telefone)
        super().save(*args, **kwargs)

    def get_responsavel_cpf(self):
        """Retorna CPF do responsável descriptografado."""
        from ..utils.crypto import decrypt_value

        return decrypt_value(self.responsavel_cpf)

    def get_celular(self):
        """Retorna celular descriptografado."""
        from ..utils.crypto import decrypt_value

        return decrypt_value(self.celular)

    def get_responsavel_telefone(self):
        """Retorna telefone do responsável descriptografado."""
        from ..utils.crypto import decrypt_value

        return decrypt_value(self.responsavel_telefone)


class Cliente(models.Model):
    """Cliente (empresa/marca). Ex: Santander, Bradesco.
    Dados simples da instituição. Endereços e responsáveis ficam no PontoDeVenda."""

    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cliente_profile",
        help_text="Conta de usuario vinculada",
    )
    nome = models.CharField(max_length=200, verbose_name="Nome da Instituição")
    segmento = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Segmento / Ramo",
        help_text="Ex: Financeiro, Varejo, Saúde, Tecnologia",
    )
    email = models.EmailField(unique=True, verbose_name="E-mail de Contato")
    telefone = models.CharField(
        max_length=500, blank=True, help_text="Criptografado em repouso", verbose_name="Telefone"
    )
    # Campo legado mantido por compatibilidade
    empresa = models.CharField(max_length=100, blank=True, verbose_name="Empresa (legado)")
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    cod_rede = models.CharField(
        max_length=20, blank=True, default="", db_index=True,
        verbose_name="Código Rede",
        help_text="Código da rede na planilha (ex: 104-0021)",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        from ..utils.crypto import encrypt_value

        if self.telefone and not self.telefone.startswith("enc::"):
            self.telefone = encrypt_value(self.telefone)
        super().save(*args, **kwargs)

    def get_telefone(self):
        """Retorna telefone descriptografado."""
        from ..utils.crypto import decrypt_value

        return decrypt_value(self.telefone)


class StatusTicket(models.TextChoices):
    ABERTO = "aberto", "Aberto"
    EM_ANDAMENTO = "em_andamento", "Em Andamento"
    AGUARDANDO_CLIENTE = "aguardando_cliente", "Aguardando Cliente"
    RESOLVIDO = "resolvido", "Resolvido"
    FECHADO = "fechado", "Fechado"


class PrioridadeTicket(models.TextChoices):
    BAIXA = "baixa", "Baixa"
    MEDIA = "media", "Média"
    ALTA = "alta", "Alta"
    CRITICA = "critica", "Crítica"


class CategoriaTicket(models.Model):
    nome = models.CharField(max_length=50)
    descricao = models.TextField(blank=True)
    cor = models.CharField(max_length=7, default="#007bff")  # Hex color

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"

    def __str__(self):
        return self.nome


class SLAPolicy(models.Model):
    """Políticas de SLA por categoria e prioridade"""

    name = models.CharField(max_length=100)
    categoria = models.ForeignKey(CategoriaTicket, on_delete=models.CASCADE, null=True, blank=True)
    prioridade = models.CharField(max_length=10, choices=PrioridadeTicket.choices)

    # Tempos de SLA em minutos para maior flexibilidade
    first_response_time = models.IntegerField(default=240, help_text="Tempo primeira resposta em minutos")
    resolution_time = models.IntegerField(default=1440, help_text="Tempo de resolução em minutos")
    escalation_time = models.IntegerField(default=480, help_text="Tempo para escalação em minutos")

    # Configurações de horário
    business_hours_only = models.BooleanField(default=True)
    start_hour = models.TimeField(default="08:00", help_text="Início do horário comercial")
    end_hour = models.TimeField(default="18:00", help_text="Fim do horário comercial")
    work_days = models.CharField(max_length=7, default="1234567", help_text="Dias da semana (1=Seg, 7=Dom)")

    # Configurações de alerta
    warning_percentage = models.IntegerField(
        default=80,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="% do tempo SLA para enviar alerta",
    )
    escalation_enabled = models.BooleanField(default=True)
    escalation_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sla_escalations",
        help_text="Supervisor para escalação",
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Política de SLA"
        verbose_name_plural = "Políticas de SLA"
        unique_together = ["categoria", "prioridade"]
        constraints = [
            models.CheckConstraint(
                condition=Q(first_response_time__gt=0),
                name="sla_first_response_time_gt_0",
            ),
            models.CheckConstraint(
                condition=Q(resolution_time__gt=0),
                name="sla_resolution_time_gt_0",
            ),
            models.CheckConstraint(
                condition=Q(escalation_time__gt=0),
                name="sla_escalation_time_gt_0",
            ),
            models.CheckConstraint(
                condition=Q(warning_percentage__gte=0, warning_percentage__lte=100),
                name="sla_warning_pct_0_100",
            ),
        ]

    def __str__(self):
        return self.name


class WorkflowRule(models.Model):
    """Regras de workflow automatizado"""

    EVENT_CHOICES = [
        ("ticket_created", "Ticket Criado"),
        ("ticket_updated", "Ticket Atualizado"),
        ("status_changed", "Status Alterado"),
        ("agent_assigned", "Agente Atribuído"),
        ("interaction_added", "Interação Adicionada"),
        ("sla_warning", "Aviso de SLA"),
        ("sla_breach", "Violação de SLA"),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    trigger_event = models.CharField(max_length=50, choices=EVENT_CHOICES, db_index=True)
    conditions = models.JSONField(help_text="Condições em formato JSON")
    actions = models.JSONField(help_text="Ações em formato JSON")
    priority = models.IntegerField(default=1, help_text="Prioridade de execução (1-10)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Regra de Workflow"
        verbose_name_plural = "Regras de Workflow"
        ordering = ["-priority", "name"]

    def __str__(self):
        return self.name


class Ticket(models.Model):
    # --- Tipo ITIL ---
    TIPO_CHOICES = [
        ("incidente", "Incidente"),
        ("requisicao", "Requisicao de Servico"),
        ("problema", "Problema"),
        ("mudanca", "Mudanca"),
    ]

    numero = models.CharField(max_length=10, unique=True, blank=True, db_index=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="tickets")
    ponto_de_venda = models.ForeignKey(
        PontoDeVenda,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
        verbose_name="Ponto de Venda",
        help_text="Unidade/filial onde o atendimento ocorre",
    )
    agente = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets_agente")
    categoria = models.ForeignKey(CategoriaTicket, on_delete=models.SET_NULL, null=True, blank=True)

    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    tags = models.CharField(max_length=500, blank=True, help_text="Tags separadas por virgula")
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES, default="incidente")
    status = models.CharField(max_length=20, choices=StatusTicket.choices, default=StatusTicket.ABERTO, db_index=True)
    prioridade = models.CharField(
        max_length=10, choices=PrioridadeTicket.choices, default=PrioridadeTicket.MEDIA, db_index=True
    )
    origem = models.CharField(max_length=20, default="web", help_text="web, email, whatsapp, slack")

    # --- Equipamento vinculado (opcional) ---
    equipamento = models.ForeignKey(
        "Equipamento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
        help_text="Equipamento relacionado a este chamado",
    )

    # --- Hierarquia e vinculacao ---
    parent_ticket = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sub_tickets",
        help_text="Ticket pai (sub-tickets)",
    )
    related_tickets = models.ManyToManyField("self", blank=True, symmetrical=True, help_text="Tickets vinculados")
    merged_into = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merged_from",
        help_text="Ticket de destino do merge",
    )

    # --- Watchers / Followers ---
    watchers = models.ManyToManyField(
        User, blank=True, related_name="watched_tickets", help_text="Usuarios que acompanham este ticket"
    )

    # Campos relacionados ao SLA
    sla_policy = models.ForeignKey(SLAPolicy, on_delete=models.SET_NULL, null=True, blank=True)
    sla_deadline = models.DateTimeField(null=True, blank=True, help_text="Prazo de resposta SLA")
    sla_resolution_deadline = models.DateTimeField(null=True, blank=True, help_text="Prazo de resolucao SLA")
    first_response_at = models.DateTimeField(null=True, blank=True)
    is_escalated = models.BooleanField(default=False)
    escalated_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="escalated_tickets"
    )
    escalated_at = models.DateTimeField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    resolvido_em = models.DateTimeField(null=True, blank=True)
    fechado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["status", "prioridade", "criado_em"], name="idx_ticket_status_prio_data"),
            models.Index(fields=["status", "agente", "criado_em"], name="idx_ticket_status_agente_data"),
            models.Index(fields=["cliente", "status", "criado_em"], name="idx_ticket_cliente_status"),
            models.Index(fields=["status", "sla_deadline"], name="idx_ticket_status_sla"),
            models.Index(fields=["categoria", "status"], name="idx_ticket_categoria_status"),
        ]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.numero:
                # Gerar número do ticket sequencial com lock para evitar race condition
                from django.db.models import Max

                ultimo = Ticket.objects.select_for_update().aggregate(max_num=Max("id"))["max_num"] or 0
                self.numero = f"TK-{ultimo + 1:05d}"

            # Atualizar timestamps baseado no status
            if self.status == StatusTicket.RESOLVIDO and not self.resolvido_em:
                self.resolvido_em = timezone.now()
            elif self.status == StatusTicket.FECHADO and not self.fechado_em:
                self.fechado_em = timezone.now()

            super().save(*args, **kwargs)

    def get_tags_list(self):
        """Retorna lista de tags"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(",") if tag.strip()]
        return []

    def __str__(self):
        return f"#{self.numero} - {self.titulo}"


class TicketAnexo(models.Model):
    """Modelo para anexos dos tickets"""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="anexos")
    arquivo = models.FileField(upload_to="tickets/anexos/%Y/%m/")
    nome_original = models.CharField(max_length=255)
    tamanho = models.BigIntegerField(help_text="Tamanho em bytes")
    tipo_mime = models.CharField(max_length=100)
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Anexo do Ticket"
        verbose_name_plural = "Anexos dos Tickets"

    def __str__(self):
        return f"Anexo: {self.nome_original} - Ticket #{self.ticket.numero}"


class SLAHistory(models.Model):
    """Histórico de SLA dos tickets"""

    STATUS_CHOICES = [
        ("on_track", "No Prazo"),
        ("warning", "Alerta"),
        ("breached", "Violado"),
        ("escalated", "Escalado"),
        ("completed", "Concluído"),
    ]

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="sla_history")
    sla_policy = models.ForeignKey(SLAPolicy, on_delete=models.CASCADE)

    # Prazos calculados
    first_response_deadline = models.DateTimeField()
    resolution_deadline = models.DateTimeField()
    escalation_deadline = models.DateTimeField()

    # Status atual
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="on_track", db_index=True)
    warning_sent = models.BooleanField(default=False)
    escalated = models.BooleanField(default=False)
    escalated_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)

    # Métricas de cumprimento
    first_response_time = models.DurationField(null=True, blank=True)
    resolution_time = models.DurationField(null=True, blank=True)
    sla_compliance = models.BooleanField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Histórico de SLA"
        verbose_name_plural = "Históricos de SLA"
        ordering = ["-created_at"]

    def __str__(self):
        return f"SLA #{self.ticket.numero} - {self.status}"


class SLAAlert(models.Model):
    """Alertas de SLA"""

    ALERT_TYPES = [
        ("warning", "Alerta de Prazo"),
        ("breach", "Violação de SLA"),
        ("escalation", "Escalação Necessária"),
        ("resolved", "SLA Cumprido"),
    ]

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="sla_alerts")
    sla_history = models.ForeignKey(SLAHistory, on_delete=models.CASCADE)
    alert_type = models.CharField(max_length=15, choices=ALERT_TYPES, db_index=True)
    message = models.TextField()

    # Destinatários
    sent_to_agent = models.BooleanField(default=False)
    sent_to_supervisor = models.BooleanField(default=False)
    sent_to_client = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Alerta de SLA"
        verbose_name_plural = "Alertas de SLA"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Alerta SLA - Ticket #{self.ticket.numero}"


class InteracaoTicket(models.Model):
    TIPO_CHOICES = [
        ("resposta", "Resposta"),
        ("nota_interna", "Nota Interna"),
        ("sistema", "Sistema"),
        ("status_change", "Mudança de Status"),
    ]

    CANAL_CHOICES = [
        ("web", "Web"),
        ("email", "Email"),
        ("whatsapp", "WhatsApp"),
        ("chat", "Chat"),
        ("api", "API"),
    ]

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="interacoes")
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    mensagem = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="resposta", db_index=True)
    canal = models.CharField(max_length=15, choices=CANAL_CHOICES, default="web")
    eh_publico = models.BooleanField(default=True)  # Visível para o cliente
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Interação"
        verbose_name_plural = "Interações"
        ordering = ["criado_em"]
        indexes = [
            models.Index(fields=["ticket", "criado_em"]),
            models.Index(fields=["tipo", "criado_em"]),
        ]

    def __str__(self):
        return f"Interação em {self.ticket.numero} por {self.usuario.username}"


class ItemAtendimento(SoftDeleteModel):
    """Produtos e serviços utilizados em um atendimento/ticket (soft delete habilitado)"""

    TIPO_ITEM_CHOICES = [
        ("produto", "Produto"),
        ("servico", "Serviço"),
    ]

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="itens_atendimento")
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="itens_atendimento")
    tipo_item = models.CharField(max_length=10, choices=TIPO_ITEM_CHOICES, default="produto")

    # Quantidade e valores
    quantidade = models.DecimalField(
        max_digits=10, decimal_places=3, default=1, validators=[MinValueValidator(Decimal("0.001"))]
    )
    valor_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Valor unitário usado no atendimento",
    )
    desconto_percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Desconto aplicado (%)",
    )

    # Observações específicas do uso
    observacoes = models.TextField(blank=True, help_text="Observações sobre o uso do item no atendimento")

    # Controle
    adicionado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="itens_adicionados")
    adicionado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Item de Atendimento"
        verbose_name_plural = "Itens de Atendimento"
        ordering = ["adicionado_em"]
        unique_together = ["ticket", "produto"]  # Evita duplicação do mesmo produto no mesmo ticket
        constraints = [
            models.CheckConstraint(
                condition=Q(quantidade__gt=0),
                name="item_atend_quantidade_gt_0",
            ),
            models.CheckConstraint(
                condition=Q(valor_unitario__gte=0),
                name="item_atend_valor_unitario_gte_0",
            ),
            models.CheckConstraint(
                condition=Q(desconto_percentual__gte=0, desconto_percentual__lte=100),
                name="item_atend_desconto_0_100",
            ),
        ]

    def __str__(self):
        return f"{self.produto.nome} - Ticket #{self.ticket.numero}"

    @property
    def valor_subtotal(self):
        """Calcula o subtotal do item (quantidade × valor_unitário)"""
        return self.quantidade * self.valor_unitario

    @property
    def valor_desconto(self):
        """Calcula o valor do desconto aplicado"""
        return self.valor_subtotal * (self.desconto_percentual / Decimal("100"))

    @property
    def valor_total(self):
        """Calcula o valor total do item (subtotal - desconto)"""
        return self.valor_subtotal - self.valor_desconto

    def save(self, *args, **kwargs):
        # Se não foi definido um valor unitário, usar o preço de venda do produto
        if not self.valor_unitario:
            self.valor_unitario = self.produto.preco_venda
        super().save(*args, **kwargs)


class StatusAgente(models.TextChoices):
    ONLINE = "online", "Online"
    OCUPADO = "ocupado", "Ocupado"
    AUSENTE = "ausente", "Ausente"
    OFFLINE = "offline", "Offline"


class PerfilAgente(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=StatusAgente.choices, default=StatusAgente.OFFLINE, db_index=True)
    max_tickets_simultaneos = models.IntegerField(default=5)
    especialidades = models.ManyToManyField(CategoriaTicket, blank=True)

    class Meta:
        verbose_name = "Perfil do Agente"
        verbose_name_plural = "Perfis dos Agentes"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"

    @property
    def tickets_ativos(self):
        return Ticket.objects.filter(
            agente=self.user,
            status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO, StatusTicket.AGUARDANDO_CLIENTE],
        ).count()


class PerfilUsuario(models.Model):
    """Modelo para estender as informações de perfil do usuário (PII protegido - LGPD)"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")

    # Informações pessoais — PII criptografado (LGPD Art. 46)
    telefone = models.CharField(
        max_length=500, blank=True, verbose_name="Telefone", help_text="Criptografado em repouso"
    )
    telefone_alternativo = models.CharField(
        max_length=500, blank=True, verbose_name="Telefone Alternativo", help_text="Criptografado em repouso"
    )

    # Endereço — PII criptografado
    endereco = models.CharField(
        max_length=500, blank=True, verbose_name="Endereço", help_text="Criptografado em repouso"
    )
    cidade = models.CharField(max_length=100, blank=True, verbose_name="Cidade")
    estado = models.CharField(max_length=2, blank=True, verbose_name="Estado")
    cep = models.CharField(max_length=500, blank=True, verbose_name="CEP", help_text="Criptografado em repouso")

    # Informações profissionais
    cargo = models.CharField(max_length=100, blank=True, verbose_name="Cargo")
    departamento = models.CharField(
        max_length=3,
        blank=True,
        choices=[
            ("TI", "Tecnologia da Informação"),
            ("SUP", "Suporte Técnico"),
            ("RH", "Recursos Humanos"),
            ("FIN", "Financeiro"),
            ("OPS", "Operações"),
            ("COM", "Comercial"),
        ],
        verbose_name="Departamento",
    )
    bio = models.TextField(blank=True, verbose_name="Bio Profissional")

    # Avatar
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True, verbose_name="Foto de Perfil")

    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuários"

    def __str__(self):
        return f"Perfil de {self.user.get_full_name() or self.user.username}"

    def save(self, *args, **kwargs):
        from ..utils.crypto import encrypt_value

        if self.telefone and not self.telefone.startswith("enc::"):
            self.telefone = encrypt_value(self.telefone)
        if self.telefone_alternativo and not self.telefone_alternativo.startswith("enc::"):
            self.telefone_alternativo = encrypt_value(self.telefone_alternativo)
        if self.endereco and not self.endereco.startswith("enc::"):
            self.endereco = encrypt_value(self.endereco)
        if self.cep and not self.cep.startswith("enc::"):
            self.cep = encrypt_value(self.cep)
        super().save(*args, **kwargs)

    def get_telefone(self):
        """Retorna telefone descriptografado."""
        from ..utils.crypto import decrypt_value

        return decrypt_value(self.telefone)

    def get_telefone_alternativo(self):
        """Retorna telefone alternativo descriptografado."""
        from ..utils.crypto import decrypt_value

        return decrypt_value(self.telefone_alternativo)

    def get_endereco(self):
        """Retorna endereço descriptografado."""
        from ..utils.crypto import decrypt_value

        return decrypt_value(self.endereco)

    def get_cep(self):
        """Retorna CEP descriptografado."""
        from ..utils.crypto import decrypt_value

        return decrypt_value(self.cep)

    @property
    def perfil_completo_percentual(self):
        """Calcula o percentual de preenchimento do perfil"""
        campos_obrigatorios = [
            self.user.email,
            self.user.first_name,
            self.user.last_name,
            self.telefone,
            self.endereco,
            self.cidade,
            self.cargo,
        ]

        campos_preenchidos = sum(1 for campo in campos_obrigatorios if campo and campo.strip())
        return round((campos_preenchidos / len(campos_obrigatorios)) * 100)


# ========== NOVOS MODELOS PARA RECURSOS AVANÇADOS ==========


class SLAViolation(models.Model):
    """Registro de violações de SLA"""

    VIOLATION_TYPES = [
        ("deadline_missed", "Prazo Perdido"),
        ("escalation_failed", "Falha na Escalação"),
        ("response_delayed", "Resposta Atrasada"),
    ]

    SEVERITY_LEVELS = [
        ("low", "Baixa"),
        ("medium", "Média"),
        ("high", "Alta"),
        ("critical", "Crítica"),
    ]

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="sla_violations")
    violation_type = models.CharField(max_length=20, choices=VIOLATION_TYPES, db_index=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default="medium", db_index=True)
    expected_deadline = models.DateTimeField()
    actual_time = models.DateTimeField()
    time_exceeded = models.DurationField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Violação de SLA"
        verbose_name_plural = "Violações de SLA"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Violação SLA - Ticket #{self.ticket.numero}"


class WorkflowExecution(models.Model):
    """Registro de execuções de workflow"""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="workflow_executions")
    rule = models.ForeignKey(WorkflowRule, on_delete=models.CASCADE)
    trigger_event = models.CharField(max_length=50)
    execution_result = models.JSONField()
    executed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    execution_time = models.DurationField(null=True, blank=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Execução de Workflow"
        verbose_name_plural = "Execuções de Workflow"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Execução {self.rule.name} - Ticket #{self.ticket.numero}"


class NotificationLog(models.Model):
    """Log de notificações enviadas"""

    NOTIFICATION_TYPES = [
        ("email", "Email"),
        ("slack", "Slack"),
        ("whatsapp", "WhatsApp"),
        ("sms", "SMS"),
        ("push", "Push Notification"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pendente"),
        ("sent", "Enviado"),
        ("delivered", "Entregue"),
        ("failed", "Falhou"),
        ("bounced", "Rejeitado"),
    ]

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="notifications", null=True, blank=True)
    recipient = models.CharField(max_length=200)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, db_index=True)
    event_type = models.CharField(max_length=50)
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    external_id = models.CharField(max_length=100, blank=True)  # ID do serviço externo
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Log de Notificação"
        verbose_name_plural = "Logs de Notificações"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.notification_type} para {self.recipient}"


class AutomationSettings(models.Model):
    """Configurações de automação do sistema"""

    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração de Automação"
        verbose_name_plural = "Configurações de Automação"

    def __str__(self):
        return self.key


class KnowledgeBase(models.Model):
    """DEPRECADO - Use ArtigoConhecimento de models_knowledge.py como KB principal.
    Mantido para compatibilidade com migrations existentes."""

    title = models.CharField(max_length=200)
    content = models.TextField()
    keywords = models.JSONField(help_text="Lista de palavras-chave para busca")
    category = models.CharField(max_length=50, blank=True)
    is_public = models.BooleanField(default=True)
    view_count = models.IntegerField(default=0)
    helpful_votes = models.IntegerField(default=0)
    unhelpful_votes = models.IntegerField(default=0)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Base de Conhecimento (Deprecado)"
        verbose_name_plural = "Base de Conhecimento (Deprecado)"
        ordering = ["-view_count", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(view_count__gte=0),
                name="kb_view_count_gte_0",
            ),
            models.CheckConstraint(
                condition=Q(helpful_votes__gte=0),
                name="kb_helpful_votes_gte_0",
            ),
            models.CheckConstraint(
                condition=Q(unhelpful_votes__gte=0),
                name="kb_unhelpful_votes_gte_0",
            ),
        ]

    def __str__(self):
        return self.title


class SystemMetrics(models.Model):
    """Métricas do sistema para dashboard executivo"""

    date = models.DateField(unique=True)
    total_tickets = models.IntegerField(default=0)
    new_tickets = models.IntegerField(default=0)
    resolved_tickets = models.IntegerField(default=0)
    sla_compliance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    avg_resolution_time = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="em horas")
    customer_satisfaction = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    agent_productivity = models.JSONField(default=dict)  # métricas por agente
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Métricas do Sistema"
        verbose_name_plural = "Métricas do Sistema"
        ordering = ["-date"]

    def __str__(self):
        return f"Métricas {self.date}"


class Notification(models.Model):
    """Notificações do sistema em tempo real"""

    NOTIFICATION_TYPES = [
        ("new_ticket", "Novo Ticket"),
        ("ticket_assigned", "Ticket Atribuído"),
        ("ticket_status_change", "Mudança de Status"),
        ("sla_warning", "Alerta de SLA"),
        ("sla_breach", "SLA Violado"),
        ("new_interaction", "Nova Interação"),
        ("system_alert", "Alerta do Sistema"),
    ]

    COLOR_CHOICES = [
        ("primary", "Primária"),
        ("secondary", "Secundária"),
        ("success", "Sucesso"),
        ("danger", "Perigo"),
        ("warning", "Aviso"),
        ("info", "Informação"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES, db_index=True)
    title = models.CharField(max_length=200)
    message = models.TextField()
    icon = models.CharField(max_length=50, default="notifications")
    color = models.CharField(max_length=20, choices=COLOR_CHOICES, default="primary")
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)  # dados extras
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["read", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.username}"

    def mark_as_read(self):
        """Marca a notificação como lida"""
        if not self.read:
            self.read = True
            self.read_at = timezone.now()
            self.save(update_fields=["read", "read_at"])


# ========== MODELOS FINANCEIROS ==========


class CategoriaFinanceira(SoftDeleteModel):
    """Categorias financeiras (soft delete habilitado)"""

    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    tipo = models.CharField(max_length=20, choices=[("receita", "Receita"), ("despesa", "Despesa")])
    cor = models.CharField(max_length=7, default="#007bff")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Categoria Financeira"
        verbose_name_plural = "Categorias Financeiras"

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"


class FormaPagamento(SoftDeleteModel):
    """Formas de pagamento (soft delete habilitado)"""

    nome = models.CharField(max_length=50)
    descricao = models.TextField(blank=True, null=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Forma de Pagamento"
        verbose_name_plural = "Formas de Pagamento"

    def __str__(self):
        return self.nome


class Contrato(SoftDeleteModel):
    """Contratos com clientes (soft delete habilitado)"""

    STATUS_CHOICES = [
        ("ativo", "Ativo"),
        ("suspenso", "Suspenso"),
        ("cancelado", "Cancelado"),
        ("vencido", "Vencido"),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="contratos")
    numero_contrato = models.CharField(max_length=50, unique=True)
    descricao = models.TextField()
    valor_mensal = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    data_inicio = models.DateField(db_index=True)
    data_fim = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ativo", db_index=True)
    observacoes = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Contrato"
        verbose_name_plural = "Contratos"
        ordering = ["-criado_em"]
        constraints = [
            models.CheckConstraint(
                condition=Q(valor_mensal__gte=Decimal("0.01")),
                name="contrato_valor_mensal_gte_001",
            ),
        ]

    def __str__(self):
        return f"Contrato {self.numero_contrato} - {self.cliente.nome}"


class Fatura(SoftDeleteModel):
    """Faturas de contratos (soft delete habilitado)"""

    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("pago", "Pago"),
        ("vencido", "Vencido"),
        ("cancelado", "Cancelado"),
    ]

    contrato = models.ForeignKey(Contrato, on_delete=models.PROTECT, related_name="faturas")
    numero_fatura = models.CharField(max_length=50, unique=True)
    valor = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    data_vencimento = models.DateField(db_index=True)
    data_pagamento = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente", db_index=True)
    observacoes = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Fatura"
        verbose_name_plural = "Faturas"
        ordering = ["-data_vencimento"]
        constraints = [
            models.CheckConstraint(
                condition=Q(valor__gte=Decimal("0.01")),
                name="fatura_valor_gte_001",
            ),
        ]

    def __str__(self):
        return f"Fatura {self.numero_fatura} - {self.contrato.cliente.nome}"


class Pagamento(SoftDeleteModel):
    """Pagamentos de faturas (soft delete habilitado)"""

    fatura = models.ForeignKey(Fatura, on_delete=models.PROTECT, related_name="pagamentos")
    forma_pagamento = models.ForeignKey(FormaPagamento, on_delete=models.PROTECT)
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    data_pagamento = models.DateTimeField(db_index=True)
    numero_transacao = models.CharField(max_length=100, blank=True, null=True)
    observacoes = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pagamento"
        verbose_name_plural = "Pagamentos"
        ordering = ["-data_pagamento"]
        constraints = [
            models.CheckConstraint(
                condition=Q(valor_pago__gte=Decimal("0.01")),
                name="pagamento_valor_pago_gte_001",
            ),
        ]

    def __str__(self):
        return f"Pagamento {self.fatura.numero_fatura} - R$ {self.valor_pago}"


class MovimentacaoFinanceira(SoftDeleteModel):
    """Movimentações financeiras (soft delete habilitado)"""

    TIPO_CHOICES = [
        ("receita", "Receita"),
        ("despesa", "Despesa"),
    ]

    categoria = models.ForeignKey(CategoriaFinanceira, on_delete=models.PROTECT)
    descricao = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, db_index=True)
    valor = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    data_movimentacao = models.DateField(db_index=True)
    observacoes = models.TextField(blank=True, null=True)
    usuario = models.ForeignKey(User, on_delete=models.PROTECT)
    # Relacionamento opcional com fatura (para receitas de faturas pagas)
    fatura = models.ForeignKey(Fatura, on_delete=models.SET_NULL, null=True, blank=True)
    # Novo campo para centro de custo
    centro_custo = models.ForeignKey(
        "CentroCusto",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimentacoes",
        help_text="Centro de custo responsável",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimentação Financeira"
        verbose_name_plural = "Movimentações Financeiras"
        ordering = ["-data_movimentacao"]
        constraints = [
            models.CheckConstraint(
                condition=Q(valor__gte=Decimal("0.01")),
                name="mov_financeira_valor_gte_001",
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.descricao} - R$ {self.valor}"


class RelatorioFinanceiro(models.Model):
    TIPO_CHOICES = [
        ("receitas_despesas", "Receitas x Despesas"),
        ("fluxo_caixa", "Fluxo de Caixa"),
        ("contratos_ativos", "Contratos Ativos"),
        ("faturas_pendentes", "Faturas Pendentes"),
        ("inadimplencia", "Inadimplência"),
        ("personalizado", "Personalizado"),
    ]

    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    data_inicio = models.DateField()
    data_fim = models.DateField()
    parametros = models.JSONField(default=dict, blank=True)
    gerado_por = models.ForeignKey(User, on_delete=models.PROTECT)
    gerado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Relatório Financeiro"
        verbose_name_plural = "Relatórios Financeiros"
        ordering = ["-gerado_em"]

    def __str__(self):
        return f"{self.nome} - {self.get_tipo_display()}"


class CentroCusto(SoftDeleteModel):
    """Centro de Custos para controle financeiro (soft delete habilitado)"""

    STATUS_CHOICES = [
        ("ativo", "Ativo"),
        ("inativo", "Inativo"),
        ("suspenso", "Suspenso"),
    ]

    # Informações básicas
    codigo = models.CharField(max_length=20, unique=True, help_text="Código único do centro de custo")
    nome = models.CharField(max_length=100, help_text="Nome do centro de custo")
    descricao = models.TextField(blank=True, null=True, help_text="Descrição detalhada")

    # Hierarquia e organização
    departamento = models.CharField(max_length=100, help_text="Departamento responsável")
    centro_pai = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subcentros",
        help_text="Centro de custo pai (para hierarquia)",
    )

    # Responsabilidade
    responsavel = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="centros_custo_responsavel",
        help_text="Responsável pelo centro de custo",
    )
    gerente = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="centros_custo_gerente",
        help_text="Gerente do centro de custo",
    )

    # Orçamento e controle
    orcamento_mensal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Orçamento mensal planejado",
    )
    orcamento_anual = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Orçamento anual planejado",
    )

    # Status e configurações
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ativo", db_index=True)
    permite_suborçamento = models.BooleanField(default=False, help_text="Permite estourar o orçamento")
    alerta_percentual = models.DecimalField(
        max_digits=5, decimal_places=2, default=80, help_text="Percentual para alerta de orçamento (%)"
    )

    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="centros_custo_criados"
    )

    class Meta:
        verbose_name = "Centro de Custo"
        verbose_name_plural = "Centros de Custo"
        ordering = ["departamento", "codigo"]
        constraints = [
            models.CheckConstraint(
                condition=Q(orcamento_mensal__gte=0),
                name="cc_orcamento_mensal_gte_0",
            ),
            models.CheckConstraint(
                condition=Q(orcamento_anual__gte=0),
                name="cc_orcamento_anual_gte_0",
            ),
            models.CheckConstraint(
                condition=Q(alerta_percentual__gte=0, alerta_percentual__lte=100),
                name="cc_alerta_pct_0_100",
            ),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    @property
    def orcamento_utilizado_mes_atual(self):
        """Calcula o orçamento utilizado no mês atual"""
        agora = timezone.now()
        mes_atual = agora.month
        ano_atual = agora.year

        total = (
            MovimentacaoFinanceira.objects.filter(
                centro_custo=self, data_movimentacao__month=mes_atual, data_movimentacao__year=ano_atual, tipo="despesa"
            ).aggregate(total=models.Sum("valor"))["total"]
            or 0
        )

        return total

    @property
    def percentual_orcamento_utilizado(self):
        """Calcula o percentual do orçamento mensal utilizado"""
        if self.orcamento_mensal <= 0:
            return 0

        utilizado = self.orcamento_utilizado_mes_atual
        return (utilizado / self.orcamento_mensal) * 100

    @property
    def saldo_orcamento_mensal(self):
        """Calcula o saldo restante do orçamento mensal"""
        return self.orcamento_mensal - self.orcamento_utilizado_mes_atual

    @property
    def status_orcamento(self):
        """Retorna o status do orçamento baseado no percentual utilizado"""
        percentual = self.percentual_orcamento_utilizado

        if percentual >= 100:
            return "estourado"
        elif percentual >= self.alerta_percentual:
            return "alerta"
        else:
            return "normal"

    def get_movimentacoes_mes(self, mes=None, ano=None):
        """Retorna as movimentações do mês especificado"""
        agora = timezone.now()
        if not mes:
            mes = agora.month
        if not ano:
            ano = agora.year

        return MovimentacaoFinanceira.objects.filter(
            centro_custo=self, data_movimentacao__month=mes, data_movimentacao__year=ano
        ).order_by("-data_movimentacao")


# ========== MODELOS DE PRODUTIVIDADE ==========


class CannedResponse(models.Model):
    """Respostas prontas / Macros para agentes"""

    titulo = models.CharField(max_length=200)
    corpo = models.TextField(help_text="Suporta variaveis: {{cliente_nome}}, {{ticket_numero}}, {{agente_nome}}")
    categoria = models.CharField(max_length=100, blank=True, db_index=True)
    atalho = models.CharField(max_length=50, blank=True, help_text="Atalho de teclado, ex: /saudacao")
    criado_por = models.ForeignKey(User, on_delete=models.CASCADE, related_name="canned_responses")
    compartilhado = models.BooleanField(default=True, help_text="Visivel para todos os agentes")
    uso_count = models.PositiveIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Resposta Pronta"
        verbose_name_plural = "Respostas Prontas"
        ordering = ["-uso_count", "titulo"]

    def __str__(self):
        return self.titulo

    def render(self, ticket=None, agente=None):
        """Renderiza o corpo substituindo variaveis"""
        text = self.corpo
        if ticket:
            text = text.replace("{{ticket_numero}}", ticket.numero or "")
            text = text.replace("{{cliente_nome}}", ticket.cliente.nome if ticket.cliente else "")
        if agente:
            text = text.replace("{{agente_nome}}", agente.get_full_name() or agente.username)
        return text


class TicketTemplate(models.Model):
    """Templates de ticket com pre-preenchimento"""

    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    titulo_padrao = models.CharField(max_length=200, blank=True)
    descricao_padrao = models.TextField(blank=True)
    categoria = models.ForeignKey(CategoriaTicket, on_delete=models.SET_NULL, null=True, blank=True)
    prioridade = models.CharField(max_length=10, choices=PrioridadeTicket.choices, default=PrioridadeTicket.MEDIA)
    tipo = models.CharField(max_length=15, choices=Ticket.TIPO_CHOICES, default="incidente")
    tags_padrao = models.CharField(max_length=500, blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Template de Ticket"
        verbose_name_plural = "Templates de Ticket"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class CustomField(models.Model):
    """Campos customizados para tickets"""

    FIELD_TYPES = [
        ("text", "Texto"),
        ("number", "Numero"),
        ("date", "Data"),
        ("select", "Selecao"),
        ("checkbox", "Checkbox"),
        ("textarea", "Area de texto"),
    ]
    nome = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110, unique=True)
    tipo = models.CharField(max_length=10, choices=FIELD_TYPES)
    obrigatorio = models.BooleanField(default=False)
    opcoes = models.JSONField(default=list, blank=True, help_text="Lista de opcoes para tipo select")
    placeholder = models.CharField(max_length=200, blank=True)
    ordem = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Campo Customizado"
        verbose_name_plural = "Campos Customizados"
        ordering = ["ordem"]

    def __str__(self):
        return self.nome


class TicketCustomFieldValue(models.Model):
    """Valor de campo customizado para um ticket"""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="custom_values")
    field = models.ForeignKey(CustomField, on_delete=models.CASCADE)
    value = models.TextField(blank=True)

    class Meta:
        verbose_name = "Valor de Campo Customizado"
        verbose_name_plural = "Valores de Campos Customizados"
        unique_together = ("ticket", "field")

    def __str__(self):
        return f"{self.field.nome}: {self.value}"


class StatusTransition(models.Model):
    """Regras de transicao de status validas"""

    from_status = models.CharField(max_length=20, choices=StatusTicket.choices)
    to_status = models.CharField(max_length=20, choices=StatusTicket.choices)
    requires_role = models.CharField(max_length=20, blank=True, help_text="Role necessaria: admin, supervisor, agente")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Transicao de Status"
        verbose_name_plural = "Transicoes de Status"
        unique_together = ("from_status", "to_status")

    def __str__(self):
        return f"{self.from_status} -> {self.to_status}"


# ===========================================================================
# FASE 4 — Webhooks, API Keys, Time Tracking, Tags, Portal Cliente
# ===========================================================================


class Tag(models.Model):
    """Tags reutilizaveis para tickets"""

    nome = models.CharField(max_length=50, unique=True)
    cor = models.CharField(max_length=7, default="#06b6d4", help_text="Hex color")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class WebhookEndpoint(models.Model):
    """Endpoints de webhook para notificacoes outbound"""

    EVENTS = [
        ("ticket_created", "Ticket Criado"),
        ("ticket_updated", "Ticket Atualizado"),
        ("ticket_resolved", "Ticket Resolvido"),
        ("ticket_closed", "Ticket Fechado"),
        ("ticket_assigned", "Ticket Atribuido"),
        ("sla_warning", "SLA Warning"),
        ("sla_breach", "SLA Breach"),
        ("comment_added", "Comentario Adicionado"),
    ]

    nome = models.CharField(max_length=100)
    url = models.URLField()
    secret = models.CharField(
        max_length=500, blank=True, help_text="HMAC secret para assinatura (armazenado criptografado)"
    )
    events = models.JSONField(default=list, help_text="Lista de eventos para notificar")
    headers = models.JSONField(default=dict, blank=True, help_text="Headers customizados")
    is_active = models.BooleanField(default=True)
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    failure_count = models.IntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Webhook Endpoint"
        verbose_name_plural = "Webhook Endpoints"
        constraints = [
            models.CheckConstraint(
                condition=Q(failure_count__gte=0),
                name="webhook_failure_count_gte_0",
            ),
        ]

    def save(self, *args, **kwargs):
        from ..utils.crypto import encrypt_value

        if self.secret and not self.secret.startswith("enc::"):
            self.secret = encrypt_value(self.secret)
        super().save(*args, **kwargs)

    def get_secret(self):
        """Retorna o secret descriptografado."""
        from ..utils.crypto import decrypt_value

        return decrypt_value(self.secret)

    def __str__(self):
        return f"{self.nome} ({self.url})"


class WebhookDelivery(models.Model):
    """Log de entregas de webhook"""

    webhook = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE, related_name="deliveries")
    event = models.CharField(max_length=50)
    payload = models.JSONField()
    response_status = models.IntegerField(null=True)
    response_body = models.TextField(blank=True)
    success = models.BooleanField(default=False)
    duration_ms = models.IntegerField(null=True)
    attempt = models.IntegerField(default=1)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Webhook Delivery"
        verbose_name_plural = "Webhook Deliveries"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["-criado_em"]),
            models.Index(fields=["webhook", "success"]),
        ]


class APIKey(models.Model):
    """Chave de API para integracoes de terceiros"""

    nome = models.CharField(max_length=100)
    key_hash = models.CharField(max_length=128, unique=True, db_index=True)
    prefix = models.CharField(max_length=8, unique=True, help_text="Primeiros 8 chars da chave")
    criado_por = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_keys")
    permissions = models.JSONField(default=list, help_text='Ex: ["tickets.read", "tickets.write"]')
    rate_limit = models.IntegerField(default=1000, help_text="Requests por dia")
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"
        constraints = [
            models.CheckConstraint(
                condition=Q(rate_limit__gt=0),
                name="apikey_rate_limit_gt_0",
            ),
        ]

    def __str__(self):
        return f"{self.nome} ({self.prefix}...)"

    @classmethod
    def generate_key(cls):
        import hashlib
        import secrets

        raw_key = secrets.token_urlsafe(48)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        prefix = raw_key[:8]
        return raw_key, key_hash, prefix

    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True


class TimeEntry(models.Model):
    """Registro de tempo gasto em tickets"""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="time_entries")
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="time_entries")
    minutos = models.PositiveIntegerField()
    descricao = models.TextField(blank=True)
    data = models.DateField(default=timezone.now)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de Tempo"
        verbose_name_plural = "Registros de Tempo"
        ordering = ["-data", "-criado_em"]

    def __str__(self):
        return f"{self.usuario} - {self.minutos}min em {self.ticket}"

    @property
    def horas(self):
        return round(self.minutos / 60, 1)


class Holiday(models.Model):
    """Feriados para calculo de SLA business hours"""

    nome = models.CharField(max_length=100)
    data = models.DateField(unique=True)
    recorrente = models.BooleanField(default=False, help_text="Repete anualmente")

    class Meta:
        verbose_name = "Feriado"
        verbose_name_plural = "Feriados"
        ordering = ["data"]

    def __str__(self):
        return f"{self.nome} ({self.data})"


class EscalationChain(models.Model):
    """Cadeia de escalonamento multi-nivel"""

    nome = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Cadeia de Escalonamento"
        verbose_name_plural = "Cadeias de Escalonamento"

    def __str__(self):
        return self.nome


class EscalationLevel(models.Model):
    """Nivel individual na cadeia de escalonamento"""

    chain = models.ForeignKey(EscalationChain, on_delete=models.CASCADE, related_name="levels")
    nivel = models.PositiveIntegerField()
    destino = models.ForeignKey(User, on_delete=models.CASCADE, help_text="Usuario que recebe a escalonamento")
    timeout_minutos = models.PositiveIntegerField(default=60, help_text="Minutos antes de escalar para proximo nivel")
    notificar_email = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Nivel de Escalonamento"
        verbose_name_plural = "Niveis de Escalonamento"
        ordering = ["chain", "nivel"]
        unique_together = ("chain", "nivel")
        constraints = [
            models.CheckConstraint(
                condition=Q(timeout_minutos__gt=0),
                name="escalation_timeout_gt_0",
            ),
        ]

    def __str__(self):
        return f"{self.chain.nome} - Nivel {self.nivel}: {self.destino}"


# ===========================================================================
# FASE 5 — IA & Automacao Inteligente
# ===========================================================================


class AIConfiguration(models.Model):
    """Configuracao de provedor de IA"""

    PROVIDERS = [
        ("openai", "OpenAI"),
        ("anthropic", "Anthropic (Claude)"),
        ("local", "Modelo Local"),
        ("google", "Google AI"),
    ]
    provider = models.CharField(max_length=20, choices=PROVIDERS, unique=True)
    api_key = models.CharField(max_length=500, help_text="Chave de API (armazenada criptografada)")
    model_name = models.CharField(max_length=100, default="gpt-4o-mini")
    temperature = models.FloatField(default=0.3)
    max_tokens = models.IntegerField(default=1000)
    is_active = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuracao de IA"
        verbose_name_plural = "Configuracoes de IA"

    def save(self, *args, **kwargs):
        from ..utils.crypto import encrypt_value

        if self.api_key and not self.api_key.startswith("enc::"):
            self.api_key = encrypt_value(self.api_key)
        super().save(*args, **kwargs)

    def get_api_key(self):
        """Retorna a chave de API descriptografada."""
        from ..utils.crypto import decrypt_value

        return decrypt_value(self.api_key)

    def __str__(self):
        return f"{self.get_provider_display()} - {self.model_name}"


class AIInteraction(models.Model):
    """Log de interacoes com IA"""

    TIPOS = [
        ("categorization", "Auto-categorizacao"),
        ("priority", "Predicao de Prioridade"),
        ("response", "Sugestao de Resposta"),
        ("summary", "Resumo de Conversa"),
        ("sentiment", "Analise de Sentimento"),
        ("duplicate", "Deteccao de Duplicata"),
        ("triage", "Auto-triagem"),
        ("chatbot", "Chatbot"),
    ]
    tipo = models.CharField(max_length=20, choices=TIPOS)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, null=True, blank=True, related_name="ai_interactions")
    input_text = models.TextField()
    output_text = models.TextField()
    confidence = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    provider = models.CharField(max_length=20, blank=True)
    model_used = models.CharField(max_length=100, blank=True)
    tokens_used = models.IntegerField(default=0)
    processing_time_ms = models.IntegerField(default=0)
    accepted_by_user = models.BooleanField(null=True, blank=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Interacao IA"
        verbose_name_plural = "Interacoes IA"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["tipo", "-criado_em"]),
            models.Index(fields=["ticket", "-criado_em"]),
        ]


class ScheduledRule(models.Model):
    """Regras agendadas (cron-based automation)"""

    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    cron_expression = models.CharField(max_length=50, help_text="Ex: 0 9 * * 1 (seg 9h)")
    conditions = models.JSONField(default=dict, help_text="Filtros para selecionar tickets")
    actions = models.JSONField(default=list, help_text="Acoes a executar")
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    run_count = models.IntegerField(default=0)
    max_executions_per_hour = models.IntegerField(default=100)
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Regra Agendada"
        verbose_name_plural = "Regras Agendadas"

    def __str__(self):
        return self.nome


# ===========================================================================
# FASE 6 — Analytics & Relatorios Enterprise
# ===========================================================================


class ScheduledReport(models.Model):
    """Relatorios agendados por email"""

    FREQUENCY_CHOICES = [
        ("daily", "Diario"),
        ("weekly", "Semanal"),
        ("monthly", "Mensal"),
    ]
    FORMAT_CHOICES = [
        ("pdf", "PDF"),
        ("excel", "Excel"),
        ("csv", "CSV"),
    ]
    nome = models.CharField(max_length=200)
    report_type = models.CharField(max_length=50, help_text="Tipo do relatorio (tickets, sla, financial, performance)")
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default="weekly")
    output_format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default="pdf")
    recipients = models.JSONField(default=list, help_text="Lista de emails destinatarios")
    filters = models.JSONField(default=dict, blank=True, help_text="Filtros customizados")
    is_active = models.BooleanField(default=True)
    last_sent = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Relatorio Agendado"
        verbose_name_plural = "Relatorios Agendados"

    def __str__(self):
        return f"{self.nome} ({self.get_frequency_display()})"


class SharedDashboard(models.Model):
    """Dashboards compartilhaveis via URL publica"""

    nome = models.CharField(max_length=200)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    dashboard_config = models.JSONField(default=dict, help_text="Configuracao dos widgets/metricas")
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    view_count = models.IntegerField(default=0)
    criado_por = models.ForeignKey(User, on_delete=models.CASCADE)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Dashboard Compartilhado"
        verbose_name_plural = "Dashboards Compartilhados"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.token:
            import secrets

            self.token = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)

    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True


class KPIAlert(models.Model):
    """Alertas de KPI — notifica quando metricas cruzam thresholds"""

    METRIC_CHOICES = [
        ("csat_below", "CSAT abaixo de"),
        ("sla_compliance_below", "SLA Compliance abaixo de"),
        ("queue_above", "Fila acima de"),
        ("avg_resolution_above", "Tempo medio resolucao acima de"),
        ("open_tickets_above", "Tickets abertos acima de"),
    ]
    nome = models.CharField(max_length=200)
    metric = models.CharField(max_length=30, choices=METRIC_CHOICES)
    threshold = models.DecimalField(max_digits=10, decimal_places=2, help_text="Valor limite para disparo")
    recipients = models.JSONField(default=list, help_text="Emails notificados")
    is_active = models.BooleanField(default=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    trigger_count = models.IntegerField(default=0)
    cooldown_minutes = models.IntegerField(default=60, help_text="Minutos entre alertas")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Alerta de KPI"
        verbose_name_plural = "Alertas de KPI"

    def __str__(self):
        return f"{self.nome}: {self.get_metric_display()} {self.threshold}"


# ===========================================================================
# FASE 7 — Omnichannel & Integracoes
# ===========================================================================


class EmailAccount(models.Model):
    """Conta de email para recebimento inbound"""

    PROTOCOL_CHOICES = [
        ("imap", "IMAP"),
        ("pop3", "POP3"),
    ]
    nome = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    protocol = models.CharField(max_length=4, choices=PROTOCOL_CHOICES, default="imap")
    server = models.CharField(max_length=255)
    port = models.IntegerField(default=993)
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=500, help_text="Senha (armazenada criptografada)")
    use_ssl = models.BooleanField(default=True)
    folder = models.CharField(max_length=100, default="INBOX")
    is_active = models.BooleanField(default=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    auto_create_ticket = models.BooleanField(default=True)
    default_category = models.ForeignKey(CategoriaTicket, on_delete=models.SET_NULL, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Conta de Email"
        verbose_name_plural = "Contas de Email"

    def save(self, *args, **kwargs):
        from ..utils.crypto import encrypt_value

        if self.password and not self.password.startswith("enc::"):
            self.password = encrypt_value(self.password)
        super().save(*args, **kwargs)

    def get_password(self):
        """Retorna a senha descriptografada."""
        from ..utils.crypto import decrypt_value

        return decrypt_value(self.password)

    def __str__(self):
        return f"{self.nome} ({self.email})"


class InboundEmail(models.Model):
    """Email recebido — pode gerar ticket ou interacao"""

    email_account = models.ForeignKey(EmailAccount, on_delete=models.CASCADE, related_name="emails")
    message_id = models.CharField(max_length=255, unique=True)
    from_email = models.EmailField()
    from_name = models.CharField(max_length=200, blank=True)
    subject = models.CharField(max_length=500)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    in_reply_to = models.CharField(max_length=255, blank=True)
    references = models.TextField(blank=True)
    ticket = models.ForeignKey(Ticket, on_delete=models.SET_NULL, null=True, blank=True, related_name="inbound_emails")
    processed = models.BooleanField(default=False, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Email Recebido"
        verbose_name_plural = "Emails Recebidos"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.from_email}: {self.subject}"


class EmailTemplate(models.Model):
    """Templates de email editaveis"""

    TEMPLATE_TYPES = [
        ("ticket_created", "Ticket Criado"),
        ("ticket_resolved", "Ticket Resolvido"),
        ("ticket_closed", "Ticket Fechado"),
        ("ticket_assigned", "Ticket Atribuido"),
        ("ticket_reply", "Resposta de Ticket"),
        ("sla_warning", "Aviso de SLA"),
        ("satisfaction_survey", "Pesquisa de Satisfacao"),
        ("welcome", "Boas-vindas"),
        ("password_reset", "Reset de Senha"),
    ]
    tipo = models.CharField(max_length=30, choices=TEMPLATE_TYPES, unique=True)
    assunto = models.CharField(max_length=200)
    corpo_html = models.TextField(help_text="HTML com variaveis: {{cliente_nome}}, {{ticket_numero}}, etc.")
    corpo_texto = models.TextField(blank=True, help_text="Versao texto plano")
    is_active = models.BooleanField(default=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Template de Email"
        verbose_name_plural = "Templates de Email"

    def __str__(self):
        return f"{self.get_tipo_display()}"

    def render(self, context: dict) -> tuple:
        """Renderiza template com variaveis"""
        subject = self.assunto
        body = self.corpo_html
        for key, value in context.items():
            placeholder = "{{" + key + "}}"
            subject = subject.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))
        return subject, body


# ===========================================================================
# FASE 9 — Features Premium
# ===========================================================================


class CustomerHealthScore(models.Model):
    """Score de saude do cliente — identifica clientes em risco"""

    cliente = models.OneToOneField(Cliente, on_delete=models.CASCADE, related_name="health_score")
    score = models.DecimalField(max_digits=5, decimal_places=2, default=100, help_text="0-100, onde 100 = saudavel")
    ticket_frequency_score = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    satisfaction_score = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    resolution_time_score = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    escalation_score = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    risk_level = models.CharField(
        max_length=10,
        choices=[
            ("low", "Baixo"),
            ("medium", "Medio"),
            ("high", "Alto"),
            ("critical", "Critico"),
        ],
        default="low",
        db_index=True,
    )
    last_calculated = models.DateTimeField(auto_now=True)
    factors = models.JSONField(default=dict, help_text="Detalhamento dos fatores")

    class Meta:
        verbose_name = "Health Score do Cliente"
        verbose_name_plural = "Health Scores dos Clientes"
        constraints = [
            models.CheckConstraint(
                condition=Q(score__gte=0, score__lte=100),
                name="health_score_0_100",
            ),
            models.CheckConstraint(
                condition=Q(ticket_frequency_score__gte=0, ticket_frequency_score__lte=100),
                name="health_ticket_freq_0_100",
            ),
            models.CheckConstraint(
                condition=Q(satisfaction_score__gte=0, satisfaction_score__lte=100),
                name="health_satisfaction_0_100",
            ),
            models.CheckConstraint(
                condition=Q(resolution_time_score__gte=0, resolution_time_score__lte=100),
                name="health_resolution_0_100",
            ),
            models.CheckConstraint(
                condition=Q(escalation_score__gte=0, escalation_score__lte=100),
                name="health_escalation_0_100",
            ),
        ]

    def __str__(self):
        return f"{self.cliente.nome}: {self.score:.0f} ({self.risk_level})"

    def calculate(self):
        """Recalcular score baseado em metricas"""
        from datetime import timedelta

        now = timezone.now()
        last_90d = now - timedelta(days=90)
        tickets = self.cliente.tickets.filter(criado_em__gte=last_90d)
        total = tickets.count()

        # Frequência de tickets (muitos tickets = score mais baixo)
        if total == 0:
            self.ticket_frequency_score = 100
        elif total <= 3:
            self.ticket_frequency_score = 90
        elif total <= 10:
            self.ticket_frequency_score = 70
        else:
            self.ticket_frequency_score = max(30, 100 - total * 3)

        # Satisfação
        try:
            from .satisfacao import AvaliacaoSatisfacao

            avg_sat = AvaliacaoSatisfacao.objects.filter(
                ticket__cliente=self.cliente, criado_em__gte=last_90d
            ).aggregate(avg=models.Avg("nota_atendimento"))["avg"]
            self.satisfaction_score = (avg_sat / 5 * 100) if avg_sat else 80
        except Exception:
            self.satisfaction_score = 80

        # Tempo de resolução
        resolved = tickets.filter(resolvido_em__isnull=False)
        if resolved.exists():
            avg_delta = resolved.aggregate(avg=models.Avg(models.F("resolvido_em") - models.F("criado_em")))["avg"]
            if avg_delta:
                hours = avg_delta.total_seconds() / 3600
                self.resolution_time_score = max(20, 100 - hours * 2)
            else:
                self.resolution_time_score = 80
        else:
            self.resolution_time_score = 80

        # Escalonamentos
        escalated = tickets.filter(is_escalated=True).count()
        self.escalation_score = max(20, 100 - escalated * 15)

        # Score final (média ponderada)
        self.score = (
            self.ticket_frequency_score * 0.2
            + self.satisfaction_score * 0.35
            + self.resolution_time_score * 0.25
            + self.escalation_score * 0.2
        )

        # Risk level
        if self.score >= 80:
            self.risk_level = "low"
        elif self.score >= 60:
            self.risk_level = "medium"
        elif self.score >= 40:
            self.risk_level = "high"
        else:
            self.risk_level = "critical"

        self.factors = {
            "ticket_frequency": self.ticket_frequency_score,
            "satisfaction": self.satisfaction_score,
            "resolution_time": self.resolution_time_score,
            "escalation": self.escalation_score,
        }
        self.save()


class GamificationBadge(models.Model):
    """Badges de gamificacao para agentes"""

    nome = models.CharField(max_length=100)
    descricao = models.TextField()
    icone = models.CharField(max_length=50, default="fas fa-trophy")
    cor = models.CharField(max_length=7, default="#06b6d4")
    criteria = models.JSONField(help_text="Criterios para ganhar: {'metric': 'tickets_resolved', 'threshold': 100}")
    pontos = models.IntegerField(default=10)

    class Meta:
        verbose_name = "Badge"
        verbose_name_plural = "Badges"

    def __str__(self):
        return self.nome


class AgentBadge(models.Model):
    """Badges conquistadas por agentes"""

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="badges")
    badge = models.ForeignKey(GamificationBadge, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Badge do Agente"
        verbose_name_plural = "Badges dos Agentes"
        unique_together = ("usuario", "badge")

    def __str__(self):
        return f"{self.usuario} - {self.badge.nome}"


class AgentLeaderboard(models.Model):
    """Leaderboard de agentes — atualizado periodicamente"""

    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name="leaderboard")
    pontos_total = models.IntegerField(default=0)
    tickets_resolved = models.IntegerField(default=0)
    avg_satisfaction = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    avg_resolution_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    first_response_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, help_text="% respondidos dentro do SLA"
    )
    rank = models.IntegerField(default=0, db_index=True)
    periodo = models.CharField(max_length=7, help_text="YYYY-MM", db_index=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Leaderboard"
        verbose_name_plural = "Leaderboard"
        ordering = ["-pontos_total"]
        constraints = [
            models.CheckConstraint(
                condition=Q(first_response_rate__gte=0, first_response_rate__lte=100),
                name="leaderboard_frr_0_100",
            ),
        ]

    def __str__(self):
        return f"#{self.rank} {self.usuario} - {self.pontos_total}pts"


# Os re-exports agora ficam em models/__init__.py
