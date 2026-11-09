"""Shared app shell: real identity, cached weather and persisted notifications."""

from django.utils import timezone

from notifications.models import Notification
from weather.client import cached_snapshot
from weather.models import Location

from . import mock_data as data


def app_shell(request):
    match = getattr(request, "resolver_match", None)
    user = request.user
    authenticated = user.is_authenticated
    location = Location.objects.filter(user=user).first() if authenticated else None
    snapshot = cached_snapshot(location) if location else None
    notifications = (
        Notification.objects.filter(recipient=user)
        if authenticated
        else Notification.objects.none()
    )
    name = (user.first_name or user.username) if authenticated else "Guest"
    usage = data.TUTOR_USAGE
    return {
        "gh_today": timezone.localdate(),
        "gh_user": {
            "initial": name[:1].upper(),
            "display_name": name,
            "username": user.username if authenticated else "",
        },
        "gh_location": {"label": location.label if location else "Set your location"},
        "gh_weather_now": {"temp_c": snapshot.current_temp_c, "icon": "i-cloud"}
        if snapshot
        else None,
        "gh_notifications": notifications[:8],
        "gh_unread": notifications.filter(read_at__isnull=True).count(),
        "gh_tutor": {**usage, "pct": round(usage["used"] / usage["limit"] * 100)},
        "nav": f"{match.namespace}:{match.url_name}" if match else "",
    }
