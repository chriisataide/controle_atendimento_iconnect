# Sistema de IA para Chatbot
from django.db import models
from textblob import TextBlob
import re

class IntentClassifier:
    """Classificador de intenções para o chatbot"""
    
    INTENTS = {
        'problema_tecnico': [
            'não funciona', 'erro', 'bug', 'falha', 'quebrou', 'parou',
            'lento', 'travando', 'não abre', 'não carrega'
        ],
        'duvida': [
            'como', 'onde', 'quando', 'por que', 'o que é', 'ajuda',
            'tutorial', 'explicar', 'dúvida'
        ],
        'solicitacao': [
            'preciso', 'quero', 'gostaria', 'solicito', 'criar',
            'adicionar', 'incluir', 'novo'
        ],
        'reclamacao': [
            'insatisfeito', 'ruim', 'péssimo', 'reclamação', 'problema',
            'indignado', 'revoltado'
        ]
    }
    
    @classmethod
    def classify_message(cls, message):
        message_lower = message.lower()
        scores = {}
        
        for intent, keywords in cls.INTENTS.items():
            score = sum(1 for keyword in keywords if keyword in message_lower)
            if score > 0:
                scores[intent] = score
        
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        return 'geral'
    
    @classmethod
    def get_sentiment(cls, message):
        """Análise de sentimento básica"""
        blob = TextBlob(message)
        polarity = blob.sentiment.polarity
        
        if polarity > 0.1:
            return 'positivo'
        elif polarity < -0.1:
            return 'negativo'
        return 'neutro'

class ChatbotResponse(models.Model):
    intent = models.CharField(max_length=50)
    resposta = models.TextField()
    ativa = models.BooleanField(default=True)
    prioridade = models.IntegerField(default=0)  # Maior número = maior prioridade
    
    class Meta:
        ordering = ['-prioridade']

class ChatbotInteraction(models.Model):
    sessao_id = models.CharField(max_length=100)
    usuario = models.CharField(max_length=100, blank=True)
    mensagem_usuario = models.TextField()
    intent_detectado = models.CharField(max_length=50)
    sentimento = models.CharField(max_length=20)
    resposta_bot = models.TextField()
    satisfacao = models.IntegerField(null=True, blank=True)  # 1-5
    criado_em = models.DateTimeField(auto_now_add=True)
