from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from django.utils import timezone

from .client import cached_snapshot, is_fresh
from .models import Location, WeatherAlert


def weather_cards(user):
    cards = []
    for location in Location.objects.filter(user=user):
        snapshot = cached_snapshot(location)
        daily = []
        if snapshot:
            # Aggregate UTC hourly forecast into this location's civil days.
            hourly = snapshot.forecast.get("hourly", {})
            grouped = {}
            today = timezone.now().astimezone(ZoneInfo(location.timezone)).date()
            for index, stamp in enumerate(hourly.get("time", [])):
                day = (
                    datetime.fromisoformat(stamp)
                    .replace(tzinfo=UTC)
                    .astimezone(ZoneInfo(location.timezone))
                    .date()
                )
                value = hourly["temperature_2m"][index]
                if day >= today and value is not None:
                    grouped.setdefault(day, []).append(value)
            daily = [
                {"date": day, "low": min(values), "high": max(values)}
                for day, values in sorted(grouped.items())[:7]
            ]
        cards.append(
            {
                "location": location,
                "snapshot": snapshot,
                "stale": not is_fresh(snapshot),
                "daily": daily,
            }
        )
    return cards


def active_alerts(user):
    return WeatherAlert.objects.filter(
        user=user,
        valid_from__lte=timezone.now(),
        valid_until__gt=timezone.now(),
        user_overrode=False,
    ).select_related("user_plant__plant")
