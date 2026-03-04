# Sistema de Auto-atribuição Inteligente
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class SkillAgent(models.Model):
    """Skills/Competências dos Agentes"""

    agente = models.ForeignKey(User, on_delete=models.CASCADE)
    skill = models.CharField(max_length=100)  # Ex: 'rede', 'email', 'hardware'
    nivel = models.IntegerField(choices=[(1, "Básico"), (2, "Intermediário"), (3, "Avançado")])
    certificado = models.BooleanField(default=False)

    class Meta:
        unique_together = ["agente", "skill"]


class RegraAtribuicao(models.Model):
    """Regras para auto-atribuição de tickets"""

    nome = models.CharField(max_length=100)
    categoria = models.CharField(max_length=100, blank=True)
    prioridade = models.CharField(max_length=20, blank=True)
    palavras_chave = models.TextField(blank=True, help_text="Uma por linha")
    skill_requerida = models.CharField(max_length=100, blank=True)
    nivel_minimo = models.IntegerField(default=1)
    agente_especifico = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    ativa = models.BooleanField(default=True)
    prioridade_regra = models.IntegerField(default=0)

    class Meta:
        ordering = ["-prioridade_regra"]


class CargoTrabalho(models.Model):
    """Carga de trabalho dos agentes"""

    agente = models.OneToOneField(User, on_delete=models.CASCADE)
    tickets_abertos = models.IntegerField(default=0)
    capacidade_maxima = models.IntegerField(default=10)
    disponivel = models.BooleanField(default=True)
    ultima_atribuicao = models.DateTimeField(null=True, blank=True)

    @property
    def percentual_ocupacao(self):
        return (self.tickets_abertos / self.capacidade_maxima) * 100 if self.capacidade_maxima > 0 else 100

    @property
    def pode_receber_ticket(self):
        return self.disponivel and self.tickets_abertos < self.capacidade_maxima


def auto_assign_ticket(ticket):
    """Função para auto-atribuir tickets"""

    # 1. Buscar regras aplicáveis
    regras = RegraAtribuicao.objects.filter(ativa=True)

    for regra in regras:
        if regra_se_aplica(ticket, regra):
            # 2. Buscar agentes disponíveis
            if regra.agente_especifico:
                agentes_candidatos = [regra.agente_especifico]
            else:
                agentes_candidatos = buscar_agentes_por_skill(regra.skill_requerida, regra.nivel_minimo)

            # 3. Filtrar por disponibilidade
            agentes_disponiveis = []
            for agente in agentes_candidatos:
                carga, created = CargoTrabalho.objects.get_or_create(agente=agente)
                if carga.pode_receber_ticket:
                    agentes_disponiveis.append((agente, carga))

            if agentes_disponiveis:
                # 4. Escolher agente com menor carga
                agente_escolhido = min(agentes_disponiveis, key=lambda x: x[1].percentual_ocupacao)[0]

                # 5. Atribuir ticket
                ticket.agente = agente_escolhido
                ticket.save()

                # 6. Atualizar carga de trabalho
                carga = CargoTrabalho.objects.get(agente=agente_escolhido)
                carga.tickets_abertos += 1
                carga.ultima_atribuicao = timezone.now()
                carga.save()

                return agente_escolhido

    return None


def regra_se_aplica(ticket, regra):
    """Verifica se uma regra se aplica ao ticket"""
    # Verificar categoria
    if regra.categoria and ticket.categoria != regra.categoria:
        return False

    # Verificar prioridade
    if regra.prioridade and ticket.prioridade != regra.prioridade:
        return False

    # Verificar palavras-chave
    if regra.palavras_chave:
        palavras = regra.palavras_chave.strip().split("\n")
        texto_ticket = f"{ticket.titulo} {ticket.descricao}".lower()
        if not any(palavra.lower() in texto_ticket for palavra in palavras):
            return False

    return True


def buscar_agentes_por_skill(skill, nivel_minimo):
    """Busca agentes com a skill requerida"""
    if not skill:
        return User.objects.filter(is_staff=True, is_active=True)

    return User.objects.filter(skillagent__skill=skill, skillagent__nivel__gte=nivel_minimo, is_active=True).distinct()
