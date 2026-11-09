import json

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import (ExperienceForm, LocationChoiceForm, LocationSearchForm, LoginForm, ProfileForm,
                    SignupForm, SpaceForm, SunlightForm)
from .models import GrowingLocation, Profile
from .services import GeocodingError, search_places

REMEMBER_ME_SECONDS = 60 * 60 * 24 * 30


def _safe_next(request):
    """Return the ?next= target only if it stays on this site."""
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return target
    return "garden:dashboard"


def login_view(request):
    if request.user.is_authenticated:
        return redirect("userprofile:onboarding")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        # The form asks for an email, but Django authenticates by username.
        account = User.objects.filter(email__iexact=form.cleaned_data["email"]).first()
        user = account and authenticate(request, username=account.username, password=form.cleaned_data["password"])
        if user is None:
            form.add_error(None, "Incorrect email or password.")
        else:
            login(request, user)
            request.session.set_expiry(REMEMBER_ME_SECONDS if form.cleaned_data["remember"] else 0)
            if not Profile.objects.get_or_create(user=user)[0].onboarding_completed:
                return redirect("userprofile:onboarding")
            return redirect(_safe_next(request))
    return render(request, "accounts/login.html", {"form": form, "next": request.GET.get("next", "")})


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("garden:dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        User.objects.create_user(username=data["username"], email=data["email"], password=data["password"])
        messages.success(request, "Account created successfully. Sign in to setup your garden and pick your first plant")
        return redirect("userprofile:login")
    return render(request, "accounts/signup.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "You have successfully logged out")
    return redirect("userprofile:login")


# ---------- Onboarding wizard: location -> space -> sunlight -> experience (PRD 3.1) ----------

ONBOARDING_STEPS = 4
# step -> (form class, Profile field it fills)
PROFILE_STEPS = {2: (SpaceForm, "space_type"), 3: (SunlightForm, "sunlight_level"), 4: (ExperienceForm, "experience_level")}


def _location_step(request, location, done_url):
    """Step 1: search a city, then pick the right match. Returns (redirect or None, template context)."""
    context = {"search_form": LocationSearchForm(), "results": None, "location": location, "continue_url": done_url}
    if request.method != "POST":
        return None, context

    if "place" in request.POST:
        try:
            choice = LocationChoiceForm(json.loads(request.POST["place"]))
        except (ValueError, TypeError):
            choice = LocationChoiceForm({})
        if choice.is_valid():
            GrowingLocation.objects.update_or_create(user=request.user, defaults=choice.cleaned_data)
            return redirect(done_url), context
        context["error"] = "Pick one of the places below."

    search = LocationSearchForm(request.POST)
    context["search_form"] = search
    if search.is_valid():
        try:
            places = search_places(search.cleaned_data["query"])
        except GeocodingError:
            context["error"] = "We couldn't look that up right now. Check your connection and try again."
        else:
            context["results"] = [{**p, "value": json.dumps({k: p[k] for k in p if k != "label"})} for p in places]
    return None, context


@login_required
def onboarding(request, step=1):
    profile = Profile.objects.get_or_create(user=request.user)[0]
    if profile.onboarding_completed:
        return redirect("garden:dashboard")
    if not 1 <= step <= ONBOARDING_STEPS:
        return redirect("userprofile:onboarding", step=1)

    location = GrowingLocation.objects.filter(user=request.user).first()
    if step > 1 and location is None:
        messages.info(request, "Tell us where you grow first. It drives your weather and plant suggestions.")
        return redirect("userprofile:onboarding", step=1)

    context = {"step": step, "total": ONBOARDING_STEPS, "percent": step * 100 // ONBOARDING_STEPS}
    if step == 1:
        done, extra = _location_step(request, location, reverse("userprofile:onboarding", kwargs={"step": 2}))
        if done:
            return done
        context.update(extra)
    else:
        form_class, field = PROFILE_STEPS[step]
        form = form_class(request.POST if request.method == "POST" else None, initial={field: getattr(profile, field)})
        if request.method == "POST" and form.is_valid():
            setattr(profile, field, form.cleaned_data[field])
            if step == ONBOARDING_STEPS:
                profile.onboarding_completed = True
                profile.save()
                messages.success(request, "You're all set. Pick your first plant to start growing.")
                return redirect("plants:list")
            profile.save()
            return redirect("userprofile:onboarding", step=step + 1)
        context["form"] = form
        context["field"] = form[field]
    return render(request, "accounts/onboarding.html", context)


# ---------- Profile page (PRD 3.1) ----------

@login_required
def profile(request):
    profile = Profile.objects.get_or_create(user=request.user)[0]
    return render(request, "accounts/profile.html", {
        "profile": profile,
        "location": GrowingLocation.objects.filter(user=request.user).first(),
        "plant_count": request.user.my_garden_plants.count(),
    })


@login_required
def profile_edit(request):
    profile = Profile.objects.get_or_create(user=request.user)[0]
    form = ProfileForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("userprofile:profile")
    return render(request, "accounts/profile_edit.html", {"form": form, "profile": profile})


@login_required
def location_edit(request):
    """Change the growing location after onboarding (same search flow as wizard step 1)."""
    location = GrowingLocation.objects.filter(user=request.user).first()
    done, context = _location_step(request, location, reverse("userprofile:profile"))
    if done:
        messages.success(request, "Location updated.")
        return done
    return render(request, "accounts/onboarding.html", {**context, "step": 1, "standalone": True})
