from django.urls import path
from . import views

urlpatterns = [
    path('webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('logs/', views.chat_logs_view, name='chat_logs'),
    path('tester/', views.chat_tester_view, name='chat_tester'),
    
    # Email Agent Routes
    path('email/', views.email_inbox_view, name='email_inbox'),
    path('email/<int:email_id>/', views.review_email_view, name='email_review'),
    path('email/<int:email_id>/action/', views.approve_and_send_email_view, name='email_action'),
]
