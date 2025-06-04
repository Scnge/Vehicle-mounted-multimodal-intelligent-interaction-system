# forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
class CustomRegisterForm(UserCreationForm):
    username = forms.CharField(label='用户名')
    password1 = forms.CharField(label='密码', widget=forms.PasswordInput)
    password2 = forms.CharField(label='确认密码', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'password1', 'password2']
class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(
        label='用户名',
        widget=forms.TextInput(attrs={'placeholder': '请输入用户名'})
    )
    password = forms.CharField(
        label='密码',
        widget=forms.PasswordInput(attrs={'placeholder': '请输入密码'})
    )