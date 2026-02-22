"""
Modelos para Sistema de Chat Integrado Avançado
iConnect - Sistema de Atendimento Competitivo
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import FileExtensionValidator


class ChatRoom(models.Model):
    """
    Sala de chat entre agentes e clientes
    """
    ROOM_TYPES = (
        ('support', 'Suporte Técnico'),
        ('sales', 'Vendas'),
        ('general', 'Geral'),
        ('group', 'Grupo'),
        ('private', 'Privado'),
    )
    
    STATUS_CHOICES = (
        ('active', 'Ativo'),
        ('paused', 'Pausado'),
        ('closed', 'Fechado'),
        ('archived', 'Arquivado'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name="Nome da Sala")
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default='support', db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
    
    # Relacionamentos
    ticket = models.ForeignKey('Ticket', on_delete=models.CASCADE, null=True, blank=True,
                              verbose_name="Ticket Relacionado")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_chat_rooms')
    
    # Configurações
    is_private = models.BooleanField(default=True, verbose_name="Chat Privado")
    max_participants = models.PositiveIntegerField(default=10, verbose_name="Máximo de Participantes")
    allow_file_upload = models.BooleanField(default=True, verbose_name="Permitir Upload de Arquivos")
    allow_voice_messages = models.BooleanField(default=True, verbose_name="Permitir Mensagens de Voz")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(default=timezone.now)
    
    # Estatísticas
    message_count = models.PositiveIntegerField(default=0)
    participant_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = "Sala de Chat"
        verbose_name_plural = "Salas de Chat"
        ordering = ['-last_activity']
    
    def __str__(self):
        return f"{self.name} ({self.get_room_type_display()})"
    
    @property
    def active_participants(self):
        """Retorna participantes ativos"""
        return self.participants.filter(is_active=True, left_at__isnull=True)
    
    @property
    def is_group_chat(self):
        """Verifica se é chat em grupo"""
        return self.room_type == 'group' or self.participant_count > 2


class ChatParticipant(models.Model):
    """
    Participantes de uma sala de chat
    """
    ROLES = (
        ('admin', 'Administrador'),
        ('agent', 'Agente'),
        ('client', 'Cliente'),
        ('observer', 'Observador'),
    )
    
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLES, default='client')
    
    # Status
    is_active = models.BooleanField(default=True, db_index=True)
    is_typing = models.BooleanField(default=False)
    is_online = models.BooleanField(default=False, db_index=True)
    
    # Timestamps
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(default=timezone.now)
    last_read_message = models.ForeignKey('ChatMessage', on_delete=models.SET_NULL, 
                                         null=True, blank=True, related_name='read_by_participants')
    
    # Configurações
    notifications_enabled = models.BooleanField(default=True)
    sound_enabled = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Participante do Chat"
        verbose_name_plural = "Participantes do Chat"
        unique_together = ('room', 'user')
        ordering = ['joined_at']
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} in {self.room.name}"
    
    @property
    def unread_count(self):
        """Conta mensagens não lidas"""
        if not self.last_read_message:
            return self.room.messages.count()
        
        return self.room.messages.filter(
            created_at__gt=self.last_read_message.created_at
        ).exclude(sender=self.user).count()


class ChatMessage(models.Model):
    """
    Mensagens de chat com recursos avançados
    """
    MESSAGE_TYPES = (
        ('text', 'Texto'),
        ('file', 'Arquivo'),
        ('image', 'Imagem'),
        ('voice', 'Voz'),
        ('video', 'Vídeo'),
        ('system', 'Sistema'),
        ('location', 'Localização'),
        ('contact', 'Contato'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Conteúdo
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField(verbose_name="Conteúdo da Mensagem")
    formatted_content = models.TextField(blank=True, verbose_name="Conteúdo Formatado")
    
    # Arquivos
    file = models.FileField(
        upload_to='chat/files/%Y/%m/',
        null=True, blank=True,
        validators=[FileExtensionValidator(allowed_extensions=[
            'jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 
            'txt', 'mp3', 'mp4', 'wav', 'ogg'
        ])]
    )
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(default=0, help_text="Tamanho em bytes")
    
    # Metadata
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='replies', verbose_name="Resposta a")
    forwarded_from = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='forwards', verbose_name="Encaminhada de")
    
    # Status
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    is_important = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    
    # Entrega e leitura
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = "Mensagem de Chat"
        verbose_name_plural = "Mensagens de Chat"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['room', 'created_at']),
            models.Index(fields=['sender', 'created_at']),
        ]
    
    def __str__(self):
        return f"Mensagem de {self.sender.username} em {self.room.name}"
    
    @property
    def is_file_message(self):
        """Verifica se é mensagem com arquivo"""
        return self.message_type in ['file', 'image', 'voice', 'video']
    
    @property
    def file_extension(self):
        """Retorna extensão do arquivo"""
        if self.file:
            return self.file.name.split('.')[-1].lower()
        return None
    
    def mark_as_read_by(self, user):
        """Marca mensagem como lida por usuário"""
        read_receipt, created = ChatMessageReadReceipt.objects.get_or_create(
            message=self,
            user=user,
            defaults={'read_at': timezone.now()}
        )
        
        if created:
            self.read_count += 1
            self.save(update_fields=['read_count'])
        
        return read_receipt


class ChatMessageReadReceipt(models.Model):
    """
    Confirmação de leitura de mensagens
    """
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='read_receipts')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Confirmação de Leitura"
        verbose_name_plural = "Confirmações de Leitura"
        unique_together = ('message', 'user')
        ordering = ['read_at']
    
    def __str__(self):
        return f"{self.user.username} leu mensagem {self.message.id}"


class ChatReaction(models.Model):
    """
    Reações/Emojis em mensagens
    """
    REACTIONS = (
        ('👍', 'Like'),
        ('❤️', 'Love'),
        ('😂', 'Laugh'),
        ('😮', 'Surprise'),
        ('😢', 'Sad'),
        ('😡', 'Angry'),
        ('👏', 'Clap'),
        ('🔥', 'Fire'),
    )
    
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reaction = models.CharField(max_length=10, choices=REACTIONS)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Reação"
        verbose_name_plural = "Reações"
        unique_together = ('message', 'user', 'reaction')
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.user.username} reagiu {self.reaction} à mensagem {self.message.id}"


class ChatSettings(models.Model):
    """
    Configurações de chat por usuário
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='chat_settings')
    
    # Notificações
    notifications_enabled = models.BooleanField(default=True)
    sound_notifications = models.BooleanField(default=True)
    desktop_notifications = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=False)
    
    # Aparência
    theme = models.CharField(max_length=20, default='light', 
                           choices=[('light', 'Claro'), ('dark', 'Escuro'), ('auto', 'Automático')])
    font_size = models.CharField(max_length=10, default='medium',
                               choices=[('small', 'Pequeno'), ('medium', 'Médio'), ('large', 'Grande')])
    
    # Privacidade
    show_online_status = models.BooleanField(default=True)
    show_typing_indicator = models.BooleanField(default=True)
    show_read_receipts = models.BooleanField(default=True)
    
    # Auto-responses
    auto_response_enabled = models.BooleanField(default=False)
    auto_response_message = models.TextField(blank=True, max_length=500)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configurações de Chat"
        verbose_name_plural = "Configurações de Chat"
    
    def __str__(self):
        return f"Configurações de {self.user.username}"


class ChatBot(models.Model):
    """
    Configurações do ChatBot AI
    """
    name = models.CharField(max_length=100, default="iConnect Assistant")
    is_active = models.BooleanField(default=True)
    
    # Configurações de comportamento
    greeting_message = models.TextField(default="Olá! Sou o assistente virtual da iConnect. Como posso ajudar?")
    fallback_message = models.TextField(default="Desculpe, não entendi. Posso conectá-lo com um agente humano?")
    handoff_keywords = models.TextField(
        default="agente,humano,pessoa,atendente",
        help_text="Palavras-chave separadas por vírgula para transferir para agente humano"
    )
    
    # Configurações de integração
    openai_model = models.CharField(max_length=50, default="gpt-3.5-turbo")
    max_tokens = models.PositiveIntegerField(default=150)
    temperature = models.FloatField(default=0.7)
    
    # Horários de funcionamento
    business_hours_start = models.TimeField(default="08:00")
    business_hours_end = models.TimeField(default="18:00")
    weekend_active = models.BooleanField(default=False)
    
    # Estatísticas
    total_conversations = models.PositiveIntegerField(default=0)
    successful_resolutions = models.PositiveIntegerField(default=0)
    handoffs_to_agents = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "ChatBot"
        verbose_name_plural = "ChatBots"
    
    def __str__(self):
        return self.name
    
    @property
    def success_rate(self):
        """Taxa de sucesso do bot"""
        if self.total_conversations == 0:
            return 0
        return (self.successful_resolutions / self.total_conversations) * 100
