# Sistema de Satisfação
from django.db import models

class AvaliacaoSatisfacao(models.Model):
    NOTAS = [(i, str(i)) for i in range(1, 6)]  # 1 a 5 estrelas
    
    ticket = models.OneToOneField('Ticket', on_delete=models.CASCADE)
    nota_atendimento = models.IntegerField(choices=NOTAS)
    nota_resolucao = models.IntegerField(choices=NOTAS)
    nota_tempo = models.IntegerField(choices=NOTAS)
    comentario = models.TextField(blank=True)
    avaliado_em = models.DateTimeField(auto_now_add=True)
    
    @property
    def media_geral(self):
        return (self.nota_atendimento + self.nota_resolucao + self.nota_tempo) / 3
    
    def __str__(self):
        return f"Avaliação Ticket #{self.ticket.id} - {self.media_geral:.1f}★"

class PesquisaSatisfacao(models.Model):
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    ativa = models.BooleanField(default=True)
    criada_em = models.DateTimeField(auto_now_add=True)

class PerguntaPesquisa(models.Model):
    TIPOS = [
        ('rating', 'Avaliação (1-5)'),
        ('nps', 'NPS (0-10)'),
        ('multipla', 'Múltipla Escolha'),
        ('texto', 'Texto Livre'),
    ]
    
    pesquisa = models.ForeignKey(PesquisaSatisfacao, on_delete=models.CASCADE)
    pergunta = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPOS)
    obrigatoria = models.BooleanField(default=False)
    ordem = models.IntegerField(default=0)
