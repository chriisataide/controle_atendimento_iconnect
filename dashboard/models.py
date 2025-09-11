from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class Cliente(models.Model):
    nome = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    telefone = models.CharField(max_length=20, blank=True)
    empresa = models.CharField(max_length=100, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        
    def __str__(self):
        return self.nome


class StatusTicket(models.TextChoices):
    ABERTO = 'aberto', 'Aberto'
    EM_ANDAMENTO = 'em_andamento', 'Em Andamento'
    AGUARDANDO_CLIENTE = 'aguardando_cliente', 'Aguardando Cliente'
    RESOLVIDO = 'resolvido', 'Resolvido'
    FECHADO = 'fechado', 'Fechado'


class PrioridadeTicket(models.TextChoices):
    BAIXA = 'baixa', 'Baixa'
    MEDIA = 'media', 'Média'
    ALTA = 'alta', 'Alta'
    CRITICA = 'critica', 'Crítica'


class CategoriaTicket(models.Model):
    nome = models.CharField(max_length=50)
    descricao = models.TextField(blank=True)
    cor = models.CharField(max_length=7, default='#007bff')  # Hex color
    
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
    response_time_hours = models.IntegerField(help_text="Tempo de resposta em horas")
    resolution_time_hours = models.IntegerField(help_text="Tempo de resolução em horas", null=True, blank=True)
    business_hours_only = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Política de SLA"
        verbose_name_plural = "Políticas de SLA"
    
    def __str__(self):
        return self.name


class WorkflowRule(models.Model):
    """Regras de workflow automatizado"""
    EVENT_CHOICES = [
        ('ticket_created', 'Ticket Criado'),
        ('ticket_updated', 'Ticket Atualizado'),
        ('status_changed', 'Status Alterado'),
        ('agent_assigned', 'Agente Atribuído'),
        ('interaction_added', 'Interação Adicionada'),
        ('sla_warning', 'Aviso de SLA'),
        ('sla_breach', 'Violação de SLA'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    trigger_event = models.CharField(max_length=50, choices=EVENT_CHOICES)
    conditions = models.JSONField(help_text="Condições em formato JSON")
    actions = models.JSONField(help_text="Ações em formato JSON")
    priority = models.IntegerField(default=1, help_text="Prioridade de execução (1-10)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Regra de Workflow"
        verbose_name_plural = "Regras de Workflow"
        ordering = ['-priority', 'name']
    
    def __str__(self):
        return self.name


class Ticket(models.Model):
    numero = models.CharField(max_length=10, unique=True, blank=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='tickets')
    agente = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_agente')
    categoria = models.ForeignKey(CategoriaTicket, on_delete=models.SET_NULL, null=True, blank=True)
    
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    tags = models.CharField(max_length=500, blank=True, help_text="Tags separadas por vírgula")
    status = models.CharField(max_length=20, choices=StatusTicket.choices, default=StatusTicket.ABERTO)
    prioridade = models.CharField(max_length=10, choices=PrioridadeTicket.choices, default=PrioridadeTicket.MEDIA)
    origem = models.CharField(max_length=20, default='web', help_text="web, email, whatsapp, slack")
    
    # Campos relacionados ao SLA
    sla_deadline = models.DateTimeField(null=True, blank=True, help_text="Prazo de resposta SLA")
    first_response_at = models.DateTimeField(null=True, blank=True)
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    resolvido_em = models.DateTimeField(null=True, blank=True)
    fechado_em = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"
        ordering = ['-criado_em']
    
    def save(self, *args, **kwargs):
        if not self.numero:
            # Gerar número do ticket automaticamente
            import random
            import string
            self.numero = ''.join(random.choices(string.digits, k=4))
            # Verificar se já existe e gerar novo se necessário
            while Ticket.objects.filter(numero=self.numero).exists():
                self.numero = ''.join(random.choices(string.digits, k=4))
        
        # Atualizar timestamps baseado no status
        if self.status == StatusTicket.RESOLVIDO and not self.resolvido_em:
            self.resolvido_em = timezone.now()
        elif self.status == StatusTicket.FECHADO and not self.fechado_em:
            self.fechado_em = timezone.now()
            
        super().save(*args, **kwargs)
    
    def get_tags_list(self):
        """Retorna lista de tags"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []
    
    def __str__(self):
        return f"#{self.numero} - {self.titulo}"


class TicketAnexo(models.Model):
    """Modelo para anexos dos tickets"""
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='anexos')
    arquivo = models.FileField(upload_to='tickets/anexos/%Y/%m/')
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


class InteracaoTicket(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='interacoes')
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    mensagem = models.TextField()
    eh_publico = models.BooleanField(default=True)  # Visível para o cliente
    criado_em = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Interação"
        verbose_name_plural = "Interações"
        ordering = ['criado_em']
    
    def __str__(self):
        return f"Interação em {self.ticket.numero} por {self.usuario.username}"


class StatusAgente(models.TextChoices):
    ONLINE = 'online', 'Online'
    OCUPADO = 'ocupado', 'Ocupado'
    AUSENTE = 'ausente', 'Ausente'
    OFFLINE = 'offline', 'Offline'


class PerfilAgente(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=StatusAgente.choices, default=StatusAgente.OFFLINE)
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
            status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO, StatusTicket.AGUARDANDO_CLIENTE]
        ).count()


class PerfilUsuario(models.Model):
    """Modelo para estender as informações de perfil do usuário"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    
    # Informações pessoais
    telefone = models.CharField(max_length=20, blank=True, verbose_name="Telefone")
    telefone_alternativo = models.CharField(max_length=20, blank=True, verbose_name="Telefone Alternativo")
    
    # Endereço
    endereco = models.CharField(max_length=200, blank=True, verbose_name="Endereço")
    cidade = models.CharField(max_length=100, blank=True, verbose_name="Cidade")
    estado = models.CharField(max_length=2, blank=True, verbose_name="Estado")
    cep = models.CharField(max_length=9, blank=True, verbose_name="CEP")
    
    # Informações profissionais
    cargo = models.CharField(max_length=100, blank=True, verbose_name="Cargo")
    departamento = models.CharField(max_length=3, blank=True, choices=[
        ('TI', 'Tecnologia da Informação'),
        ('SUP', 'Suporte Técnico'),
        ('RH', 'Recursos Humanos'),
        ('FIN', 'Financeiro'),
        ('OPS', 'Operações'),
        ('COM', 'Comercial'),
    ], verbose_name="Departamento")
    bio = models.TextField(blank=True, verbose_name="Bio Profissional")
    
    # Avatar
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Foto de Perfil")
    
    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuários"
    
    def __str__(self):
        return f"Perfil de {self.user.get_full_name() or self.user.username}"
    
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
            self.cargo
        ]
        
        campos_preenchidos = sum(1 for campo in campos_obrigatorios if campo and campo.strip())
        return round((campos_preenchidos / len(campos_obrigatorios)) * 100)


# ========== NOVOS MODELOS PARA RECURSOS AVANÇADOS ==========

class SLAViolation(models.Model):
    """Registro de violações de SLA"""
    VIOLATION_TYPES = [
        ('deadline_missed', 'Prazo Perdido'),
        ('escalation_failed', 'Falha na Escalação'),
        ('response_delayed', 'Resposta Atrasada'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Baixa'),
        ('medium', 'Média'),
        ('high', 'Alta'),
        ('critical', 'Crítica'),
    ]
    
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='sla_violations')
    violation_type = models.CharField(max_length=20, choices=VIOLATION_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default='medium')
    expected_deadline = models.DateTimeField()
    actual_time = models.DateTimeField()
    time_exceeded = models.DurationField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Violação de SLA"
        verbose_name_plural = "Violações de SLA"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Violação SLA - Ticket #{self.ticket.numero}"


class WorkflowExecution(models.Model):
    """Registro de execuções de workflow"""
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='workflow_executions')
    rule = models.ForeignKey(WorkflowRule, on_delete=models.CASCADE)
    trigger_event = models.CharField(max_length=50)
    execution_result = models.JSONField()
    executed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    execution_time = models.DurationField(null=True, blank=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Execução de Workflow"
        verbose_name_plural = "Execuções de Workflow"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Execução {self.rule.name} - Ticket #{self.ticket.numero}"


class NotificationLog(models.Model):
    """Log de notificações enviadas"""
    NOTIFICATION_TYPES = [
        ('email', 'Email'),
        ('slack', 'Slack'),
        ('whatsapp', 'WhatsApp'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('sent', 'Enviado'),
        ('delivered', 'Entregue'),
        ('failed', 'Falhou'),
        ('bounced', 'Rejeitado'),
    ]
    
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    recipient = models.CharField(max_length=200)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    event_type = models.CharField(max_length=50)
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    external_id = models.CharField(max_length=100, blank=True)  # ID do serviço externo
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Log de Notificação"
        verbose_name_plural = "Logs de Notificações"
        ordering = ['-created_at']
    
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
    """Base de conhecimento para chatbot"""
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
        verbose_name = "Base de Conhecimento"
        verbose_name_plural = "Base de Conhecimento"
        ordering = ['-view_count', '-created_at']
    
    def __str__(self):
        return self.title


class SystemMetrics(models.Model):
    """Métricas do sistema para dashboard executivo"""
    date = models.DateField(unique=True)
    total_tickets = models.IntegerField(default=0)
    new_tickets = models.IntegerField(default=0)
    resolved_tickets = models.IntegerField(default=0)
    sla_compliance_rate = models.FloatField(default=0.0)
    avg_resolution_time = models.FloatField(default=0.0)  # em horas
    customer_satisfaction = models.FloatField(default=0.0)
    agent_productivity = models.JSONField(default=dict)  # métricas por agente
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Métricas do Sistema"
        verbose_name_plural = "Métricas do Sistema"
        ordering = ['-date']
    
    def __str__(self):
        return f"Métricas {self.date}"


class Notification(models.Model):
    """Notificações do sistema em tempo real"""
    NOTIFICATION_TYPES = [
        ('new_ticket', 'Novo Ticket'),
        ('ticket_assigned', 'Ticket Atribuído'),
        ('ticket_status_change', 'Mudança de Status'),
        ('sla_warning', 'Alerta de SLA'),
        ('new_interaction', 'Nova Interação'),
        ('system_alert', 'Alerta do Sistema'),
    ]
    
    COLOR_CHOICES = [
        ('primary', 'Primária'),
        ('secondary', 'Secundária'),
        ('success', 'Sucesso'),
        ('danger', 'Perigo'),
        ('warning', 'Aviso'),
        ('info', 'Informação'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    icon = models.CharField(max_length=50, default='notifications')
    color = models.CharField(max_length=20, choices=COLOR_CHOICES, default='primary')
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)  # dados extras
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['read', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    def mark_as_read(self):
        """Marca a notificação como lida"""
        if not self.read:
            self.read = True
            self.read_at = timezone.now()
            self.save(update_fields=['read', 'read_at'])
