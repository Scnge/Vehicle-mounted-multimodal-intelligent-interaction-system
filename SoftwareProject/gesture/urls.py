from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='gesture_index'),
    path('video_feed/', views.video_feed, name='video_feed'),
    path('update_params/', views.update_params, name='update_params'),
]