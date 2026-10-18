"""Context shared by every template (header, sidebar, notifications, weather chip)."""
from . import mock_data as data


def app_shell(request):
    match = getattr(request, "resolver_match", None)
    unread = sum(1 for n in data.NOTIFICATIONS if n["unread"])
    usage = data.TUTOR_USAGE
    return {
        "gh_today": data.TODAY,
        "gh_user": data.USER,
        "gh_location": data.LOCATION,
        "gh_weather_now": data.WEATHER["current"],
        "gh_notifications": data.NOTIFICATIONS,
        "gh_unread": unread,
        "gh_tutor": {**usage, "pct": round(usage["used"] / usage["limit"] * 100)},
        # e.g. "garden:dashboard" — used to mark the current nav item
        "nav": f"{match.namespace}:{match.url_name}" if match else "",
    }
