"""
URL configuration for controle_atendimento project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from dashboard.api_docs import urlpatterns as api_docs_urlpatterns
from django.conf import settings
from django.conf.urls.static import static
from dashboard import views
from dashboard.monitoring import HealthCheckView
from dashboard.sso import SSOProviderListView, SSOLoginView, SSOCallbackView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),  # Language switching
    path('', views.home_redirect, name='home'),  # Página inicial inteligente
    path('login/', views.custom_login, name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('health/', HealthCheckView.as_view(), name='health_check'),  # Health check na raiz
    path('dashboard/', include('dashboard.urls')),
    path('cliente/', include('dashboard.cliente_urls')),  # Portal Self-Service
    path('financeiro/', include('dashboard.financeiro_urls')),  # Módulo Financeiro
    path('estoque/', include('dashboard.estoque_urls')),  # Módulo de Estoque
    path('equipamentos/', include('dashboard.equipamento_urls')),  # Gestão de Equipamentos
    
    # SSO — Single Sign-On (SAML 2.0 + OIDC)
    path('sso/providers/', SSOProviderListView.as_view(), name='sso_providers'),
    path('sso/login/<slug:slug>/', SSOLoginView.as_view(), name='sso_login'),
    path('sso/callback/<slug:slug>/', SSOCallbackView.as_view(), name='sso_callback'),
    
    # APIs REST
    path('api/v1/', include('dashboard.api_urls')),
    path('api/user-info/', views.get_user_info, name='user_info'),
    
    # Mobile Interface
    path('mobile/', include('dashboard.mobile_urls')),
    
    # Cálculo de Implantação de Vigilante
    path('calculo-vigilante/', include('calculo_vigilante.urls')),
    
    # PWA Files
    path('manifest.json', views.manifest, name='manifest'),
    path('service-worker.js', views.service_worker, name='service_worker'),
    # Documentação automática das APIs (Swagger/Redoc)
    *api_docs_urlpatterns,
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
