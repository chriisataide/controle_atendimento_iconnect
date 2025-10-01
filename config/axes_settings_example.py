"""
Exemplo de configuração do django-axes para proteção contra brute-force
"""
INSTALLED_APPS_EXTRA = ['axes']
MIDDLEWARE_EXTRA = ['axes.middleware.AxesMiddleware']

AXES_ENABLED = True
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # em horas
AXES_LOCKOUT_TEMPLATE = 'registration/lockout.html'
AXES_USE_USER_AGENT = True
AXES_ONLY_USER_FAILURES = True
AXES_RESET_ON_SUCCESS = True
