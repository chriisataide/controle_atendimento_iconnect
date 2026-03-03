"""
Sistema de Busca Avançada para iConnect
Implementa busca full-text, filtros avançados e busca por similaridade
"""

import re
from typing import Any, Dict, List

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import models
from django.db.models import Q
from django.utils import timezone

from ..models import Cliente, Ticket

# Alias para compatibilidade
Customer = Cliente


class AdvancedSearchService:
    """
    Serviço de busca avançada com múltiplas estratégias
    """

    def __init__(self):
        self.search_weights = {
            "ticket_number": "A",  # Maior peso
            "title": "A",
            "customer_name": "B",
            "customer_email": "B",
            "description": "C",
            "tags": "D",  # Menor peso
        }

    def search_tickets(
        self,
        query: str = None,
        filters: Dict[str, Any] = None,
        sort_by: str = "relevance",
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Busca avançada de tickets com multiple estratégias

        Args:
            query: Termo de busca livre
            filters: Dicionário de filtros específicos
            sort_by: Campo de ordenação ('relevance', 'created_at', 'updated_at', etc.)
            limit: Número máximo de resultados
            offset: Offset para paginação

        Returns:
            Dicionário com resultados, total e metadados
        """

        # Inicializar queryset base
        tickets = Ticket.objects.all()

        # Aplicar filtros específicos
        if filters:
            tickets = self._apply_filters(tickets, filters)

        # Aplicar busca textual se fornecida
        if query and query.strip():
            tickets = self._apply_text_search(tickets, query.strip())

        # Aplicar ordenação
        tickets = self._apply_sorting(tickets, sort_by, bool(query))

        # Contar total antes da paginação
        total_count = tickets.count()

        # Aplicar paginação
        paginated_tickets = tickets[offset : offset + limit]

        # Serializar resultados
        results = []
        for ticket in paginated_tickets:
            result = self._serialize_ticket(ticket)

            # Adicionar score de relevância se disponível
            if hasattr(ticket, "search_rank"):
                result["relevance_score"] = float(ticket.search_rank)

            results.append(result)

        # Estatísticas de busca
        stats = self._get_search_stats(tickets if not query else Ticket.objects.all(), filters)

        return {
            "results": results,
            "total_count": total_count,
            "has_more": total_count > (offset + limit),
            "query": query,
            "filters_applied": filters or {},
            "stats": stats,
            "search_time_ms": 0,  # Implementar timing se necessário
        }

    def _apply_filters(self, queryset, filters: Dict[str, Any]):
        """Aplica filtros específicos ao queryset"""

        if "status" in filters:
            status_list = filters["status"] if isinstance(filters["status"], list) else [filters["status"]]
            queryset = queryset.filter(status__in=status_list)

        if "priority" in filters:
            priority_list = filters["priority"] if isinstance(filters["priority"], list) else [filters["priority"]]
            queryset = queryset.filter(priority__in=priority_list)

        if "assigned_to" in filters:
            assigned_list = (
                filters["assigned_to"] if isinstance(filters["assigned_to"], list) else [filters["assigned_to"]]
            )
            queryset = queryset.filter(assigned_to_id__in=assigned_list)

        if "customer_id" in filters:
            queryset = queryset.filter(customer_id=filters["customer_id"])

        if "created_after" in filters:
            queryset = queryset.filter(created_at__gte=filters["created_after"])

        if "created_before" in filters:
            queryset = queryset.filter(created_at__lte=filters["created_before"])

        if "updated_after" in filters:
            queryset = queryset.filter(updated_at__gte=filters["updated_after"])

        if "updated_before" in filters:
            queryset = queryset.filter(updated_at__lte=filters["updated_before"])

        if "tag" in filters:
            # Assumindo que existe um campo tags (JSONField ou ManyToMany)
            if hasattr(Ticket, "tags"):
                tag_list = filters["tag"] if isinstance(filters["tag"], list) else [filters["tag"]]
                queryset = queryset.filter(tags__overlap=tag_list)

        if "has_attachments" in filters:
            if filters["has_attachments"]:
                queryset = queryset.filter(attachments__isnull=False).distinct()
            else:
                queryset = queryset.filter(attachments__isnull=True)

        if "overdue" in filters and filters["overdue"]:
            # Tickets em atraso (SLA vencido)
            queryset = queryset.filter(sla_deadline__lt=timezone.now(), status__in=["NOVO", "ABERTO", "EM_ANDAMENTO"])

        if "unassigned" in filters and filters["unassigned"]:
            queryset = queryset.filter(assigned_to__isnull=True)

        if "escalated" in filters and filters["escalated"]:
            queryset = queryset.filter(escalated=True)

        return queryset

    def _apply_text_search(self, queryset, query: str):
        """Aplica busca textual full-text usando PostgreSQL"""

        # Detectar tipo de busca
        search_type = self._detect_search_type(query)

        if search_type == "ticket_number":
            # Busca exata por número do ticket
            return queryset.filter(ticket_number__iexact=query)

        elif search_type == "email":
            # Busca por email do cliente
            return queryset.filter(Q(customer__email__iexact=query) | Q(customer__email__icontains=query)).distinct()

        elif search_type == "phone":
            # Busca por telefone (remover formatação)
            clean_phone = re.sub(r"[^\d]", "", query)
            return queryset.filter(customer__phone__icontains=clean_phone)

        else:
            # Busca full-text geral
            return self._apply_fulltext_search(queryset, query)

    def _detect_search_type(self, query: str) -> str:
        """Detecta o tipo de busca baseado no padrão da query"""

        # Número de ticket (ex: #12345, TK-12345)
        if re.match(r"^#?\w*\d+$", query):
            return "ticket_number"

        # Email
        if re.match(r"^[^@]+@[^@]+\.[^@]+$", query):
            return "email"

        # Telefone
        if re.match(r"^[\d\s\(\)\-\+]{8,}$", query):
            return "phone"

        return "text"

    def _apply_fulltext_search(self, queryset, query: str):
        """Aplica busca full-text com ranking"""

        # Criar vetor de busca combinando múltiplos campos
        search_vector = (
            SearchVector("ticket_number", weight="A")
            + SearchVector("title", weight="A")
            + SearchVector("description", weight="C")
            + SearchVector("customer__name", weight="B")
            + SearchVector("customer__email", weight="B")
        )

        # Criar query de busca
        search_query = SearchQuery(query, config="portuguese")

        # Aplicar busca com ranking
        queryset = queryset.annotate(search=search_vector, search_rank=SearchRank(search_vector, search_query)).filter(
            search=search_query
        )

        # Busca alternativa com LIKE se não houver resultados full-text
        if not queryset.exists():
            queryset = self._apply_like_search(queryset.model.objects.all(), query)

        return queryset

    def _apply_like_search(self, queryset, query: str):
        """Busca alternativa usando LIKE/ILIKE"""

        return queryset.filter(
            Q(ticket_number__icontains=query)
            | Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(customer__name__icontains=query)
            | Q(customer__email__icontains=query)
            | Q(assigned_to__user__first_name__icontains=query)
            | Q(assigned_to__user__last_name__icontains=query)
        ).distinct()

    def _apply_sorting(self, queryset, sort_by: str, has_search: bool):
        """Aplica ordenação aos resultados"""

        # Se há busca textual, priorizar relevância
        if has_search and hasattr(queryset.model, "search_rank"):
            if sort_by == "relevance":
                return queryset.order_by("-search_rank", "-created_at")

        # Mapeamento de campos de ordenação
        sort_mapping = {
            "created_at": "-created_at",
            "created_at_asc": "created_at",
            "updated_at": "-updated_at",
            "updated_at_asc": "updated_at",
            "priority": "-priority",
            "status": "status",
            "customer": "customer__name",
            "assigned_to": "assigned_to__user__first_name",
            "title": "title",
            "ticket_number": "ticket_number",
        }

        order_field = sort_mapping.get(sort_by, "-created_at")
        return queryset.order_by(order_field)

    def _serialize_ticket(self, ticket) -> Dict[str, Any]:
        """Serializa um ticket para o resultado da busca"""

        return {
            "id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "title": ticket.title,
            "description": ticket.description[:200] + "..." if len(ticket.description) > 200 else ticket.description,
            "status": ticket.status,
            "priority": ticket.priority,
            "customer": {
                "id": ticket.customer.id if ticket.customer else None,
                "name": ticket.customer.name if ticket.customer else None,
                "email": ticket.customer.email if ticket.customer else None,
            },
            "assigned_to": {
                "id": ticket.assigned_to.id if ticket.assigned_to else None,
                "name": ticket.assigned_to.user.get_full_name() if ticket.assigned_to else None,
            },
            "created_at": ticket.created_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat(),
            "sla_status": self._get_sla_status(ticket),
            "has_attachments": hasattr(ticket, "attachments") and ticket.attachments.exists(),
        }

    def _get_sla_status(self, ticket) -> Dict[str, Any]:
        """Calcula status do SLA para o ticket"""

        if not hasattr(ticket, "sla_deadline") or not ticket.sla_deadline:
            return {"status": "no_sla", "remaining_hours": None}

        now = timezone.now()

        if ticket.status == "FECHADO":
            if ticket.resolved_at and ticket.resolved_at <= ticket.sla_deadline:
                return {"status": "met", "remaining_hours": None}
            else:
                return {"status": "breached", "remaining_hours": None}

        if now > ticket.sla_deadline:
            return {"status": "breached", "remaining_hours": 0}

        remaining = ticket.sla_deadline - now
        remaining_hours = remaining.total_seconds() / 3600

        if remaining_hours <= 2:
            status = "critical"
        elif remaining_hours <= 8:
            status = "warning"
        else:
            status = "ok"

        return {"status": status, "remaining_hours": round(remaining_hours, 1)}

    def _get_search_stats(self, base_queryset, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Gera estatísticas de busca"""

        stats = {
            "total_tickets": base_queryset.count(),
            "status_distribution": {},
            "priority_distribution": {},
            "assigned_distribution": {},
        }

        # Distribuição por status
        status_counts = base_queryset.values("status").annotate(count=models.Count("id")).order_by("-count")

        for item in status_counts:
            stats["status_distribution"][item["status"]] = item["count"]

        # Distribuição por prioridade
        priority_counts = base_queryset.values("priority").annotate(count=models.Count("id")).order_by("-count")

        for item in priority_counts:
            stats["priority_distribution"][item["priority"]] = item["count"]

        # Tickets não atribuídos
        unassigned_count = base_queryset.filter(assigned_to__isnull=True).count()
        assigned_count = base_queryset.filter(assigned_to__isnull=False).count()

        stats["assigned_distribution"] = {"assigned": assigned_count, "unassigned": unassigned_count}

        return stats

    def get_search_suggestions(self, partial_query: str, limit: int = 10) -> List[str]:
        """
        Gera sugestões de busca baseadas em queries parciais
        """
        suggestions = []

        if len(partial_query) >= 2:
            # Sugestões de títulos de tickets
            title_suggestions = (
                Ticket.objects.filter(title__icontains=partial_query)
                .values_list("title", flat=True)
                .distinct()[: limit // 3]
            )

            suggestions.extend(title_suggestions)

            # Sugestões de nomes de clientes
            customer_suggestions = (
                Customer.objects.filter(name__icontains=partial_query)
                .values_list("name", flat=True)
                .distinct()[: limit // 3]
            )

            suggestions.extend(customer_suggestions)

            # Sugestões de números de ticket
            ticket_suggestions = (
                Ticket.objects.filter(ticket_number__icontains=partial_query)
                .values_list("ticket_number", flat=True)
                .distinct()[: limit // 3]
            )

            suggestions.extend(ticket_suggestions)

        return list(set(suggestions))[:limit]

    def save_search_history(self, user_id: int, query: str, filters: Dict[str, Any], results_count: int):
        """
        Salva histórico de buscas do usuário para analytics
        """
        # Implementar modelo SearchHistory se necessário


# Instância global do serviço
search_service = AdvancedSearchService()
