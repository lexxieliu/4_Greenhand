from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from calendar_app.models import CalendarEvent, ReminderOccurrence
from notifications.services import notify

from .client import cached_snapshot, get_snapshot, is_fresh, location_key
from .models import PlantWeatherSettings, WeatherAlert


def make_alert(config, snapshot, kind, message, now, valid_until):
    day = now.astimezone(ZoneInfo(config.location.timezone)).date()
    alert, created = WeatherAlert.objects.get_or_create(
        dedupe_key=f"{config.user_plant_id}:{kind}:{day}",
        defaults=dict(
            user=config.user_plant.user,
            user_plant=config.user_plant,
            snapshot=snapshot,
            alert_type=kind,
            message=message,
            valid_from=now,
            valid_until=valid_until,
        ),
    )
    if created:
        notify(
            recipient=config.user_plant.user,
            key=f"weather:{alert.pk}",
            title={
                "rain_skip": "Rain did the watering today",
                "frost": "Frost risk",
                "heat": "Heat alert",
            }[kind],
            body=message,
            kind="weather_alert",
            plant=config.user_plant,
            priority=0 if kind == "frost" else 2,
            link="/weather/",
        )
        CalendarEvent.objects.get_or_create(
            source_type="weather",
            source_id=alert.pk,
            defaults=dict(
                user=config.user_plant.user,
                user_plant=config.user_plant,
                title=(
                    config.user_plant.nickname
                    + " · "
                    + {
                        "frost": "Frost alert",
                        "rain_skip": "Watering skipped after rain",
                        "heat": "Heat alert",
                    }[kind]
                )[:120],
                date=day,
                event_type="frost_alert" if kind == "frost" else "custom",
                icon={"frost": "i-snow", "rain_skip": "i-rain", "heat": "i-sun"}[kind],
            ),
        )
    return alert


def apply_rain_to_occurrence(occurrence, now, config=None, snapshot=None):
    reminder = occurrence.reminder
    if (
        occurrence.status != "pending"
        or occurrence.overridden_at
        or reminder.type != "water"
        or not reminder.weather_aware
        or not reminder.user_plant_id
    ):
        return
    config = (
        config
        or PlantWeatherSettings.objects.filter(user_plant_id=reminder.user_plant_id)
        .select_related("location", "user_plant__user", "user_plant__plant")
        .first()
    )
    if config is None or config.setting != "outdoor":
        return
    snapshot = snapshot or cached_snapshot(config.location)
    if not is_fresh(snapshot, now):
        return
    tz = ZoneInfo(config.location.timezone)
    today = now.astimezone(tz).date()
    if occurrence.due_at.astimezone(tz).date() != today:
        return
    if snapshot.rain_last_24h_mm < 5 and snapshot.precip_prob_next_12h < 70:
        return
    reason = f"{snapshot.rain_last_24h_mm:g} mm rain in 24h; {snapshot.precip_prob_next_12h}% rain chance in 12h"
    alert = make_alert(
        config,
        snapshot,
        "rain_skip",
        reason + ". Outdoor watering skipped; you can override it.",
        now,
        datetime.combine(today + timedelta(days=1), time.min, tzinfo=tz),
    )
    occurrence.status = "skipped_rain"
    occurrence.skip_reason = reason
    occurrence.weather_alert = alert
    occurrence.save(update_fields=["status", "skip_reason", "weather_alert"])


def refresh_weather(now=None):
    from calendar_app.services import prepare_occurrences

    now = now or timezone.now()
    prepare_occurrences(now)
    snapshots = {}
    configs = (
        PlantWeatherSettings.objects.select_related("location", "user_plant__user", "user_plant__plant")
        .filter(user_plant__user__is_active=True)
        .exclude(
            user_plant__status__in=["failed", "archived", "completed"]
        )
    )
    for config in configs:
        key = location_key(config.location)
        if key not in snapshots:
            snapshots[key] = get_snapshot(config.location, now)
        snapshot = snapshots[key]
        if config.setting != "outdoor" or not is_fresh(snapshot, now):
            continue
        with transaction.atomic():
            occurrences = (
                ReminderOccurrence.objects.select_for_update()
                .filter(
                    reminder__user_plant=config.user_plant,
                    reminder__is_active=True,
                    status="pending",
                    due_at__gte=now - timedelta(days=1),
                    due_at__lte=now + timedelta(days=1),
                )
                .select_related("reminder")
            )
            for occurrence in occurrences:
                apply_rain_to_occurrence(occurrence, now, config, snapshot)
            if (
                not config.frost_tolerant
                and snapshot.min_temp_next_48h_c <= config.frost_threshold_c
            ):
                make_alert(
                    config,
                    snapshot,
                    "frost",
                    f"{config.user_plant.nickname}: temperatures may reach {snapshot.min_temp_next_48h_c:g} °C within 48h. Cover plants, move pots indoors, or water soil before frost.",
                    now,
                    now + timedelta(hours=48),
                )
            if snapshot.max_temp_next_48h_c >= 32:
                make_alert(
                    config,
                    snapshot,
                    "heat",
                    f"{config.user_plant.nickname}: temperatures may reach {snapshot.max_temp_next_48h_c:g} °C. Check soil moisture, consider extra watering and provide shade.",
                    now,
                    now + timedelta(hours=48),
                )
    return len(snapshots)
