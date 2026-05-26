from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('trigger-sync/', views.trigger_sync, name='trigger_sync'),
    path('sync-status/<str:task_id>/', views.sync_status, name='sync_status'),
]
