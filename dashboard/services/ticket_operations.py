"""
Ticket Operations — Merge, Split e Parent/Child para iConnect.

Operações avançadas sobre tickets:
- Merge: unir múltiplos tickets com mesmo problema em um ticket principal
- Split: dividir um ticket em múltiplos tickets independentes
- Parent/Child: gerenciar hierarquia de tickets (sub-tarefas)
"""

import logging

from django.db import transaction
from django.utils import timezone

from ..models import InteracaoTicket, StatusTicket, Ticket

logger = logging.getLogger("dashboard")


class TicketOperations:
    """Engine para operações avançadas de tickets"""

    # ======================== MERGE ========================

    @transaction.atomic
    def merge_tickets(self, target_ticket_id, source_ticket_ids, user, reason=""):
        """
        Merge múltiplos tickets em um ticket alvo.

        - O target_ticket permanece aberto e recebe todas as interações
        - Os source_tickets são marcados como 'fechado' com merged_into apontando para o target
        - Histórico completo é preservado

        Args:
            target_ticket_id: ID do ticket que receberá os merges
            source_ticket_ids: lista de IDs dos tickets a serem mesclados
            user: usuário que está executando a operação
            reason: motivo do merge

        Returns:
            dict com resultado da operação
        """
        try:
            target = Ticket.objects.select_for_update().get(id=target_ticket_id)
            sources = list(
                Ticket.objects.select_for_update()
                .filter(id__in=source_ticket_ids)
                .exclude(id=target_ticket_id)
                .exclude(status=StatusTicket.FECHADO)
            )

            if not sources:
                return {"success": False, "error": "Nenhum ticket válido para merge"}

            merged_numbers = []

            for source in sources:
                # 1. Copiar interações do source para o target
                for interacao in source.interacoes.all():
                    InteracaoTicket.objects.create(
                        ticket=target,
                        usuario=interacao.usuario,
                        mensagem=f"[Merged de #{source.numero}] {interacao.mensagem}",
                        tipo=interacao.tipo,
                        canal=interacao.canal,
                        eh_publico=interacao.eh_publico,
                    )

                # 2. Mover watchers
                for watcher in source.watchers.all():
                    target.watchers.add(watcher)

                # 3. Vincular tickets relacionados
                for related in source.related_tickets.all():
                    if related != target:
                        target.related_tickets.add(related)

                # 4. Mover anexos (referenciar ao target)
                source.anexos.update(ticket=target)

                # 5. Marcar source como merged
                source.merged_into = target
                source.status = StatusTicket.FECHADO
                source.fechado_em = timezone.now()
                source.save()

                merged_numbers.append(source.numero)

                logger.info(f"Ticket #{source.numero} merged into #{target.numero} by {user.username}")

            # 6. Adicionar nota de sistema no target
            merge_msg = (
                f"🔀 **Merge realizado** por {user.get_full_name() or user.username}\n"
                f'Tickets mesclados: {", ".join(f"#{n}" for n in merged_numbers)}\n'
            )
            if reason:
                merge_msg += f"Motivo: {reason}"

            InteracaoTicket.objects.create(
                ticket=target,
                usuario=user,
                mensagem=merge_msg,
                tipo="sistema",
                eh_publico=False,
            )

            return {
                "success": True,
                "target_ticket": target.numero,
                "merged_tickets": merged_numbers,
                "total_merged": len(merged_numbers),
            }

        except Ticket.DoesNotExist:
            return {"success": False, "error": "Ticket alvo não encontrado"}
        except Exception as e:
            logger.error(f"Erro no merge de tickets: {e}")
            return {"success": False, "error": str(e)}

    # ======================== SPLIT ========================

    @transaction.atomic
    def split_ticket(self, original_ticket_id, new_tickets_data, user):
        """
        Divide um ticket em múltiplos tickets novos.

        O ticket original permanece e novos tickets são criados a partir dele.

        Args:
            original_ticket_id: ID do ticket original
            new_tickets_data: lista de dicts com dados dos novos tickets
                [{'titulo': '...', 'descricao': '...', 'prioridade': 'media'}, ...]
            user: usuário que está executando a operação

        Returns:
            dict com resultado da operação
        """
        try:
            original = Ticket.objects.select_for_update().get(id=original_ticket_id)
            created_tickets = []

            for ticket_data in new_tickets_data:
                new_ticket = Ticket.objects.create(
                    cliente=original.cliente,
                    agente=original.agente,
                    categoria=original.categoria,
                    titulo=ticket_data.get("titulo", f"Split de #{original.numero}"),
                    descricao=ticket_data.get("descricao", original.descricao),
                    prioridade=ticket_data.get("prioridade", original.prioridade),
                    tipo=ticket_data.get("tipo", original.tipo),
                    status=StatusTicket.ABERTO,
                    origem=original.origem,
                    sla_policy=original.sla_policy,
                    parent_ticket=original,  # Vincula como subticket
                )

                # Copiar tags do original
                if original.tags:
                    new_ticket.tags = original.tags
                    new_ticket.save()

                # Copiar watchers
                for watcher in original.watchers.all():
                    new_ticket.watchers.add(watcher)

                # Nota de sistema no novo ticket
                InteracaoTicket.objects.create(
                    ticket=new_ticket,
                    usuario=user,
                    mensagem=f"✂️ Ticket criado por split do ticket #{original.numero}",
                    tipo="sistema",
                    eh_publico=False,
                )

                created_tickets.append(
                    {
                        "id": new_ticket.id,
                        "numero": new_ticket.numero,
                        "titulo": new_ticket.titulo,
                    }
                )

                logger.info(f"Split: #{new_ticket.numero} criado a partir de #{original.numero}")

            # Nota de sistema no ticket original
            split_refs = ", ".join(f'#{t["numero"]}' for t in created_tickets)
            InteracaoTicket.objects.create(
                ticket=original,
                usuario=user,
                mensagem=(
                    f"✂️ **Split realizado** por {user.get_full_name() or user.username}\n"
                    f"Novos tickets criados: {split_refs}"
                ),
                tipo="sistema",
                eh_publico=False,
            )

            return {
                "success": True,
                "original_ticket": original.numero,
                "created_tickets": created_tickets,
                "total_created": len(created_tickets),
            }

        except Ticket.DoesNotExist:
            return {"success": False, "error": "Ticket original não encontrado"}
        except Exception as e:
            logger.error(f"Erro no split de ticket: {e}")
            return {"success": False, "error": str(e)}

    # ======================== PARENT/CHILD ========================

    def add_sub_ticket(self, parent_ticket_id, child_data, user):
        """
        Cria um sub-ticket vinculado a um ticket pai.

        Args:
            parent_ticket_id: ID do ticket pai
            child_data: dict com dados do sub-ticket
            user: usuário criador
        """
        try:
            parent = Ticket.objects.get(id=parent_ticket_id)

            child = Ticket.objects.create(
                cliente=parent.cliente,
                agente=child_data.get("agente") or parent.agente,
                categoria=parent.categoria,
                titulo=child_data.get("titulo", f"Sub-tarefa de #{parent.numero}"),
                descricao=child_data.get("descricao", ""),
                prioridade=child_data.get("prioridade", parent.prioridade),
                tipo=child_data.get("tipo", parent.tipo),
                status=StatusTicket.ABERTO,
                origem="web",
                parent_ticket=parent,
            )

            InteracaoTicket.objects.create(
                ticket=parent,
                usuario=user,
                mensagem=f"📋 Sub-ticket #{child.numero} criado: {child.titulo}",
                tipo="sistema",
                eh_publico=False,
            )

            logger.info(f"Sub-ticket #{child.numero} criado para #{parent.numero}")

            return {
                "success": True,
                "parent_ticket": parent.numero,
                "child_ticket": {
                    "id": child.id,
                    "numero": child.numero,
                    "titulo": child.titulo,
                },
            }

        except Ticket.DoesNotExist:
            return {"success": False, "error": "Ticket pai não encontrado"}
        except Exception as e:
            logger.error(f"Erro ao criar sub-ticket: {e}")
            return {"success": False, "error": str(e)}

    def remove_sub_ticket(self, child_ticket_id, user):
        """Remove vínculo de sub-ticket (não deleta o ticket)"""
        try:
            child = Ticket.objects.get(id=child_ticket_id)
            parent = child.parent_ticket

            if not parent:
                return {"success": False, "error": "Ticket não é um sub-ticket"}

            child.parent_ticket = None
            child.save()

            InteracaoTicket.objects.create(
                ticket=parent,
                usuario=user,
                mensagem=f"📋 Sub-ticket #{child.numero} desvinculado",
                tipo="sistema",
                eh_publico=False,
            )

            return {"success": True, "detached_ticket": child.numero}

        except Ticket.DoesNotExist:
            return {"success": False, "error": "Ticket não encontrado"}

    def get_ticket_hierarchy(self, ticket_id):
        """
        Retorna a hierarquia completa de um ticket: pai, irmãos, filhos, merged.
        """
        try:
            ticket = Ticket.objects.get(id=ticket_id)

            # Filhos diretos
            children = list(ticket.sub_tickets.values("id", "numero", "titulo", "status", "prioridade"))

            # Tickets merged neste
            merged = list(ticket.merged_from.values("id", "numero", "titulo", "status"))

            # Pai
            parent = None
            siblings = []
            if ticket.parent_ticket:
                parent = {
                    "id": ticket.parent_ticket.id,
                    "numero": ticket.parent_ticket.numero,
                    "titulo": ticket.parent_ticket.titulo,
                    "status": ticket.parent_ticket.status,
                }
                # Irmãos
                siblings = list(
                    ticket.parent_ticket.sub_tickets.exclude(id=ticket.id).values("id", "numero", "titulo", "status")
                )

            # Ticket de destino do merge
            merged_into = None
            if ticket.merged_into:
                merged_into = {
                    "id": ticket.merged_into.id,
                    "numero": ticket.merged_into.numero,
                    "titulo": ticket.merged_into.titulo,
                }

            # Tickets relacionados
            related = list(ticket.related_tickets.values("id", "numero", "titulo", "status"))

            # Progresso dos filhos
            total_children = len(children)
            closed_children = sum(1 for c in children if c["status"] in [StatusTicket.FECHADO, StatusTicket.RESOLVIDO])

            return {
                "ticket": {
                    "id": ticket.id,
                    "numero": ticket.numero,
                    "titulo": ticket.titulo,
                    "status": ticket.status,
                },
                "parent": parent,
                "siblings": siblings,
                "children": children,
                "children_progress": {
                    "total": total_children,
                    "completed": closed_children,
                    "percentage": round(closed_children / total_children * 100) if total_children > 0 else 0,
                },
                "merged_from": merged,
                "merged_into": merged_into,
                "related_tickets": related,
            }

        except Ticket.DoesNotExist:
            return {"error": "Ticket não encontrado"}

    def auto_close_parent_if_all_children_done(self, parent_ticket_id, user=None):
        """
        Verifica se todos os sub-tickets estão fechados/resolvidos.
        Se sim, marca o pai como resolvido.
        """
        try:
            parent = Ticket.objects.get(id=parent_ticket_id)
            children = parent.sub_tickets.all()

            if not children.exists():
                return False

            all_done = all(c.status in [StatusTicket.FECHADO, StatusTicket.RESOLVIDO] for c in children)

            if all_done and parent.status not in [StatusTicket.FECHADO, StatusTicket.RESOLVIDO]:
                parent.status = StatusTicket.RESOLVIDO
                parent.save()

                if user:
                    InteracaoTicket.objects.create(
                        ticket=parent,
                        usuario=user,
                        mensagem="✅ Todos os sub-tickets foram resolvidos. Ticket pai marcado como resolvido automaticamente.",
                        tipo="sistema",
                        eh_publico=True,
                    )

                logger.info(f"Ticket #{parent.numero} auto-resolvido (todos sub-tickets concluídos)")
                return True

            return False

        except Ticket.DoesNotExist:
            return False


# Instância global
ticket_ops = TicketOperations()
