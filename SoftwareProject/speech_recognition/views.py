from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.

def hello(request):
    return HttpResponse("Hello world ! ")

def recognize_speech(request):
    return render(request, 'speech_recognition/recognize.html')


