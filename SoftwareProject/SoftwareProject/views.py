from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from .forms import CustomRegisterForm
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from .forms import CustomLoginForm
from django.contrib.auth import logout
from django.shortcuts import redirect

def hello(request):
    return render(request, 'hello.html')

def home(request):
    context = {
        'title': '智能车载系统',
        'car_status': 'P',
        'temperature': 22.0,
        'playing_title': '虚拟',
        'playing_artist': '陈粒',
    }
    return render(request, 'index.html', context)

def admin_page(request):
    return render(request, 'admin.html')



def register(request):
    if request.method == 'POST':
        form = CustomRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = CustomRegisterForm()
    return render(request, 'register.html', {'form': form})


def custom_login(request):
    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # 根据用户权限跳转
            if user.is_staff or user.is_superuser:
                return redirect('admin_page')  # 跳转到你自己的 admin.html
            else:
                return redirect('home')
    else:
        form = CustomLoginForm()
    return render(request, 'login.html', {'form': form})

def custom_logout(request):
    logout(request)                 # 清除用户登录状态
    return redirect('login')       # 重定向到 login 页面