import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


# ========== BADGE HELPERS ==========

STATUS_COLORS = {
    "aberto": "info",
    "em_andamento": "primary",
    "aguardando_cliente": "warning",
    "resolvido": "success",
    "fechado": "secondary",
}

PRIORITY_COLORS = {
    "baixa": "success",
    "media": "info",
    "alta": "warning",
    "urgente": "danger",
    "critica": "danger",
}


@register.simple_tag
def status_badge(status):
    """Retorna HTML de badge para o status do ticket."""
    color = STATUS_COLORS.get(str(status).lower(), "secondary")
    label = str(status).replace("_", " ").title()
    return mark_safe(f'<span class="badge bg-{color}">{label}</span>')


@register.simple_tag
def priority_badge(priority):
    """Retorna HTML de badge para a prioridade do ticket."""
    color = PRIORITY_COLORS.get(str(priority).lower(), "secondary")
    label = str(priority).replace("_", " ").title()
    return mark_safe(f'<span class="badge bg-{color}">{label}</span>')


@register.filter
def json_script(value):
    """
    Safely serialize a Python object as JSON for use in templates.
    """
    try:
        return mark_safe(json.dumps(value))
    except (ValueError, TypeError):
        return mark_safe("null")


@register.filter
def json_serialize(value):
    """
    Serialize a Python object as JSON.
    """
    try:
        return json.dumps(value)
    except (ValueError, TypeError):
        return "null"
