from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('trigger-sync/', views.trigger_sync, name='trigger_sync'),
    path('sync-status/<str:task_id>/', views.sync_status, name='sync_status'),
    path('blocks/', views.blocks_list, name='blocks_list'),
    path('blocks/<int:block_id>/', views.block_detail, name='block_detail'),
    path('blocks/compare/', views.block_compare, name='block_compare'),
    path('blocks/new/', views.block_create, name='block_create'),
]
