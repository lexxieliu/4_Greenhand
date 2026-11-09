from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import LoginForm, SignupForm


def login_view(request):
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        candidates = get_user_model().objects.filter(
            email__iexact=form.cleaned_data["email"]
        )
        account = candidates.first() if candidates.count() == 1 else None
        user = authenticate(
            request,
            username=account.username if account else "",
            password=form.cleaned_data["password"],
        )
        if user is not None:
            login(request, user)
            if not form.cleaned_data["remember"]:
                request.session.set_expiry(0)
            return redirect("garden:dashboard")
        form.add_error(None, "Email or password is incorrect.")
    return render(request, "accounts/login.html", {"form": form})


def signup_view(request):
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        messages.success(
            request,
            "Account created successfully. Sign in to setup your garden and pick your first plant",
        )
        return redirect("userprofile:login")
    return render(request, "accounts/signup.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "You have successfully logged out")
    return redirect("userprofile:login")
