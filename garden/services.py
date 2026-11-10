"""Operations that change My Garden (PRD 3.3, FR-13, FR-20 – FR-28).

Views validate input with garden/forms.py and call these functions; nothing here touches HTTP.
Each function takes an already-owned UserPlant (see selectors.get_user_plant), so ownership is
checked once, at lookup.
"""
from datetime import timedelta

from django.db import transaction

from greenhand.clock import now as clock_now, today

from .models import CareLog, Harvest, Problem, Reminder, ReminderOccurrence, TimelineEntry, UserPlant

Status = UserPlant.Status
ACTIVE = (Status.SPROUTING, Status.GROWING, Status.FLOWERING, Status.FRUITING, Status.PRODUCING)
ENDED = (Status.COMPLETED, Status.FAILED, Status.ARCHIVED)
# Growth order, used so a timeline entry never moves a plant backwards
GROWTH_ORDER = [Status.PLANNED, Status.SPROUTING, Status.GROWING, Status.FLOWERING, Status.FRUITING, Status.PRODUCING]
STAGE_STATUS = {"seed": Status.SPROUTING, "seedling": Status.SPROUTING, "vegetative": Status.GROWING,
                "flowering": Status.FLOWERING, "fruiting": Status.FRUITING}

# Care schedule (FR-24)
FEED_INTERVAL_DAYS = 14                                 # PRD: about every 2–3 weeks
FIRST_FEED_AFTER_DAYS = {"seed": 21, "seedling": 14, "cutting": 14}   # seedlings need true leaves first
PROBLEM_CHECK_AFTER_DAYS = 3                            # PRD: check_problem 3 days after a problem
HARVEST_CHECK_INTERVAL_DAYS = {"continuous": 4, "single": 7}         # PRD: every 3–5 days for continuous crops
CARE_FOR_REMINDER = {Reminder.Type.WATER: CareLog.Action.WATER, Reminder.Type.FERTILIZE: CareLog.Action.FERTILIZE}


class GardenError(Exception):
    """A request that is valid input but not allowed in the plant's current state (message is user-facing)."""


def _reminder(user_plant, type_, title, interval_days, next_due_on, **extra):
    return Reminder.objects.create(user=user_plant.user, user_plant=user_plant, type=type_, title=title,
                                   interval_days=interval_days, next_due_on=next_due_on, **extra)


def _deactivate(user_plant, types=None):
    reminders = user_plant.reminders.filter(is_active=True)
    if types:
        reminders = reminders.filter(type__in=types)
    reminders.update(is_active=False)


@transaction.atomic
def start_growing(user, plant, *, nickname, planted_on, start_method, setting, container_type="", quantity=1):
    """FR-13: add a plant to My Garden with its first timeline entry and an automatic care schedule."""
    planned = planted_on > today()
    user_plant = UserPlant.objects.create(
        user=user, plant=plant, nickname=nickname or plant.common_name, planted_on=planted_on,
        start_method=start_method, setting=setting, container_type=container_type, quantity=quantity,
        status=Status.PLANNED if planned else (Status.SPROUTING if start_method == "seed" else Status.GROWING),
        watering_interval_days=plant.watering_interval_days,
        current_stage_updated_at=None if planned else clock_now(),
    )
    if not planned:
        verb = "Sowed" if start_method == "seed" else "Planted"
        TimelineEntry.objects.create(user_plant=user_plant, stage="seed" if start_method == "seed" else "seedling",
                                     recorded_on=planted_on, note=f"{verb} {user_plant.nickname}.")
    first_water = planted_on if planned else today() + timedelta(days=1)
    _reminder(user_plant, Reminder.Type.WATER, f"Water {user_plant.nickname}", user_plant.watering_interval_days,
              first_water, weather_aware=setting == UserPlant.Setting.OUTDOOR)
    _reminder(user_plant, Reminder.Type.FERTILIZE, f"Feed {user_plant.nickname}", FEED_INTERVAL_DAYS,
              planted_on + timedelta(days=FIRST_FEED_AFTER_DAYS[start_method]), notify_email=False)
    return user_plant


def _advance_status(user_plant, target):
    """Move forward along GROWTH_ORDER only, and never over a status the user set themselves."""
    if user_plant.status in ENDED or user_plant.status_source == UserPlant.StatusSource.USER:
        return False
    if GROWTH_ORDER.index(target) <= GROWTH_ORDER.index(user_plant.status):
        return False
    user_plant.status = target
    user_plant.status_source = UserPlant.StatusSource.AUTO
    user_plant.current_stage_updated_at = clock_now()
    user_plant.save(update_fields=["status", "status_source", "current_stage_updated_at", "updated_at"])
    if target == Status.FRUITING:
        _start_harvest_checks(user_plant)
    return True


def _start_harvest_checks(user_plant):
    """FR-24: harvest_check reminders begin when the plant starts fruiting."""
    if user_plant.reminders.filter(type=Reminder.Type.HARVEST_CHECK, is_active=True).exists():
        return
    interval = HARVEST_CHECK_INTERVAL_DAYS[user_plant.plant.harvest_mode]
    _reminder(user_plant, Reminder.Type.HARVEST_CHECK, f"Check {user_plant.nickname} for harvest", interval,
              today() + timedelta(days=interval), notify_email=False)


@transaction.atomic
def add_timeline_entry(user_plant, *, stage, recorded_on, note="", photo=None, update_status=True):
    """FR-21. Returns the new status label when the entry moved the plant to a new stage, else None."""
    TimelineEntry.objects.create(user_plant=user_plant, stage=stage, recorded_on=recorded_on, note=note, photo=photo)
    target = STAGE_STATUS.get(stage)
    if user_plant.status == Status.PLANNED and stage != "harvest":
        target = target or Status.SPROUTING
    elif not update_status:
        return None
    if target and _advance_status(user_plant, target):
        return user_plant.get_status_display()
    return None


def _mark_occurrence_done(reminder, done_on, interval_days):
    ReminderOccurrence.objects.create(reminder=reminder, due_on=done_on, status=ReminderOccurrence.Status.DONE)
    if interval_days:
        reminder.next_due_on = done_on + timedelta(days=interval_days)
        reminder.save(update_fields=["next_due_on", "updated_at"])
    else:
        reminder.is_active = False
        reminder.save(update_fields=["is_active", "updated_at"])


@transaction.atomic
def skip_watering_for_rain(user, reason):
    """FR-41: rain did the watering. Skip today's due watering reminders of the user's outdoor plants that follow the
    weather. Returns how many were skipped."""
    day = today()
    due = Reminder.objects.filter(user=user, type=Reminder.Type.WATER, is_active=True, weather_aware=True,
                                  next_due_on__lte=day, user_plant__setting="outdoor", user_plant__status__in=ACTIVE)
    count = 0
    for reminder in due:
        ReminderOccurrence.objects.create(reminder=reminder, due_on=day, status=ReminderOccurrence.Status.SKIPPED_RAIN,
                                          reason=reason)
        if reminder.interval_days:
            reminder.next_due_on = day + timedelta(days=reminder.interval_days)
            reminder.save(update_fields=["next_due_on", "updated_at"])
        count += 1
    return count


@transaction.atomic
def undo_rain_skip(reminder):
    """The user's override: put today's rain-skipped watering back on the list."""
    skipped = reminder.occurrences.filter(status=ReminderOccurrence.Status.SKIPPED_RAIN, due_on=today()).first()
    if not skipped:
        raise GardenError("This watering was not skipped for rain.")
    reminder.next_due_on = skipped.due_on
    reminder.save(update_fields=["next_due_on", "updated_at"])
    skipped.delete()


@transaction.atomic
def log_care(user_plant, *, action, performed_on, amount="", note="", source=CareLog.Source.MANUAL):
    """FR-22. Watering also completes a watering reminder that is due by the next day."""
    log = CareLog.objects.create(user_plant=user_plant, action=action, performed_on=performed_on, amount=amount,
                                 note=note, source=source)
    reminder_type = next((t for t, a in CARE_FOR_REMINDER.items() if a == action), None)
    if reminder_type:
        reminder = user_plant.reminders.filter(type=reminder_type, is_active=True,
                                               next_due_on__lte=performed_on + timedelta(days=1)).first()
        if reminder:
            _mark_occurrence_done(reminder, performed_on, reminder.interval_days or user_plant.watering_interval_days)
    return log


@transaction.atomic
def complete_reminder(reminder):
    """One-tap Done on a task (FR-24): log the matching care action, or just record the occurrence."""
    action = CARE_FOR_REMINDER.get(reminder.type)
    if action and reminder.user_plant:
        return log_care(reminder.user_plant, action=action, performed_on=today(), source=CareLog.Source.REMINDER)
    _mark_occurrence_done(reminder, today(), reminder.interval_days)
    return None


@transaction.atomic
def log_problem(user_plant, *, title, description="", category="unknown", severity="medium", photo=None):
    """FR-25: log a problem and schedule the 3-day follow-up check."""
    problem = Problem.objects.create(user_plant=user_plant, title=title, description=description, category=category,
                                     severity=severity, photo=photo, opened_on=today())
    _reminder(user_plant, Reminder.Type.CHECK_PROBLEM, f"Check: {title}", 0,
              today() + timedelta(days=PROBLEM_CHECK_AFTER_DAYS), time="09:00", notify_email=False)
    return problem


@transaction.atomic
def set_problem_status(problem, status, resolution_note=""):
    problem.status = status
    if status == Problem.Status.RESOLVED:
        problem.resolved_at = clock_now()
        problem.resolution_note = resolution_note
        if not problem.user_plant.problems.exclude(pk=problem.pk).exclude(status=Problem.Status.RESOLVED).exists():
            _deactivate(problem.user_plant, [Reminder.Type.CHECK_PROBLEM])
    else:
        problem.resolved_at = None
    problem.save(update_fields=["status", "resolved_at", "resolution_note", "updated_at"])
    return problem


@transaction.atomic
def log_harvest(user_plant, *, harvested_on, quantity=None, unit="g", note="", photo=None, final=False):
    """FR-27. The first harvest sets first_harvest_at (North Star). Continuous crops become `producing`
    and keep accepting harvests; single-harvest crops, or a harvest marked final, become `completed`."""
    if user_plant.status in (Status.FAILED, Status.ARCHIVED):
        raise GardenError("This plant is no longer growing, so it can't be harvested.")
    harvest = Harvest.objects.create(user_plant=user_plant, harvested_on=harvested_on, quantity=quantity, unit=unit,
                                     note=note, photo=photo)
    fields = ["status", "status_source", "updated_at"]
    if user_plant.first_harvest_at is None:
        user_plant.first_harvest_at = clock_now()
        fields.append("first_harvest_at")
    if final or user_plant.plant.harvest_mode == "single":
        user_plant.status = Status.COMPLETED
        _deactivate(user_plant)
    elif user_plant.status != Status.COMPLETED:
        user_plant.status = Status.PRODUCING
    user_plant.status_source = UserPlant.StatusSource.AUTO
    user_plant.save(update_fields=fields)
    return harvest


@transaction.atomic
def change_status(user_plant, status, failure_reason=""):
    """Manual status change from the status menu. The user's choice is never overwritten later (FR-29)."""
    if status in (Status.PRODUCING, Status.COMPLETED) and not user_plant.harvests.exists():
        raise GardenError("Log a harvest first. It marks the plant as producing or completed.")
    if status == Status.FAILED:
        if not failure_reason:
            raise GardenError("Choose what went wrong before marking the plant as failed.")
        user_plant.failure_reason = failure_reason
        user_plant.failed_at = clock_now()
        _deactivate(user_plant)
    elif user_plant.status == Status.FAILED:
        user_plant.failure_reason = ""
        user_plant.failed_at = None
    if status == Status.FRUITING:
        _start_harvest_checks(user_plant)
    user_plant.status = status
    user_plant.status_source = UserPlant.StatusSource.USER
    user_plant.current_stage_updated_at = clock_now()
    user_plant.save()
    return user_plant


def add_reminder(user_plant, *, type_, interval_days, time):
    titles = {"water": f"Water {user_plant.nickname}", "fertilize": f"Feed {user_plant.nickname}",
              "check_problem": f"Check {user_plant.nickname}", "harvest_check": f"Check {user_plant.nickname} for harvest",
              "custom": f"{user_plant.nickname} reminder"}
    first_due = today() + timedelta(days=interval_days or 1)
    return _reminder(user_plant, type_, titles[type_], interval_days, first_due, time=time, is_auto=False,
                     weather_aware=type_ == "water" and user_plant.setting == UserPlant.Setting.OUTDOOR)


REMINDER_FLAGS = {"active": "is_active", "inapp": "notify_in_app", "email": "notify_email", "weather_aware": "weather_aware"}


def set_reminder_flag(reminder, flag, value):
    """Toggle one switch on the Reminders tab. Turning a lapsed reminder back on schedules it from today."""
    setattr(reminder, REMINDER_FLAGS[flag], value)
    if flag == "active" and value and reminder.next_due_on < today():
        reminder.next_due_on = today() + timedelta(days=reminder.interval_days) if reminder.interval_days else today()
    reminder.is_auto = False                     # user-edited reminders are kept when the schedule is regenerated
    reminder.save()
    return reminder
