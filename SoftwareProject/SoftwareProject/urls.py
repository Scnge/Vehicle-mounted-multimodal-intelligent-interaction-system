"""
URL configuration for SoftwareProject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from . import views
from django.contrib.auth import views as auth_views
from .forms import CustomLoginForm  

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),  # 设置主页
    path('hello/', views.hello),
    # path('speech_recognition/', include('speech_recognition.urls')),  #lhz改 暂时注释掉speech_recognition
    path('gesture/', include('gesture.urls')),
    path('integrated/', include('integrated_view.urls')),
    path('speech/', include('speech.urls')),  # 添加speech应用URL
    path('admin-page/', views.admin_page, name='admin_page'),

    path('register/', views.register, name='register'),  # 自定义注册视图
    path('login/', views.custom_login, name='login'),
    path('logout/', views.custom_logout, name='logout'),

]
