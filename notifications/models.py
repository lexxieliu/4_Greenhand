from datetime import time

from django.conf import settings
from django.db import models

from weather.models import validate_timezone


class NotificationPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    timezone = models.CharField(
        max_length=64, default="UTC", validators=[validate_timezone]
    )
    reminder_email = models.BooleanField(default=True)
    frost_email = models.BooleanField(default=True)
    digest_email = models.BooleanField(default=False)
    quiet_start = models.TimeField(default=time(21))
    quiet_end = models.TimeField(default=time(7))
    suppressed_plants = models.ManyToManyField("garden.UserPlant", blank=True)


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    user_plant = models.ForeignKey(
        "garden.UserPlant", null=True, blank=True, on_delete=models.CASCADE
    )
    type = models.CharField(
        max_length=20,
        choices=[
            (x, x)
            for x in (
                "reminder",
                "weather_alert",
                "comment",
                "like",
                "digest",
                "system",
            )
        ],
    )
    title = models.CharField(max_length=120)
    body = models.TextField()
    link_url = models.CharField(max_length=300, default="/notifications/")
    dedupe_key = models.CharField(max_length=200, unique=True)
    priority = models.PositiveSmallIntegerField(default=2)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    emailed_at = models.DateTimeField(null=True, blank=True)
    email_error = models.TextField(blank=True)

    @property
    def unread(self):
        return self.read_at is None

    @property
    def icon(self):
        return "i-snow" if self.priority == 0 else "i-bell"

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "emailed_at"])]
