"""
URLs para interface mobile do iConnect
"""

from django.urls import path
from . import mobile_views

app_name = 'mobile'

urlpatterns = [
    # Dashboard Mobile
    path('', mobile_views.mobile_dashboard, name='mobile_dashboard'),
    
    # Tickets Mobile  
    path('tickets/', mobile_views.mobile_ticket_list, name='mobile_ticket_list'),
    path('create-ticket/', mobile_views.mobile_create_ticket, name='mobile_create_ticket'),
    path('tickets/<int:ticket_id>/', mobile_views.mobile_ticket_detail, name='mobile_ticket_detail'),
    
    # Notificações Mobile (placeholder)
    path('notifications/', mobile_views.mobile_dashboard, name='mobile_notifications'),
]
