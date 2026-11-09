"""Event tracking. Analytics must never break the action being tracked."""
import logging

from django.db import DatabaseError, transaction

from .models import AnalyticsEvent

logger = logging.getLogger(__name__)


def track(name, user=None, **properties):
    try:
        with transaction.atomic():      # a failed insert must not poison the caller's transaction
            AnalyticsEvent.objects.create(name=name, user=user, properties=properties)
    except DatabaseError:
        logger.exception("Could not record analytics event %s", name)
