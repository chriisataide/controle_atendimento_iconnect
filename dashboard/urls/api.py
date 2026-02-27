"""
URLs da API para funcionalidades avancadas do iConnect
"""

from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from ..views import api as api_views
from ..api.ai import TicketAISuggestionView

app_name = 'api'

urlpatterns = [
    # Autenticacao - Token
    path('auth/token/', obtain_auth_token, name='api_token_auth'),
    
    # Autenticacao - JWT
    path('auth/jwt/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/jwt/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Health check
    path('health/', api_views.health_check, name='health-check'),
    
    # Tickets CRUD
    path('tickets/', api_views.TicketListCreateAPIView.as_view(), name='ticket-list-create'),
    path('tickets/<int:pk>/', api_views.TicketDetailAPIView.as_view(), name='ticket-detail'),
    path('tickets/bulk-action/', api_views.bulk_action_tickets, name='ticket-bulk-action'),
    path('tickets/<int:pk>/time-entries/', api_views.ticket_time_entries, name='ticket-time-entries'),
    path('tickets/<int:pk>/ai-triage/', api_views.ai_triage_ticket, name='ticket-ai-triage'),
    path('tickets/<int:pk>/ai-suggest-response/', api_views.ai_suggest_response, name='ticket-ai-suggest'),
    path('tickets/<int:pk>/ai-summarize/', api_views.ai_summarize_ticket, name='ticket-ai-summarize'),
    
    # Clientes CRUD
    path('clientes/', api_views.ClienteListCreateAPIView.as_view(), name='cliente-list-create'),
    path('clientes/<int:pk>/', api_views.ClienteDetailAPIView.as_view(), name='cliente-detail'),
    path('clientes/<int:pk>/health-score/', api_views.client_health_score, name='cliente-health-score'),
    
    # Canned Responses / Macros
    path('canned-responses/', api_views.CannedResponseListCreateAPIView.as_view(), name='canned-response-list'),
    path('canned-responses/<int:pk>/', api_views.CannedResponseDetailAPIView.as_view(), name='canned-response-detail'),
    
    # Webhooks management
    path('webhooks/', api_views.WebhookListCreateAPIView.as_view(), name='webhook-list'),
    path('webhooks/<int:pk>/', api_views.WebhookDetailAPIView.as_view(), name='webhook-detail'),
    path('webhooks/trigger/', api_views.webhook_external_trigger, name='webhook-trigger'),
    
    # API Keys management
    path('api-keys/', api_views.api_key_list_create, name='api-key-list'),
    path('api-keys/<int:pk>/', api_views.api_key_revoke, name='api-key-revoke'),
    
    # Analytics endpoints
    path('analytics/overview/', api_views.analytics_overview, name='analytics-overview'),
    path('analytics/time-series/', api_views.analytics_time_series, name='analytics-time-series'),
    path('analytics/satisfaction/', api_views.analytics_satisfaction, name='analytics-satisfaction'),
    path('analytics/sla/', api_views.analytics_sla_metrics, name='analytics-sla'),
    path('analytics/agent-performance/', api_views.analytics_agent_performance, name='analytics-agent'),
    path('analytics/period-comparison/', api_views.analytics_period_comparison, name='analytics-comparison'),
    
    # AI / Machine Learning
    path('ml/predict-priority/', api_views.ml_predict_priority, name='ml-predict-priority'),
    path('ml/predict-category/', api_views.ml_predict_category, name='ml-predict-category'),
    path('ml/predict-resolution-time/', api_views.ml_predict_resolution_time, name='ml-predict-resolution-time'),
    path('ml/suggest-ticket/', TicketAISuggestionView.as_view(), name='ml-suggest-ticket'),
    path('ml/sentiment/', api_views.ai_sentiment_analysis, name='ml-sentiment'),
    path('ml/find-duplicates/', api_views.ai_find_duplicates, name='ml-find-duplicates'),
    
    # Gamification / Leaderboard
    path('gamification/leaderboard/', api_views.gamification_leaderboard, name='gamification-leaderboard'),
    path('gamification/badges/', api_views.gamification_badges, name='gamification-badges'),
    
    # Shared Dashboards
    path('dashboards/shared/', api_views.shared_dashboard_list, name='shared-dashboard-list'),
    path('dashboards/shared/<str:token>/', api_views.shared_dashboard_view, name='shared-dashboard-view'),
    
    # Export
    path('export/tickets/', api_views.export_tickets_excel, name='export-tickets-excel'),
]
