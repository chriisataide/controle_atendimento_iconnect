"""
Factories e helpers reutilizáveis para todos os testes do iConnect.
Usa factory_boy para geração de dados de teste.
"""

import factory
from django.contrib.auth.models import User
from factory.django import DjangoModelFactory

from dashboard.models import (
    CategoriaTicket,
    Cliente,
    InteracaoTicket,
    PerfilAgente,
    PrioridadeTicket,
    SLAPolicy,
    StatusTicket,
    Ticket,
    WorkflowRule,
)


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@test.com")
    first_name = factory.Faker("first_name", locale="pt_BR")
    last_name = factory.Faker("last_name", locale="pt_BR")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")
    is_active = True


class AdminFactory(UserFactory):
    is_staff = True
    is_superuser = True
    username = factory.Sequence(lambda n: f"admin_{n}")


class ClienteFactory(DjangoModelFactory):
    class Meta:
        model = Cliente

    nome = factory.Faker("name", locale="pt_BR")
    email = factory.Sequence(lambda n: f"cliente_{n}@test.com")
    empresa = factory.Faker("company", locale="pt_BR")


class CategoriaFactory(DjangoModelFactory):
    class Meta:
        model = CategoriaTicket

    nome = factory.Sequence(lambda n: f"Categoria {n}")
    cor = "#007bff"


class SLAPolicyFactory(DjangoModelFactory):
    class Meta:
        model = SLAPolicy

    name = factory.Sequence(lambda n: f"SLA Policy {n}")
    prioridade = "media"
    first_response_time = 240
    resolution_time = 1440
    escalation_time = 480
    is_active = True


class TicketFactory(DjangoModelFactory):
    class Meta:
        model = Ticket

    cliente = factory.SubFactory(ClienteFactory)
    titulo = factory.Faker("sentence", nb_words=5, locale="pt_BR")
    descricao = factory.Faker("paragraph", locale="pt_BR")
    status = StatusTicket.ABERTO
    prioridade = PrioridadeTicket.MEDIA
    tipo = "incidente"
    origem = "web"


class InteracaoFactory(DjangoModelFactory):
    class Meta:
        model = InteracaoTicket

    ticket = factory.SubFactory(TicketFactory)
    usuario = factory.SubFactory(UserFactory)
    mensagem = factory.Faker("paragraph", locale="pt_BR")
    tipo = "resposta"
    eh_publico = True


class PerfilAgenteFactory(DjangoModelFactory):
    class Meta:
        model = PerfilAgente

    user = factory.SubFactory(UserFactory)
    status = "online"
    max_tickets_simultaneos = 5


class WorkflowRuleFactory(DjangoModelFactory):
    class Meta:
        model = WorkflowRule

    name = factory.Sequence(lambda n: f"Regra {n}")
    trigger_event = "ticket_created"
    conditions = {}
    actions = {}
    priority = 1
    is_active = True
