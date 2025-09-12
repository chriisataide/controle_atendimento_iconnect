# Modelo para Base de Conhecimento
from django.db import models
from django.contrib.auth.models import User

class Categoria(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    icone = models.CharField(max_length=50, default='help')
    cor = models.CharField(max_length=7, default='#e91e63')
    
    class Meta:
        verbose_name_plural = "Categorias"

class ArtigoConhecimento(models.Model):
    titulo = models.CharField(max_length=200)
    conteudo = models.TextField()
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    autor = models.ForeignKey(User, on_delete=models.CASCADE)
    tags = models.CharField(max_length=500, blank=True)
    visualizacoes = models.IntegerField(default=0)
    util_sim = models.IntegerField(default=0)
    util_nao = models.IntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    publico = models.BooleanField(default=True)
    
    def taxa_utilidade(self):
        total = self.util_sim + self.util_nao
        return (self.util_sim / total * 100) if total > 0 else 0
