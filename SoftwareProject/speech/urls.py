# /Users/kalami/大三下/软件工程/小组作业/Vehicle-mounted-multimodal-intelligent-interaction-system/SoftwareProject/speech/urls.py
from django.urls import path
from . import views
from .wake_word_api import check_wake_word_status

app_name = 'speech'

urlpatterns = [
    path('', views.speech_interface, name='speech_interface'),
    path('recognize/', views.speech_interface, name='recognize'),
    path('wake-word/', views.wake_word_redirect, name='wake_word_redirect'),
    path('check-wake-word/', check_wake_word_status, name='check_wake_word'),
    path('process/', views.process_speech_command, name='process_command'),
]