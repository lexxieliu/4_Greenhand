"""Metric queries from PRD 1.5 and 7.3."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import DateTimeField, Exists, ExpressionWrapper, OuterRef
from django.utils import timezone

from garden.models import UserPlant

from .models import AnalyticsEvent

# PRD 1.5 "meaningful action": a care event, a photo, asking the tutor, or posting/commenting.
MEANINGFUL_EVENTS = ("care_logged", "photo_uploaded", "tutor_message_sent", "diagnosis_created",
                     "post_created", "comment_created")


def north_star():
    """Plants grown to harvest: at least one harvest log (Area 2 has no "harvested" status; plants keep producing)."""
    return UserPlant.objects.filter(harvests__isnull=False).distinct().count()


def harvest_success_rate():
    """harvested / (harvested + failed), or None with no finished plants. The PRD also counts active plants
    past their days_to_harvest_max in the denominator; Plant has no such field yet, so they are left out."""
    harvested = north_star()
    finished = harvested + UserPlant.objects.filter(status="failed").count()
    return harvested / finished if finished else None


def _after_signup(days):
    return ExpressionWrapper(OuterRef("date_joined") + timedelta(days=days), output_field=DateTimeField())


def retention(start=28, end=35, joined_after=None, joined_before=None):
    """Share of a signup cohort with a meaningful event on days start..end after signup (D30 = days 28-35).

    Only users whose whole window has passed are counted, so recent signups do not drag the rate down.
    Returns {"cohort", "retained", "rate"}; rate is None for an empty cohort."""
    cohort = get_user_model().objects.filter(date_joined__lte=timezone.now() - timedelta(days=end + 1))
    if joined_after:
        cohort = cohort.filter(date_joined__gte=joined_after)
    if joined_before:
        cohort = cohort.filter(date_joined__lt=joined_before)
    active = AnalyticsEvent.objects.filter(
        user=OuterRef("pk"), name__in=MEANINGFUL_EVENTS,
        occurred_at__gte=_after_signup(start), occurred_at__lt=_after_signup(end + 1),
    )
    size = cohort.count()
    retained = cohort.filter(Exists(active)).count()
    return {"cohort": size, "retained": retained, "rate": retained / size if size else None}


def d30_retention(**cohort):
    return retention(28, 35, **cohort)
