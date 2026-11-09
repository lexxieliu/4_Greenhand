from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import LoginForm, SignupForm
from .models import Profile


def _authenticate_by_email(request, email, password):
    account = User.objects.filter(email__iexact=email).first()
    return authenticate(request, username=account.username, password=password) if account else None


def login_view(request):
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = _authenticate_by_email(request, form.cleaned_data["email"], form.cleaned_data["password"])
        if user is None:
            form.add_error(None, "That email and password don’t match.")
        else:
            login(request, user)
            if not form.cleaned_data["remember"]:
                request.session.set_expiry(0)       # ends when the browser closes
            next_url = request.POST.get("next", "")
            if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                return redirect(next_url)
            return redirect("garden:dashboard")
    return render(request, "accounts/login.html", {"form": form})

def signup_view(request):
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = User.objects.create_user(form.cleaned_data["username"], form.cleaned_data["email"], form.cleaned_data["password"])
        Profile.objects.create(user=user)
        messages.success(request, "Account created successfully. Sign in to setup your garden and pick your first plant")
        return redirect("userprofile:login")
    return render(request, "accounts/signup.html", {"form": form})

@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "You have successfully logged out")
    return redirect("userprofile:login")
