from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from .forms import LoginForm, SignupForm

def login_view(request):
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        return (redirect("garden:dashboard"))
    return render(request, "accounts/login.html", {"form": form})

def signup_view(request):
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        messages.success(request, "Account created successfully. Sign in to setup your garden and pick your first plant")
        return redirect("accounts:login")
    return render(request, "accounts/signup.html", {"form": form})

@require_POST
def logout_view(request):
    messages.info(request, "You have successfully logged out")
    return redirect("accounts:login")