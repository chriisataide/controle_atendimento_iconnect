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
