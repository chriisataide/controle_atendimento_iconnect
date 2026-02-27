# =============================================================================
# Dashboard URLs Package
# =============================================================================
# Re-exporta os urlpatterns do módulo principal para manter compatibilidade
# com includes como: include('dashboard.urls')
# =============================================================================

from .main import urlpatterns, app_name, mobile_urlpatterns  # noqa: F401
