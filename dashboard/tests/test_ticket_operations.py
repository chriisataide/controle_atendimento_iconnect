"""
Testes para operações avançadas de ticket: Merge, Split, Parent/Child.
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase

from dashboard.models import CategoriaTicket, Cliente, InteracaoTicket, StatusTicket, Ticket
from dashboard.services.ticket_operations import TicketOperations


class TicketMergeTest(TestCase):
    """Testes de merge de tickets"""

    def setUp(self):
        self.ops = TicketOperations()
        self.user = User.objects.create_user(username="agente", password="test123")
        self.cliente = Cliente.objects.create(nome="Test Client", email="client@test.com")
        self.cat = CategoriaTicket.objects.create(nome="Suporte")

        self.target = Ticket.objects.create(
            cliente=self.cliente,
            agente=self.user,
            categoria=self.cat,
            titulo="Ticket Alvo",
            descricao="Desc target",
        )
        self.source1 = Ticket.objects.create(
            cliente=self.cliente,
            agente=self.user,
            categoria=self.cat,
            titulo="Ticket Source 1",
            descricao="Desc source 1",
        )
        self.source2 = Ticket.objects.create(
            cliente=self.cliente,
            agente=self.user,
            categoria=self.cat,
            titulo="Ticket Source 2",
            descricao="Desc source 2",
        )
        # Add interaction on source
        InteracaoTicket.objects.create(
            ticket=self.source1,
            usuario=self.user,
            mensagem="Interação no source 1",
            tipo="resposta",
        )

    def test_merge_success(self):
        result = self.ops.merge_tickets(self.target.id, [self.source1.id, self.source2.id], self.user, "Duplicatas")
        self.assertTrue(result["success"])
        self.assertEqual(result["total_merged"], 2)

        # Sources are closed with merged_into
        self.source1.refresh_from_db()
        self.source2.refresh_from_db()
        self.assertEqual(self.source1.status, StatusTicket.FECHADO)
        self.assertEqual(self.source1.merged_into, self.target)
        self.assertEqual(self.source2.merged_into, self.target)

    def test_merge_copies_interactions(self):
        self.ops.merge_tickets(self.target.id, [self.source1.id], self.user)
        # Target should now have merged interaction + system note
        interactions = self.target.interacoes.all()
        self.assertTrue(interactions.filter(mensagem__contains="Merged de").exists())

    def test_merge_invalid_target(self):
        result = self.ops.merge_tickets(99999, [self.source1.id], self.user)
        self.assertFalse(result["success"])

    def test_merge_no_sources(self):
        result = self.ops.merge_tickets(self.target.id, [], self.user)
        self.assertFalse(result["success"])

    def test_merge_already_closed_excluded(self):
        self.source1.status = StatusTicket.FECHADO
        self.source1.save()
        result = self.ops.merge_tickets(self.target.id, [self.source1.id, self.source2.id], self.user)
        self.assertTrue(result["success"])
        self.assertEqual(result["total_merged"], 1)  # Only source2


class TicketSplitTest(TestCase):
    """Testes de split de tickets"""

    def setUp(self):
        self.ops = TicketOperations()
        self.user = User.objects.create_user(username="agente_split", password="test123")
        self.cliente = Cliente.objects.create(nome="Split Client", email="split@test.com")
        self.cat = CategoriaTicket.objects.create(nome="Bug")

        self.original = Ticket.objects.create(
            cliente=self.cliente,
            agente=self.user,
            categoria=self.cat,
            titulo="Ticket Original",
            descricao="Descricao grande com vários problemas",
            prioridade="alta",
        )

    def test_split_success(self):
        result = self.ops.split_ticket(
            self.original.id,
            [
                {"titulo": "Sub A", "descricao": "Problema A"},
                {"titulo": "Sub B", "descricao": "Problema B", "prioridade": "media"},
            ],
            self.user,
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["total_created"], 2)
        self.assertEqual(result["original_ticket"], self.original.numero)

    def test_split_creates_child_tickets(self):
        self.ops.split_ticket(
            self.original.id,
            [{"titulo": "Sub C", "descricao": "Problema C"}],
            self.user,
        )
        children = self.original.sub_tickets.all()
        self.assertEqual(children.count(), 1)
        self.assertEqual(children.first().parent_ticket, self.original)

    def test_split_inherits_priority(self):
        self.ops.split_ticket(
            self.original.id,
            [{"titulo": "Herda prioridade"}],
            self.user,
        )
        child = self.original.sub_tickets.first()
        self.assertEqual(child.prioridade, "alta")

    def test_split_invalid_original(self):
        result = self.ops.split_ticket(99999, [{"titulo": "X"}], self.user)
        self.assertFalse(result["success"])


class TicketParentChildTest(TestCase):
    """Testes de hierarquia parent/child"""

    def setUp(self):
        self.ops = TicketOperations()
        self.user = User.objects.create_user(username="agente_pc", password="test123")
        self.cliente = Cliente.objects.create(nome="PC Client", email="pc@test.com")
        self.cat = CategoriaTicket.objects.create(nome="Rede")

        self.parent = Ticket.objects.create(
            cliente=self.cliente,
            agente=self.user,
            categoria=self.cat,
            titulo="Ticket Pai",
            descricao="Instalação completa",
        )

    def test_add_sub_ticket(self):
        result = self.ops.add_sub_ticket(
            self.parent.id,
            {"titulo": "Cabear rede", "descricao": "Passar cabos"},
            self.user,
        )
        self.assertTrue(result["success"])
        self.assertEqual(self.parent.sub_tickets.count(), 1)

    def test_remove_sub_ticket(self):
        # Create child first
        res = self.ops.add_sub_ticket(
            self.parent.id,
            {"titulo": "Temporario"},
            self.user,
        )
        child_id = res["child_ticket"]["id"]
        # Remove
        result = self.ops.remove_sub_ticket(child_id, self.user)
        self.assertTrue(result["success"])
        child = Ticket.objects.get(id=child_id)
        self.assertIsNone(child.parent_ticket)

    def test_remove_non_sub_ticket(self):
        result = self.ops.remove_sub_ticket(self.parent.id, self.user)
        self.assertFalse(result["success"])

    def test_hierarchy(self):
        self.ops.add_sub_ticket(self.parent.id, {"titulo": "Child 1"}, self.user)
        self.ops.add_sub_ticket(self.parent.id, {"titulo": "Child 2"}, self.user)

        hierarchy = self.ops.get_ticket_hierarchy(self.parent.id)
        self.assertEqual(len(hierarchy["children"]), 2)
        self.assertIsNone(hierarchy["parent"])
        self.assertEqual(hierarchy["children_progress"]["total"], 2)

    def test_hierarchy_child_perspective(self):
        res = self.ops.add_sub_ticket(self.parent.id, {"titulo": "Child X"}, self.user)
        child_id = res["child_ticket"]["id"]

        hierarchy = self.ops.get_ticket_hierarchy(child_id)
        self.assertIsNotNone(hierarchy["parent"])
        self.assertEqual(hierarchy["parent"]["id"], self.parent.id)

    def test_auto_close_parent(self):
        res1 = self.ops.add_sub_ticket(self.parent.id, {"titulo": "T1"}, self.user)
        res2 = self.ops.add_sub_ticket(self.parent.id, {"titulo": "T2"}, self.user)

        # Close all children
        c1 = Ticket.objects.get(id=res1["child_ticket"]["id"])
        c2 = Ticket.objects.get(id=res2["child_ticket"]["id"])
        c1.status = StatusTicket.RESOLVIDO
        c1.save()
        c2.status = StatusTicket.RESOLVIDO
        c2.save()

        closed = self.ops.auto_close_parent_if_all_children_done(self.parent.id, self.user)
        self.assertTrue(closed)
        self.parent.refresh_from_db()
        self.assertEqual(self.parent.status, StatusTicket.RESOLVIDO)

    def test_auto_close_parent_not_all_done(self):
        self.ops.add_sub_ticket(self.parent.id, {"titulo": "T1"}, self.user)
        self.ops.add_sub_ticket(self.parent.id, {"titulo": "T2"}, self.user)

        closed = self.ops.auto_close_parent_if_all_children_done(self.parent.id, self.user)
        self.assertFalse(closed)


class TicketOperationsViewTest(TestCase):
    """Testes de endpoints HTTP"""

    def setUp(self):
        self.user = User.objects.create_user(username="api_user", password="test123")
        self.client.login(username="api_user", password="test123")
        self.cliente_obj = Cliente.objects.create(nome="API Client", email="api@test.com")
        self.cat = CategoriaTicket.objects.create(nome="API")

        self.ticket1 = Ticket.objects.create(
            cliente=self.cliente_obj,
            agente=self.user,
            categoria=self.cat,
            titulo="T1",
            descricao="D1",
        )
        self.ticket2 = Ticket.objects.create(
            cliente=self.cliente_obj,
            agente=self.user,
            categoria=self.cat,
            titulo="T2",
            descricao="D2",
        )

    def test_merge_api(self):
        resp = self.client.post(
            "/dashboard/api/tickets/merge/",
            json.dumps(
                {
                    "target_ticket_id": self.ticket1.id,
                    "source_ticket_ids": [self.ticket2.id],
                    "reason": "Duplicata",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])

    def test_split_api(self):
        resp = self.client.post(
            "/dashboard/api/tickets/split/",
            json.dumps(
                {
                    "original_ticket_id": self.ticket1.id,
                    "new_tickets": [{"titulo": "Sub A"}],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)

    def test_hierarchy_api(self):
        resp = self.client.get(f"/dashboard/api/tickets/{self.ticket1.id}/hierarchy/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("children", data)

    def test_link_tickets_api(self):
        resp = self.client.post(
            f"/dashboard/api/tickets/{self.ticket1.id}/link/",
            json.dumps({"related_ticket_ids": [self.ticket2.id]}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.ticket1.refresh_from_db()
        self.assertIn(self.ticket2, self.ticket1.related_tickets.all())

    def test_merge_api_requires_auth(self):
        self.client.logout()
        resp = self.client.post(
            "/dashboard/api/tickets/merge/",
            json.dumps({"target_ticket_id": 1, "source_ticket_ids": [2]}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 302)  # Redirect to login
