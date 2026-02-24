# Test Suite iConnect - Organizado por módulo
# Importa todos os módulos de teste para autodiscovery do Django

# Módulos organizados
from .test_models import *  # noqa: F401,F403
from .test_api import *  # noqa: F401,F403
from .test_services import *  # noqa: F401,F403
from .test_views import *  # noqa: F401,F403
from .test_sso import *  # noqa: F401,F403
from .test_ticket_operations import *  # noqa: F401,F403
from .test_workflows import *  # noqa: F401,F403
from .test_tenants import *  # noqa: F401,F403

# Testes legados (arquivo original monolítico — migrar gradualmente para os módulos acima)
from dashboard.tests_legacy import *  # noqa: F401,F403
