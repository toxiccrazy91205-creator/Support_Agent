from django.urls import path
from . import views

urlpatterns = [
    path('webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('logs/', views.chat_logs_view, name='chat_logs'),
    path('tester/', views.chat_tester_view, name='chat_tester'),
]
