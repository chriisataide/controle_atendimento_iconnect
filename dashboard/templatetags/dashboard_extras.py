import json
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def json_script(value):
    """
    Safely serialize a Python object as JSON for use in templates.
    """
    try:
        return mark_safe(json.dumps(value))
    except (ValueError, TypeError):
        return mark_safe('null')

@register.filter
def json_serialize(value):
    """
    Serialize a Python object as JSON.
    """
    try:
        return json.dumps(value)
    except (ValueError, TypeError):
        return 'null'


# ===== STATUS & PRIORITY BADGES — Design System Padronizado =====

STATUS_LABELS = {
    'aberto': 'Aberto',
    'em_andamento': 'Em Andamento',
    'aguardando_cliente': 'Aguardando',
    'resolvido': 'Resolvido',
    'fechado': 'Fechado',
}

PRIORITY_LABELS = {
    'baixa': 'Baixa',
    'media': 'Média',
    'alta': 'Alta',
    'critica': 'Crítica',
    'urgente': 'Crítica',  # alias
}

TIPO_LABELS = {
    'incidente': 'Incidente',
    'requisicao': 'Requisição',
    'problema': 'Problema',
    'mudanca': 'Mudança',
}


@register.simple_tag
def status_badge(status, size='sm'):
    """Renderiza badge de status padronizado com classes do design system."""
    key = str(status).lower().strip() if status else 'fechado'
    label = STATUS_LABELS.get(key, key.replace('_', ' ').title())
    size_class = ' badge-sm' if size == 'sm' else ''
    return mark_safe(
        f'<span class="ic-badge ic-badge-{key}{size_class}">{label}</span>'
    )


@register.simple_tag
def priority_badge(priority, size='sm'):
    """Renderiza badge de prioridade padronizado com classes do design system."""
    key = str(priority).lower().strip() if priority else 'baixa'
    if key == 'urgente':
        key = 'critica'
    label = PRIORITY_LABELS.get(key, key.title())
    size_class = ' badge-sm' if size == 'sm' else ''
    return mark_safe(
        f'<span class="ic-badge ic-badge-{key}{size_class}">{label}</span>'
    )


@register.simple_tag
def tipo_badge(tipo, size='sm'):
    """Renderiza badge de tipo ITIL padronizado."""
    key = str(tipo).lower().strip() if tipo else ''
    label = TIPO_LABELS.get(key, key.replace('_', ' ').title())
    size_class = ' badge-sm' if size == 'sm' else ''
    return mark_safe(
        f'<span class="ic-badge ic-badge-{key}{size_class}">{label}</span>'
    )


@register.filter
def status_color(status):
    """Retorna a cor CSS do status para usar em charts/legends."""
    colors = {
        'aberto': '#ef4444',
        'em_andamento': '#f59e0b',
        'aguardando_cliente': '#64748b',
        'resolvido': '#22c55e',
        'fechado': '#334155',
    }
    return colors.get(str(status).lower().strip(), '#94a3b8')


@register.filter
def priority_color(priority):
    """Retorna a cor CSS da prioridade para usar em charts/legends."""
    colors = {
        'baixa': '#64748b',
        'media': '#06b6d4',
        'alta': '#f59e0b',
        'critica': '#ef4444',
        'urgente': '#ef4444',
    }
    return colors.get(str(priority).lower().strip(), '#94a3b8')
