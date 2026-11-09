from django import forms
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .models import Notification, NotificationPreference


class PreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = [
            "timezone",
            "reminder_email",
            "frost_email",
            "digest_email",
            "quiet_start",
            "quiet_end",
        ]
        widgets = {
            "quiet_start": forms.TimeInput(attrs={"type": "time"}),
            "quiet_end": forms.TimeInput(attrs={"type": "time"}),
        }


@login_required
def center(request):
    return render(
        request,
        "notifications/center.html",
        {"notifications": Notification.objects.filter(recipient=request.user)[:100]},
    )


@login_required
@require_POST
def mark_read(request, pk=None):
    items = Notification.objects.filter(recipient=request.user, read_at__isnull=True)
    if pk is not None:
        get_object_or_404(Notification, pk=pk, recipient=request.user)
        items = items.filter(pk=pk)
    items.update(read_at=timezone.now())
    return redirect("notifications:center")


@login_required
def preferences(request):
    pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
    form = PreferenceForm(request.POST or None, instance=pref)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("notifications:center")
    return render(request, "notifications/preferences.html", {"form": form})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def unsubscribe(request, token):
    # The signed bearer token authorizes only suppression. GET never mutates state.
    try:
        data = signing.loads(token, salt="notification-stop")
        pref = get_object_or_404(NotificationPreference, user_id=data["user"])
    except (signing.BadSignature, KeyError, TypeError):
        return HttpResponseBadRequest("Invalid unsubscribe link")
    if request.method == "POST":
        if data.get("category") == "digest":
            pref.digest_email = False
        elif data.get("plant"):
            plant = get_object_or_404(pref.user.my_garden_plants, pk=data["plant"])
            pref.suppressed_plants.add(plant)
        else:
            pref.reminder_email = False
            pref.frost_email = False
        pref.save()
    return render(
        request, "notifications/unsubscribe.html", {"stopped": request.method == "POST"}
    )
