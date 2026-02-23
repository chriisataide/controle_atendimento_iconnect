"""Template tags para Content Security Policy (CSP) nonces."""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def csp_nonce(context):
    """Retorna o atributo nonce para uso em tags <script> e <style>.

    Uso nos templates:
        {% load csp_tags %}
        <script nonce="{% csp_nonce %}">...</script>
        <style nonce="{% csp_nonce %}">...</style>

    O nonce é gerado pelo ``CSPNonceMiddleware`` e armazenado em
    ``request.csp_nonce``.  Se o middleware não estiver ativo, retorna
    string vazia (o script/style continua funcionando via 'unsafe-inline'
    como fallback no CSP).
    """
    request = context.get('request')
    if request and hasattr(request, 'csp_nonce'):
        return request.csp_nonce
    return ''
