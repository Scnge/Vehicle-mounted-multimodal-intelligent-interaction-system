from django.urls import path
from . import views

urlpatterns = [
    path('', views.integrated_home, name='integrated_home'),
    path('launch/', views.launch_demo, name='launch_demo'),
    path('status/', views.get_detection_data, name='get_detection_data'),
] 