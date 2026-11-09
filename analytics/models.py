from django.conf import settings
from django.db import models
from django.utils import timezone


class AnalyticsEvent(models.Model):
    """Lightweight internal event log (PRD 7.2)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="analytics_events")
    name = models.CharField(max_length=60, db_index=True)
    properties = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-occurred_at"]

    def __str__(self):
        return f"{self.name} @ {self.occurred_at:%Y-%m-%d %H:%M}"
