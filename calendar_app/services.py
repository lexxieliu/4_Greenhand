from datetime import timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from notifications.services import notify

from .models import CalendarEvent, Reminder, ReminderOccurrence, ReminderOverride
from .recurrence import next_due


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
        if occurrence.reminder.user_plant_id and not occurrence.care_log_id:
            from garden.models import CareLog

            occurrence.care_log = CareLog.objects.create(
                user_plant=occurrence.reminder.user_plant,
                action=occurrence.reminder.type,
                performed_at=occurrence.completed_at,
                note="Completed from reminder",
            )
    elif action == "skip" and occurrence.status in ("pending", "sent"):
        occurrence.status = "skipped_user"
        occurrence.skip_reason = reason[:200] or "Skipped by user"
    occurrence.save()
    return occurrence
