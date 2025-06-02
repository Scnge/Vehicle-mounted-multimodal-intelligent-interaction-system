from django.http import HttpResponse
from django.shortcuts import render


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