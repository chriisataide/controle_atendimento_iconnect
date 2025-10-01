"""
URLs da API para funcionalidades avançadas do iConnect
"""

from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from . import api_views
from .api_ai import TicketAISuggestionView

app_name = 'api'

urlpatterns = [
    # Autenticação
    path('auth/token/', obtain_auth_token, name='api_token_auth'),
    
    # Tickets CRUD
    path('tickets/', api_views.TicketListCreateAPIView.as_view(), name='ticket-list-create'),
    path('tickets/<int:pk>/', api_views.TicketDetailAPIView.as_view(), name='ticket-detail'),
    
    # Clientes CRUD
    path('clientes/', api_views.ClienteListCreateAPIView.as_view(), name='cliente-list-create'),
    path('clientes/<int:pk>/', api_views.ClienteDetailAPIView.as_view(), name='cliente-detail'),
    
    # Analytics endpoints
    path('analytics/overview/', api_views.analytics_overview, name='analytics-overview'),
    path('analytics/time-series/', api_views.analytics_time_series, name='analytics-time-series'),
    path('analytics/satisfaction/', api_views.analytics_satisfaction, name='analytics-satisfaction'),
    path('analytics/sla/', api_views.analytics_sla_metrics, name='analytics-sla'),
    
    # Machine Learning
    path('ml/predict-priority/', api_views.ml_predict_priority, name='ml-predict-priority'),
    path('ml/predict-category/', api_views.ml_predict_category, name='ml-predict-category'),
    path('ml/predict-resolution-time/', api_views.ml_predict_resolution_time, name='ml-predict-resolution-time'),
    # IA: sugestão automática de prioridade/categoria
    path('ml/suggest-ticket/', TicketAISuggestionView.as_view(), name='ml-suggest-ticket'),
    
    # Chatbot IA
]
