"""
Exemplo de configuração do django-two-factor-auth para 2FA
"""

LOGIN_URL = "two_factor:login"
LOGIN_REDIRECT_URL = "/admin/"
TWO_FACTOR_PATCH_ADMIN = True
