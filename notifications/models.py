from django.conf import settings
from django.db import models


class Notification(models.Model):
    """One in-app notification (PRD 3.7 / 7.2). `dedupe_key` stops the same event notifying twice."""

    class Type(models.TextChoices):
        REMINDER = "reminder", "Reminder"
        WEATHER_ALERT = "weather_alert", "Weather alert"
        COMMENT = "comment", "Comment"
        LIKE = "like", "Like"
        DIGEST = "digest", "Digest"
        SYSTEM = "system", "System"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=14, choices=Type.choices)
    title = models.CharField(max_length=120)
    body = models.TextField(blank=True)
    link_url = models.CharField(max_length=300, blank=True)
    dedupe_key = models.CharField(max_length=80, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["recipient", "read_at"])]
        constraints = [models.UniqueConstraint(fields=["recipient", "dedupe_key"], condition=~models.Q(dedupe_key=""),
                                               name="unique_notification_per_event")]

    def __str__(self):
        return f"{self.recipient}: {self.title}"
