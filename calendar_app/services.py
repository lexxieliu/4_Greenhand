from datetime import time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from notifications.services import notify

from .models import CalendarEvent, Reminder, ReminderOccurrence, ReminderOverride
from .recurrence import local_to_utc, next_due

HORIZON_DAYS = 35                       # occurrences are materialized this far ahead
CARE_ACTION = {"water": "water", "fertilize": "fertilize"}   # reminder types that log a CareLog when done


def materialize(reminder, horizon):
    due = reminder.next_due_at
    while due <= horizon:
        occurrence, _ = ReminderOccurrence.objects.get_or_create(
            reminder=reminder, due_at=due
        )
        CalendarEvent.objects.get_or_create(
            source_type="reminder",
            source_id=occurrence.pk,
            defaults=dict(
                user=reminder.user,
                user_plant=reminder.user_plant,
                title=reminder.title,
                event_type="watering" if reminder.type == "water" else "custom",
                icon="i-drop" if reminder.type == "water" else "i-calendar",
                date=due.astimezone(ZoneInfo(reminder.timezone)).date(),
            ),
        )
        following = next_due(reminder, due)
        if following is None:
            break
        due = following


def prepare_occurrences(now=None, days=35):
    now = now or timezone.now()
    for reminder in Reminder.objects.filter(is_active=True).select_related(
        "user", "user_plant"
    ):
        materialize(reminder, now + timedelta(days=days))


def process_due(now=None):
    from weather.services import apply_rain_to_occurrence

    now = now or timezone.now()
    prepare_occurrences(now)
    count = 0
    for reminder_id in Reminder.objects.filter(
        is_active=True, next_due_at__lte=now
    ).values_list("pk", flat=True):
        with transaction.atomic():
            reminder = (
                Reminder.objects.select_for_update()
                .select_related("user", "user_plant")
                .get(pk=reminder_id)
            )
            while reminder.is_active and reminder.next_due_at <= now:
                occurrence = ReminderOccurrence.objects.select_for_update().get(
                    reminder=reminder, due_at=reminder.next_due_at
                )
                if occurrence.status == "pending":
                    if now - occurrence.due_at > timedelta(days=1):
                        occurrence.status = "missed"
                    else:
                        apply_rain_to_occurrence(occurrence, now)
                        if occurrence.status == "pending":
                            notify(
                                recipient=reminder.user,
                                key=f"reminder:{occurrence.pk}",
                                title=reminder.title,
                                body="Your garden care task is due.",
                                plant=reminder.user_plant,
                            )
                            occurrence.status = "sent"
                            count += 1
                    occurrence.save()
                following = next_due(reminder, reminder.next_due_at)
                if following is None:
                    reminder.is_active = False
                else:
                    reminder.next_due_at = following
            reminder.save(update_fields=["next_due_at", "is_active"])
    return count


@transaction.atomic
def act_on_occurrence(user, pk, action, reason=""):
    occurrence = (
        ReminderOccurrence.objects.select_for_update()
        .select_related("reminder")
        .get(pk=pk, reminder__user=user)
    )
    if action == "override" and occurrence.status in ("skipped_rain", "skipped_user"):
        ReminderOverride.objects.create(
            occurrence=occurrence,
            user=user,
            previous_status=occurrence.status,
            reason=reason[:200],
        )
        occurrence.status = "pending"
        occurrence.overridden_at = timezone.now()
        if occurrence.weather_alert_id:
            from weather.models import WeatherAlert

            WeatherAlert.objects.filter(pk=occurrence.weather_alert_id).update(
                user_overrode=True
            )
        notify(
            recipient=user,
            key=f"override:{occurrence.pk}",
            title=occurrence.reminder.title,
            body="You restored this care task. It is ready to complete.",
            plant=occurrence.reminder.user_plant,
        )
    elif action == "done" and occurrence.status in ("pending", "sent"):
        occurrence.status = "done"
        occurrence.completed_at = timezone.now()
        action = CARE_ACTION.get(occurrence.reminder.type)
        if action and occurrence.reminder.user_plant_id and not occurrence.care_log_id:
            from garden.models import CareLog

            occurrence.care_log = CareLog.objects.create(
                user_plant=occurrence.reminder.user_plant,
                action=action,
                performed_on=occurrence.completed_at.astimezone(ZoneInfo(occurrence.reminder.timezone)).date(),
                source=CareLog.Source.REMINDER,
                note="Completed from reminder",
            )
    elif action == "skip" and occurrence.status in ("pending", "sent"):
        occurrence.status = "skipped_user"
        occurrence.skip_reason = reason[:200] or "Skipped by user"
    occurrence.save()
    return occurrence


# ---------------------------------------------------------------------------
# Used by the garden (Area 2): Start Growing's automatic schedule, problem and harvest checks,
# and care logs that complete the matching task.
# ---------------------------------------------------------------------------

def user_timezone(user):
    """The user's notification timezone, else their first location's, else the server's."""
    from django.conf import settings

    from notifications.models import NotificationPreference
    from weather.models import Location

    preference = NotificationPreference.objects.filter(user=user).first()
    if preference:
        return preference.timezone
    location = Location.objects.filter(user=user).first()
    return location.timezone if location else settings.TIME_ZONE


def rule_for(interval_days):
    return f"FREQ=DAILY;INTERVAL={interval_days}" if interval_days else ""


def schedule(user_plant, type_, title, interval_days, first_day, *, time_of_day=time(8), weather_aware=False):
    """Create a plant reminder starting on first_day (user's local date) and materialize its occurrences."""
    zone = user_timezone(user_plant.user)
    reminder = Reminder.objects.create(
        user=user_plant.user, user_plant=user_plant, type=type_, title=title,
        recurrence_rule=rule_for(interval_days), next_due_at=local_to_utc(first_day, time_of_day, zone),
        time_of_day=time_of_day, timezone=zone, weather_aware=weather_aware,
    )
    materialize(reminder, timezone.now() + timedelta(days=HORIZON_DAYS))
    return reminder


def deactivate(user_plant, types=None):
    reminders = Reminder.objects.filter(user_plant=user_plant, is_active=True)
    if types:
        reminders = reminders.filter(type__in=types)
    reminders.update(is_active=False)


def reactivate(reminder, today):
    """Turn a paused reminder back on; if its due time has passed, start again from today (local)."""
    reminder.is_active = True
    if reminder.next_due_at < timezone.now():
        step = reminder.recurrence_rule and next_due(reminder, timezone.now())
        reminder.next_due_at = step or local_to_utc(today, reminder.time_of_day, reminder.timezone)
    reminder.save(update_fields=["is_active", "next_due_at"])
    materialize(reminder, timezone.now() + timedelta(days=HORIZON_DAYS))


@transaction.atomic
def complete_with_care_log(care_log):
    """A logged watering or feeding completes that plant's open task due by the next day (FR-24)."""
    reminder_type = next((t for t, a in CARE_ACTION.items() if a == care_log.action), None)
    if not reminder_type:
        return None
    for occurrence in (ReminderOccurrence.objects.select_for_update().select_related("reminder")
                       .filter(reminder__user_plant=care_log.user_plant, reminder__type=reminder_type,
                               reminder__is_active=True, status__in=("pending", "sent"), care_log__isnull=True)
                       .order_by("due_at")):
        local_day = occurrence.due_at.astimezone(ZoneInfo(occurrence.reminder.timezone)).date()
        if local_day <= care_log.performed_on + timedelta(days=1):
            occurrence.status = "done"
            occurrence.completed_at = timezone.now()
            occurrence.care_log = care_log
            occurrence.save(update_fields=["status", "completed_at", "care_log"])
            return occurrence
    return None
