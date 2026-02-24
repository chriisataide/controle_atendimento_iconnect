"""
Base de Conhecimento - Modelo principal do iConnect
ArtigoConhecimento e o modelo canonico de KB do sistema.
ChatbotKnowledgeBase (models_chatbot_ai.py) e usado para FAQ do chatbot.
KnowledgeBase (models.py) esta DEPRECADO.
"""
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User


class CategoriaConhecimento(models.Model):
    """Categorias para artigos da base de conhecimento"""
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    icone = models.CharField(max_length=50, default='help')
    cor = models.CharField(max_length=7, default='#e91e63')
    ordem = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Categoria de Conhecimento"
        verbose_name_plural = "Categorias de Conhecimento"
        ordering = ['ordem', 'nome']
        # Renomear tabela para evitar conflito com Categoria generico
        db_table = 'dashboard_categoriaconhecimento'

    def __str__(self):
        return self.nome


class ArtigoConhecimento(models.Model):
    """Artigo da base de conhecimento - modelo principal de KB"""
    titulo = models.CharField(max_length=200)
    conteudo = models.TextField()
    resumo = models.TextField(blank=True, help_text="Resumo curto para listagem")
    categoria = models.ForeignKey(
        CategoriaConhecimento, on_delete=models.CASCADE, related_name='artigos'
    )
    autor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='artigos_conhecimento')
    tags = models.CharField(max_length=500, blank=True)
    visualizacoes = models.IntegerField(default=0)
    util_sim = models.IntegerField(default=0)
    util_nao = models.IntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    publico = models.BooleanField(default=True)
    destaque = models.BooleanField(default=False, help_text="Exibir como artigo destaque")
    slug = models.SlugField(max_length=220, blank=True)

    class Meta:
        verbose_name = "Artigo de Conhecimento"
        verbose_name_plural = "Artigos de Conhecimento"
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['publico', '-criado_em']),
            models.Index(fields=['categoria', '-visualizacoes']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(visualizacoes__gte=0),
                name='artigo_visualizacoes_gte_0',
            ),
            models.CheckConstraint(
                condition=Q(util_sim__gte=0),
                name='artigo_util_sim_gte_0',
            ),
            models.CheckConstraint(
                condition=Q(util_nao__gte=0),
                name='artigo_util_nao_gte_0',
            ),
        ]

    def __str__(self):
        return self.titulo

    def taxa_utilidade(self):
        total = self.util_sim + self.util_nao
        return (self.util_sim / total * 100) if total > 0 else 0
