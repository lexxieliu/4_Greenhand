"""Creating and reading notifications (PRD 3.7), and the weather rules that raise them (FR-41/42)."""
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince

from garden import services as garden_services
from garden.selectors import garden, weather_alerts
from plants.selectors import catalog_by_slug
from weather.services import weather_for

from .models import Notification

Type = Notification.Type
PANEL_SIZE = 10
# How each type looks in the header panel: (icon id, tint classes)
STYLE = {
    Type.REMINDER: ("i-bell", "bg-mist text-forest"),
    Type.WEATHER_ALERT: ("i-alert", "bg-indigo-100 text-indigo-700"),
    Type.COMMENT: ("i-post", "bg-mist text-forest"),
    Type.LIKE: ("i-heart", "bg-rose-100 text-rose-600"),
    Type.DIGEST: ("i-sparkles", "bg-lime-100 text-forest"),
    Type.SYSTEM: ("i-bell", "bg-mist text-forest"),
}


def notify(recipient, type_, title, body="", link_url="", dedupe_key=""):
    """Create a notification; returns None when this event (same dedupe_key) already notified the user."""
    try:
        with transaction.atomic():
            return Notification.objects.create(recipient=recipient, type=type_, title=title[:120], body=body,
                                               link_url=link_url, dedupe_key=dedupe_key)
    except IntegrityError:
        return None


def panel(user):
    """The header panel: the latest notifications in the shape the template shows, and the unread total."""
    rows = [{
        "id": n.pk, "icon": STYLE[n.type][0], "tint": STYLE[n.type][1], "title": n.title,
        "body": f"{n.body} · {timesince(n.created_at)} ago" if n.body else f"{timesince(n.created_at)} ago",
        "unread": n.read_at is None, "url": reverse("notifications:open", args=[n.pk]),
    } for n in Notification.objects.filter(recipient=user)[:PANEL_SIZE]]
    return rows, Notification.objects.filter(recipient=user, read_at__isnull=True).count()


def mark_read(user, notification_id=None):
    rows = Notification.objects.filter(recipient=user, read_at__isnull=True)
    if notification_id is not None:
        rows = rows.filter(pk=notification_id)
    rows.update(read_at=timezone.now())


def sync_weather(user):
    """Raise frost and rain alerts from the live forecast, once per event. The first rain alert of a day also
    skips today's weather-aware outdoor watering reminders (FR-41); the user can put them back."""
    weather = weather_for(user)
    if not weather:
        return
    plants = garden(user)
    link = reverse("garden:dashboard")
    for alert in weather_alerts(weather, plants, catalog_by_slug()):
        created = notify(user, Type.WEATHER_ALERT, alert["title"], alert["message"], link, dedupe_key=alert["id"])
        if created and alert["alert_type"] == "rain_skip":
            garden_services.skip_watering_for_rain(user, alert["message"][:200])
