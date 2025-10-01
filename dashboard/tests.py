
from django.test import TestCase
from django.contrib.auth.models import User
from .models import Cliente, CategoriaTicket, Ticket, PrioridadeTicket, StatusTicket

class ClienteModelTest(TestCase):
	def test_criacao_cliente(self):
		cliente = Cliente.objects.create(nome="Cliente Teste", email="teste@exemplo.com")
		self.assertEqual(str(cliente), "Cliente Teste")
		self.assertEqual(cliente.email, "teste@exemplo.com")


class CategoriaTicketModelTest(TestCase):
	def test_criacao_categoria(self):
		categoria = CategoriaTicket.objects.create(nome="Suporte", cor="#123456")
		self.assertEqual(str(categoria), "Suporte")
		self.assertEqual(categoria.cor, "#123456")


class TicketModelTest(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username="agente", password="senha123")
		self.cliente = Cliente.objects.create(nome="Cliente Ticket", email="ticket@exemplo.com")
		self.categoria = CategoriaTicket.objects.create(nome="Dúvida", cor="#654321")

	def test_criacao_ticket(self):
		ticket = Ticket.objects.create(
			cliente=self.cliente,
			agente=self.user,
			categoria=self.categoria,
			titulo="Problema de Teste",
			descricao="Descrição do problema",
			prioridade=PrioridadeTicket.ALTA,
			status=StatusTicket.ABERTO
		)
		self.assertTrue(ticket.numero)
		self.assertEqual(ticket.titulo, "Problema de Teste")
		self.assertEqual(ticket.status, StatusTicket.ABERTO)
		self.assertEqual(str(ticket), f"#{ticket.numero} - Problema de Teste")
