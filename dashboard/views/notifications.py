"""
Views de notificações: listagem, APIs e centro de notificações.
"""

import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..models import Notification

logger = logging.getLogger("dashboard")


@login_required
def notifications_center(request):
    """Centro de Notificações"""
    return render(
        request,
        "dashboard/notifications/center.html",
        {"title": "Central de Notificações", "current_page": "notifications"},
    )


@login_required
def mark_notification_read(request, notification_id):
    """Marcar notificação como lida"""
    return JsonResponse({"status": "success"})


@login_required
@require_http_methods(["GET"])
def api_notifications_recent(request):
    """API para buscar notificações recentes do usuário"""
    try:
        notifications = (
            Notification.objects.filter(user=request.user).select_related("ticket").order_by("-created_at")[:20]
        )

        notifications_data = []
        for notification in notifications:
            notifications_data.append(
                {
                    "id": notification.id,
                    "title": notification.title,
                    "message": notification.message,
                    "type": notification.type,
                    "is_read": notification.read,
                    "created_at": notification.created_at.isoformat(),
                    "ticket_id": notification.ticket.id if notification.ticket else None,
                    "ticket_numero": notification.ticket.numero if notification.ticket else None,
                }
            )

        unread_count = Notification.objects.filter(user=request.user, read=False).count()

        return JsonResponse({"success": True, "notifications": notifications_data, "unread_count": unread_count})

    except Exception:
        logger.exception("Erro em api_notifications_recent")
        return JsonResponse({"success": False, "error": "Erro interno do servidor"}, status=500)


@login_required
@require_http_methods(["POST"])
def api_notification_mark_read(request, notification_id):
    """API para marcar uma notificação como lida"""
    try:
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.mark_as_read()
        return JsonResponse({"success": True, "message": "Notificação marcada como lida"})
    except Exception:
        logger.exception("Erro em api_notification_mark_read")
        return JsonResponse({"success": False, "error": "Erro interno do servidor"}, status=500)


@login_required
@require_http_methods(["POST"])
def api_notifications_mark_all_read(request):
    """API para marcar todas as notificações como lidas"""
    try:
        updated_count = Notification.objects.filter(user=request.user, read=False).update(
            read=True, read_at=timezone.now()
        )
        return JsonResponse(
            {
                "success": True,
                "message": f"{updated_count} notificações marcadas como lidas",
                "updated_count": updated_count,
            }
        )
    except Exception:
        logger.exception("Erro em api_notifications_mark_all_read")
        return JsonResponse({"success": False, "error": "Erro interno do servidor"}, status=500)


@login_required
@require_http_methods(["POST"])
def api_notification_delete(request, notification_id):
    """API para deletar uma notificação"""
    try:
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.delete()
        return JsonResponse({"success": True, "message": "Notificação removida"})
    except Exception:
        logger.exception("Erro em api_notification_delete")
        return JsonResponse({"success": False, "error": "Erro interno do servidor"}, status=500)


@login_required
def notifications_list(request):
    """Página completa de notificações"""
    filter_type = request.GET.get("type", "")
    filter_read = request.GET.get("read", "")
    filter_period = request.GET.get("period", "")
    search_query = request.GET.get("search", "")

    notifications = Notification.objects.filter(user=request.user)

    if filter_type:
        notifications = notifications.filter(type=filter_type)

    if filter_read == "unread":
        notifications = notifications.filter(read=False)
    elif filter_read == "read":
        notifications = notifications.filter(read=True)

    if filter_period == "today":
        notifications = notifications.filter(created_at__date=timezone.now().date())
    elif filter_period == "week":
        week_ago = timezone.now() - timedelta(days=7)
        notifications = notifications.filter(created_at__gte=week_ago)
    elif filter_period == "month":
        month_ago = timezone.now() - timedelta(days=30)
        notifications = notifications.filter(created_at__gte=month_ago)

    if search_query:
        notifications = notifications.filter(
            Q(title__icontains=search_query) | Q(message__icontains=search_query) | Q(type__icontains=search_query)
        )

    notifications = notifications.select_related("ticket").order_by("-created_at")

    paginator = Paginator(notifications, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    stats = {
        "total": Notification.objects.filter(user=request.user).count(),
        "unread": Notification.objects.filter(user=request.user, read=False).count(),
        "today": Notification.objects.filter(user=request.user, created_at__date=timezone.now().date()).count(),
    }

    tipos_raw = (
        Notification.objects.filter(user=request.user).order_by("type").values_list("type", flat=True).distinct()
    )

    type_labels = dict(Notification.NOTIFICATION_TYPES)
    tipos_disponiveis = [(t, type_labels.get(t, t.replace("_", " ").title())) for t in tipos_raw]
    tipos_disponiveis.sort(key=lambda x: x[1])

    context = {
        "notifications": page_obj,
        "stats": stats,
        "tipos_disponiveis": tipos_disponiveis,
        "filter_type": filter_type,
        "filter_read": filter_read,
        "filter_period": filter_period,
        "search_query": search_query,
        "page_obj": page_obj,
    }

    return render(request, "dashboard/notifications.html", context)
