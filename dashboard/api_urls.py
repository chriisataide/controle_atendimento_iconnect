"""
URLs da API para funcionalidades avançadas do iConnect
"""

from django.urls import path
from . import api_views

app_name = 'api'

urlpatterns = [
    # Analytics endpoints
    path('analytics/', api_views.analytics_data, name='analytics_data'),
    path('dashboard/stats/', api_views.dashboard_stats_realtime, name='dashboard_stats'),
    
    # Notifications endpoints
    path('notifications/', api_views.notifications_list, name='notifications_list'),
    path('notifications/mark-read/', api_views.mark_notifications_read, name='mark_notifications_read'),
    path('notifications/<int:notification_id>/delete/', api_views.delete_notification, name='delete_notification'),
    
    # PWA endpoints
    path('push-subscription/', api_views.register_push_subscription, name='register_push_subscription'),
    
    # Tickets endpoints
    path('tickets/search/', api_views.tickets_search, name='tickets_search'),
    path('tickets/<int:ticket_id>/activity/', api_views.ticket_activity, name='ticket_activity'),
]
