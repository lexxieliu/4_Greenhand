from datetime import time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from weather.models import validate_timezone


class Reminder(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    user_plant = models.ForeignKey(
        "garden.Garden", null=True, blank=True, on_delete=models.CASCADE
    )
    type = models.CharField(
        max_length=20,
        choices=[
            (x, x.replace("_", " ").title())
            for x in ("water", "fertilize", "check_problem", "harvest_check", "custom")
        ],
    )
    title = models.CharField(max_length=120)
    recurrence_rule = models.CharField(max_length=200, blank=True)
    next_due_at = models.DateTimeField(db_index=True)
    time_of_day = models.TimeField(default=time(8))
    timezone = models.CharField(
        max_length=64, default="UTC", validators=[validate_timezone]
    )
    is_active = models.BooleanField(default=True)
    weather_aware = models.BooleanField(default=True)

    @property
    def recurrence_label(self):
        from .recurrence import parse_rule

        step = parse_rule(self.recurrence_rule)
        if step is None:
            return "One-time reminder"
        return "Every day" if step.days == 1 else f"Every {step.days} days"

    def clean(self):
        from .recurrence import parse_rule

        parse_rule(self.recurrence_rule)
        if self.user_plant_id and self.user_id != self.user_plant.user_id:
            raise ValidationError("Choose a plant in your own garden.")


class ReminderOccurrence(models.Model):
    reminder = models.ForeignKey(
        Reminder, on_delete=models.CASCADE, related_name="occurrences"
    )
    due_at = models.DateTimeField(db_index=True)
    status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            (x, x)
            for x in (
                "pending",
                "sent",
                "done",
                "skipped_rain",
                "skipped_user",
                "missed",
            )
        ],
    )
    skip_reason = models.CharField(max_length=200, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    care_log = models.OneToOneField(
        "garden.CareLog", null=True, blank=True, on_delete=models.SET_NULL
    )
    overridden_at = models.DateTimeField(null=True, blank=True)
    weather_alert = models.ForeignKey(
        "weather.WeatherAlert", null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["reminder", "due_at"], name="unique_reminder_occurrence"
            )
        ]

    @property
    def status_label(self):
        return self.status.replace("_", " ").capitalize()


class ReminderOverride(models.Model):
    occurrence = models.ForeignKey(ReminderOccurrence, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    previous_status = models.CharField(max_length=20)
    reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CalendarEvent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    user_plant = models.ForeignKey(
        "garden.Garden", null=True, blank=True, on_delete=models.CASCADE
    )
    event_type = models.CharField(
        max_length=20,
        choices=[
            (x, x)
            for x in (
                "planted",
                "watering",
                "germination",
                "flowering",
                "fruiting",
                "harvest",
                "problem",
                "frost_alert",
                "custom",
            )
        ],
    )
    icon = models.CharField(max_length=30, default="i-calendar")
    title = models.CharField(max_length=120)
    date = models.DateField(db_index=True)
    source_type = models.CharField(max_length=30, blank=True)
    source_id = models.PositiveBigIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "source_id"], name="unique_calendar_source"
            )
        ]
