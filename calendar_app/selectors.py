from .models import CalendarEvent


def calendar_payload(user):
    events = {}
    kinds = {
        "watering": "water",
        "frost_alert": "weather",
        "harvest": "harvest",
        "problem": "problem",
    }
    for event in CalendarEvent.objects.filter(user=user).order_by("date"):
        events.setdefault(event.date.isoformat(), []).append(
            {
                "type": kinds.get(event.event_type, "growth"),
                "label": event.title,
                "icon": event.icon,
            }
        )
    return events


def projected_events(user, start, end, plant_id=None):
    """Read-only projection beyond the background job's materialized horizon."""
    from zoneinfo import ZoneInfo

    from .models import Reminder, ReminderOccurrence
    from .recurrence import local_to_utc, next_due, parse_rule

    reminders = Reminder.objects.filter(user=user, is_active=True)
    if plant_id:
        reminders = reminders.filter(user_plant_id=plant_id)
    projected = []
    for reminder in reminders:
        due = reminder.next_due_at
        tz = ZoneInfo(reminder.timezone)
        step = parse_rule(reminder.recurrence_rule)
        day = due.astimezone(tz).date()
        if step and day < start:
            jumps = max(0, (start - day).days // step.days)
            due = local_to_utc(
                day + jumps * step, reminder.time_of_day, reminder.timezone
            )
        stored = set(
            ReminderOccurrence.objects.filter(reminder=reminder).values_list(
                "due_at", flat=True
            )
        )
        while due.astimezone(tz).date() < end:
            day = due.astimezone(tz).date()
            if day >= start and due not in stored:
                projected.append(
                    {
                        "date": day,
                        "title": reminder.title,
                        "icon": "i-drop" if reminder.type == "water" else "i-calendar",
                    }
                )
            due = next_due(reminder, due)
            if due is None:
                break
    return projected
