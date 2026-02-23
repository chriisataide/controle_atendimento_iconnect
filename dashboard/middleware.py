"""
Middleware customizado para iConnect.
"""
import secrets

from django.utils.deprecation import MiddlewareMixin


class CSPNonceMiddleware(MiddlewareMixin):
    """Gera um nonce criptográfico por request para uso em Content-Security-Policy.

    O nonce é armazenado em ``request.csp_nonce`` e pode ser acessado nos
    templates via o template tag ``{% csp_nonce %}``.

    O SecurityHeadersMiddleware (em security.py) lê ``request.csp_nonce``
    para incluí-lo no header CSP.  Se este middleware não estiver ativo,
    o header CSP continua funcionando com ``'unsafe-inline'`` como fallback.
    """

    def process_request(self, request):
        # 32 bytes → 43 chars base64-url-safe
        request.csp_nonce = secrets.token_urlsafe(32)

    def process_response(self, request, response):
        return response
