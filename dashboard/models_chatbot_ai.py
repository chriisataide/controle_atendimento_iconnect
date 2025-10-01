from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class ChatbotKnowledgeBase(models.Model):
    """Base de conhecimento do chatbot"""
    categoria = models.CharField(max_length=100, verbose_name='Categoria')
    pergunta = models.TextField(verbose_name='Pergunta')
    resposta = models.TextField(verbose_name='Resposta')
    tags = models.CharField(max_length=200, blank=True, verbose_name='Tags (separadas por vírgula)')
    confianca = models.FloatField(default=1.0, verbose_name='Nível de Confiança')
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        verbose_name = 'Base de Conhecimento'
        verbose_name_plural = 'Base de Conhecimento'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['categoria', 'ativo']),
            models.Index(fields=['tags']),
        ]
    
    def __str__(self):
        return f"{self.categoria}: {self.pergunta[:50]}..."


class ChatbotConversation(models.Model):
    """Conversas do chatbot"""
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Usuário')
    session_id = models.CharField(max_length=100, verbose_name='Session ID')
    iniciada_em = models.DateTimeField(auto_now_add=True, verbose_name='Iniciada em')
    finalizada_em = models.DateTimeField(null=True, blank=True, verbose_name='Finalizada em')
    ativa = models.BooleanField(default=True, verbose_name='Ativa')
    contexto = models.JSONField(default=dict, verbose_name='Contexto da Conversa')
    
    class Meta:
        verbose_name = 'Conversa Chatbot'
        verbose_name_plural = 'Conversas Chatbot'
        ordering = ['-iniciada_em']
        indexes = [
            models.Index(fields=['session_id', 'ativa']),
            models.Index(fields=['usuario', '-iniciada_em']),
        ]
    
    def __str__(self):
        return f"Conversa {self.uuid} - {self.session_id}"


class ChatbotMessage(models.Model):
    """Mensagens da conversa do chatbot"""
    TIPOS_MENSAGEM = [
        ('user', 'Usuário'),
        ('bot', 'Bot'),
        ('system', 'Sistema'),
    ]
    
    conversa = models.ForeignKey(ChatbotConversation, on_delete=models.CASCADE, related_name='mensagens', verbose_name='Conversa')
    tipo = models.CharField(max_length=10, choices=TIPOS_MENSAGEM, verbose_name='Tipo')
    conteudo = models.TextField(verbose_name='Conteúdo')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Timestamp')
    confianca = models.FloatField(null=True, blank=True, verbose_name='Confiança da Resposta')
    metadados = models.JSONField(default=dict, verbose_name='Metadados')
    
    class Meta:
        verbose_name = 'Mensagem Chatbot'
        verbose_name_plural = 'Mensagens Chatbot'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['conversa', 'timestamp']),
            models.Index(fields=['tipo', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.get_tipo_display()}: {self.conteudo[:50]}..."


class ChatbotAnalytics(models.Model):
    """Analytics do chatbot"""
    data = models.DateField(verbose_name='Data')
    total_conversas = models.IntegerField(default=0, verbose_name='Total de Conversas')
    total_mensagens = models.IntegerField(default=0, verbose_name='Total de Mensagens')
    respostas_automaticas = models.IntegerField(default=0, verbose_name='Respostas Automáticas')
    transferencias_humano = models.IntegerField(default=0, verbose_name='Transferências para Humano')
    satisfacao_media = models.FloatField(null=True, blank=True, verbose_name='Satisfação Média')
    tempo_resposta_medio = models.FloatField(null=True, blank=True, verbose_name='Tempo Resposta Médio (s)')
    
    class Meta:
        verbose_name = 'Analytics Chatbot'
        verbose_name_plural = 'Analytics Chatbot'
        ordering = ['-data']
        unique_together = ['data']
        indexes = [
            models.Index(fields=['data']),
        ]
    
    def __str__(self):
        return f"Analytics {self.data}"


class ChatbotTraining(models.Model):
    """Dados de treinamento do chatbot"""
    pergunta_original = models.TextField(verbose_name='Pergunta Original')
    resposta_bot = models.TextField(verbose_name='Resposta do Bot')
    resposta_esperada = models.TextField(blank=True, verbose_name='Resposta Esperada')
    feedback_positivo = models.BooleanField(null=True, blank=True, verbose_name='Feedback Positivo')
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Usuário')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    processado = models.BooleanField(default=False, verbose_name='Processado')
    
    class Meta:
        verbose_name = 'Treinamento Chatbot'
        verbose_name_plural = 'Treinamentos Chatbot'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['processado', '-criado_em']),
            models.Index(fields=['feedback_positivo']),
        ]
    
    def __str__(self):
        return f"Treinamento: {self.pergunta_original[:50]}..."


class ChatbotConfiguration(models.Model):
    """Configurações do chatbot"""
    nome = models.CharField(max_length=100, verbose_name='Nome')
    valor = models.TextField(verbose_name='Valor')
    tipo = models.CharField(max_length=20, choices=[
        ('string', 'String'),
        ('integer', 'Inteiro'),
        ('float', 'Decimal'),
        ('boolean', 'Booleano'),
        ('json', 'JSON'),
    ], verbose_name='Tipo')
    descricao = models.TextField(blank=True, verbose_name='Descrição')
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')
    
    class Meta:
        verbose_name = 'Configuração Chatbot'
        verbose_name_plural = 'Configurações Chatbot'
        unique_together = ['nome']
        ordering = ['nome']
    
    def __str__(self):
        return self.nome
    
    def get_value(self):
        """Retorna o valor na tipagem correta"""
        if self.tipo == 'integer':
            return int(self.valor)
        elif self.tipo == 'float':
            return float(self.valor)
        elif self.tipo == 'boolean':
            return self.valor.lower() in ['true', '1', 'yes', 'sim']
        elif self.tipo == 'json':
            import json
            return json.loads(self.valor)
        return self.valor