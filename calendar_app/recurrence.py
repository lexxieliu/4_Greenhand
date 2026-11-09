"""Small explicit RRULE subset: DAILY/WEEKLY with INTERVAL, or one-off."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError


def parse_rule(rule):
    if not rule:
        return None
    try:
        pairs = [part.split("=") for part in rule.upper().split(";")]
        values = dict(pairs)
        if len(pairs) != len(values) or set(values) - {"FREQ", "INTERVAL"}:
            raise ValueError
        frequency = values["FREQ"]
        interval = int(values.get("INTERVAL", "1"))
        if frequency not in ("DAILY", "WEEKLY") or not 1 <= interval <= 365:
            raise ValueError
        return timedelta(days=interval * (7 if frequency == "WEEKLY" else 1))
    except (ValueError, KeyError):
        raise ValidationError(
            "Use FREQ=DAILY;INTERVAL=3 or FREQ=WEEKLY;INTERVAL=1. Leave blank for a one-off reminder."
        )


def local_to_utc(day, clock, zone):
    naive = datetime.combine(day, clock)
    tz = ZoneInfo(zone)
    # fold=0 selects the first occurrence in autumn. Move gaps to the first valid minute.
    for _ in range(1441):
        aware = naive.replace(tzinfo=tz, fold=0)
        utc = aware.astimezone(UTC)
        if utc.astimezone(tz).replace(tzinfo=None) == naive:
            return utc
        naive += timedelta(minutes=1)
    raise ValueError("No valid local time found")


def next_due(reminder, after):
    step = parse_rule(reminder.recurrence_rule)
    if step is None:
        return None
    day = after.astimezone(ZoneInfo(reminder.timezone)).date() + step
    return local_to_utc(day, reminder.time_of_day, reminder.timezone)
