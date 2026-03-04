"""
Views para operações avançadas de tickets — Merge / Split / Parent-Child.
"""

import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from ..services.ticket_operations import ticket_ops
from ..utils.rbac import role_required

logger = logging.getLogger("dashboard")


@login_required
@role_required('admin', 'gerente', 'supervisor')
@require_POST
def api_merge_tickets(request):
    """
    POST /api/tickets/merge/
    Body: { "target_ticket_id": 1, "source_ticket_ids": [2, 3], "reason": "Duplicatas" }
    """
    try:
        data = json.loads(request.body)
        target_id = data.get("target_ticket_id")
        source_ids = data.get("source_ticket_ids", [])
        reason = data.get("reason", "")

        if not target_id or not source_ids:
            return JsonResponse({"error": "target_ticket_id e source_ticket_ids são obrigatórios"}, status=400)

        result = ticket_ops.merge_tickets(target_id, source_ids, request.user, reason)

        if result["success"]:
            return JsonResponse(result, status=200)
        return JsonResponse(result, status=400)

    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)
    except Exception as e:
        logger.error(f"Erro na API merge: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@role_required('admin', 'gerente', 'supervisor')
@require_POST
def api_split_ticket(request):
    """
    POST /api/tickets/split/
    Body: {
        "original_ticket_id": 1,
        "new_tickets": [
            {"titulo": "Sub-problema A", "descricao": "...", "prioridade": "alta"},
            {"titulo": "Sub-problema B", "descricao": "..."}
        ]
    }
    """
    try:
        data = json.loads(request.body)
        original_id = data.get("original_ticket_id")
        new_tickets = data.get("new_tickets", [])

        if not original_id or not new_tickets:
            return JsonResponse({"error": "original_ticket_id e new_tickets são obrigatórios"}, status=400)

        result = ticket_ops.split_ticket(original_id, new_tickets, request.user)

        if result["success"]:
            return JsonResponse(result, status=201)
        return JsonResponse(result, status=400)

    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)
    except Exception as e:
        logger.error(f"Erro na API split: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@role_required('admin', 'gerente', 'supervisor')
@require_POST
def api_add_sub_ticket(request, pk):
    """
    POST /api/tickets/<pk>/sub-tickets/
    Body: { "titulo": "Sub-tarefa X", "descricao": "...", "prioridade": "media" }
    """
    try:
        data = json.loads(request.body)
        result = ticket_ops.add_sub_ticket(pk, data, request.user)

        if result["success"]:
            return JsonResponse(result, status=201)
        return JsonResponse(result, status=400)

    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)
    except Exception as e:
        logger.error(f"Erro na API add_sub_ticket: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@role_required('admin', 'gerente', 'supervisor')
@require_POST
def api_remove_sub_ticket(request, pk):
    """
    POST /api/tickets/<pk>/sub-tickets/remove/
    Remove o vínculo de sub-ticket (não deleta).
    """
    try:
        result = ticket_ops.remove_sub_ticket(pk, request.user)

        if result["success"]:
            return JsonResponse(result, status=200)
        return JsonResponse(result, status=400)

    except Exception as e:
        logger.error(f"Erro na API remove_sub_ticket: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@role_required('admin', 'gerente', 'supervisor')
@require_GET
def api_ticket_hierarchy(request, pk):
    """
    GET /api/tickets/<pk>/hierarchy/
    Retorna hierarquia completa: pai, irmãos, filhos, merged, relacionados.
    """
    try:
        result = ticket_ops.get_ticket_hierarchy(pk)

        if "error" in result:
            return JsonResponse(result, status=404)
        return JsonResponse(result, status=200)

    except Exception as e:
        logger.error(f"Erro na API ticket_hierarchy: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@role_required('admin', 'gerente', 'supervisor')
@require_POST
def api_link_tickets(request, pk):
    """
    POST /api/tickets/<pk>/link/
    Body: { "related_ticket_ids": [5, 6] }
    Vincula tickets como relacionados.
    """
    try:
        from ..models import Ticket

        data = json.loads(request.body)
        related_ids = data.get("related_ticket_ids", [])

        if not related_ids:
            return JsonResponse({"error": "related_ticket_ids é obrigatório"}, status=400)

        ticket = Ticket.objects.get(id=pk)
        related = Ticket.objects.filter(id__in=related_ids)

        for r in related:
            ticket.related_tickets.add(r)

        return JsonResponse(
            {
                "success": True,
                "ticket": ticket.numero,
                "linked_count": related.count(),
            }
        )

    except Ticket.DoesNotExist:
        return JsonResponse({"error": "Ticket não encontrado"}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)
    except Exception as e:
        logger.error(f"Erro na API link_tickets: {e}")
        return JsonResponse({"error": str(e)}, status=500)
