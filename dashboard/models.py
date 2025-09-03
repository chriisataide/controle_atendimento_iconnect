from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


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


class Ticket(models.Model):
    numero = models.CharField(max_length=10, unique=True, blank=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    agente = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    categoria = models.ForeignKey(CategoriaTicket, on_delete=models.CASCADE)
    
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    status = models.CharField(max_length=20, choices=StatusTicket.choices, default=StatusTicket.ABERTO)
    prioridade = models.CharField(max_length=10, choices=PrioridadeTicket.choices, default=PrioridadeTicket.MEDIA)
    
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
    
    def __str__(self):
        return f"#{self.numero} - {self.titulo}"


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
