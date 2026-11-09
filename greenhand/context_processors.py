"""Context shared by every template (header, sidebar, notifications, weather chip)."""
from . import mock_data as data


def _real_user(request):
    """Header/sidebar identity for a signed-in user (the rest of the shell still runs on mock data)."""
    from userprofile.models import GrowingLocation, Profile
    user = request.user
    profile = Profile.objects.filter(user=user).first()
    location = GrowingLocation.objects.filter(user=user).first()
    name = (profile and profile.display_name) or user.username
    gh_user = {
        "display_name": name,
        "username": user.username,
        "initial": name[:1].upper(),
        "avatar_url": profile.avatar.url if profile and profile.avatar else "",
        "experience_level": profile.get_experience_level_display() if profile else "",
        "space_type": (profile.get_space_type_display() if profile else "") or "Space not set",
        "sunlight_level": (profile.get_sunlight_level_display() if profile else "") or "Sun not set",
    }
    gh_location = None
    if location:
        label = ", ".join(part for part in (location.city, location.region) if part)
        gh_location = {**data.LOCATION, "city": location.city, "region": location.region, "label": label}
    return gh_user, gh_location


def app_shell(request):
    match = getattr(request, "resolver_match", None)
    unread = sum(1 for n in data.NOTIFICATIONS if n["unread"])
    usage = data.TUTOR_USAGE
    gh_user, gh_location = _real_user(request) if request.user.is_authenticated else (None, None)
    return {
        "gh_today": data.TODAY,
        "gh_user": gh_user or data.USER,
        "gh_location": gh_location or data.LOCATION,
        "gh_weather_now": data.WEATHER["current"],
        "gh_notifications": data.NOTIFICATIONS,
        "gh_unread": unread,
        "gh_tutor": {**usage, "pct": round(usage["used"] / usage["limit"] * 100)},
        # e.g. "garden:dashboard" — used to mark the current nav item
        "nav": f"{match.namespace}:{match.url_name}" if match else "",
    }
