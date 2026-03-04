#!/usr/bin/env python
"""Seed database with sample data for testing."""

import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "controle_atendimento.settings")
sys.path.insert(0, "/app")
django.setup()

from django.contrib.auth.models import User

from dashboard.models import CategoriaTicket, Cliente, Ticket

# Categorias
cat1, _ = CategoriaTicket.objects.get_or_create(nome="Suporte Tecnico")
cat2, _ = CategoriaTicket.objects.get_or_create(nome="Financeiro")
cat3, _ = CategoriaTicket.objects.get_or_create(nome="Instalacao")
print(f"Categorias: {CategoriaTicket.objects.count()}")

# Clientes
clientes_data = [
    ("Joao Silva", "joao@empresa.com", "Tech Solutions LTDA"),
    ("Maria Oliveira", "maria@startup.com", "Startup Digital"),
    ("Carlos Santos", "carlos@corp.com", "Corp Telecom"),
    ("Ana Costa", "ana@rede.com", "Rede Conecta"),
    ("Pedro Almeida", "pedro@net.com", "NetService Provider"),
]
clients = []
for nome, email, empresa in clientes_data:
    c, _ = Cliente.objects.get_or_create(nome=nome, defaults={"email": email, "empresa": empresa})
    clients.append(c)
print(f"Clientes: {Cliente.objects.count()}")

admin = User.objects.filter(is_superuser=True).first()

# Tickets
tickets_data = [
    ("Internet lenta no escritorio principal", clients[0], cat1, "alta", "aberto"),
    ("Erro ao emitir nota fiscal no sistema", clients[1], cat2, "critica", "em_andamento"),
    ("Instalacao de novo roteador na filial", clients[2], cat3, "media", "aberto"),
    ("VPN corporativa caindo frequentemente", clients[3], cat1, "alta", "aguardando_cliente"),
    ("Configurar novo servidor de e-mail", clients[4], cat1, "baixa", "aberto"),
    ("Fatura em duplicidade no sistema", clients[0], cat2, "media", "resolvido"),
    ("Trocar equipamento com defeito", clients[1], cat3, "alta", "em_andamento"),
    ("Problema no firewall bloqueando acesso", clients[2], cat1, "critica", "aberto"),
    ("Solicitar upgrade de plano de internet", clients[3], cat2, "baixa", "fechado"),
    ("Cameras de seguranca sem conexao", clients[4], cat1, "alta", "aberto"),
]

created = 0
for titulo, cliente, categoria, prioridade, status in tickets_data:
    t, was_created = Ticket.objects.get_or_create(
        titulo=titulo,
        defaults={
            "cliente": cliente,
            "categoria": categoria,
            "agente": admin,
            "prioridade": prioridade,
            "status": status,
            "descricao": f"Descricao detalhada: {titulo}",
            "tipo": "incidente",
        },
    )
    if was_created:
        created += 1

print(f"Tickets: {Ticket.objects.count()} ({created} novos)")
print("Seed concluido com sucesso!")
