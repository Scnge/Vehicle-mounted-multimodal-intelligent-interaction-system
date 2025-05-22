from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.recognize_speech, name='recognize_speech'),
]