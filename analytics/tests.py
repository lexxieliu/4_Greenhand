from datetime import timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import DatabaseError
from django.test import TestCase
from django.utils import timezone
from django.utils.text import slugify

from garden.models import CareLog, Harvest, UserPlant
from greenhand.clock import today
from plants.models import Plant

from . import queries
from .models import AnalyticsEvent
from .services import track


def grow(user, name, status):
    plant = Plant.objects.create(common_name=name, slug=slugify(name))
    return UserPlant.objects.create(user=user, plant=plant, nickname=name, planted_on=today(), status=status, watering_interval_days=3)


def user_joined(name, days_ago):
    return User.objects.create_user(name, date_joined=timezone.now() - timedelta(days=days_ago))


def event_on_day(user, day, name="tutor_message_sent"):
    return AnalyticsEvent.objects.create(user=user, name=name, occurred_at=user.date_joined + timedelta(days=day))


class TrackTests(TestCase):
    def test_records_event(self):
        track("post_created", None, post_type="tip")
        self.assertEqual(AnalyticsEvent.objects.get().properties, {"post_type": "tip"})

    def test_failure_never_breaks_the_caller(self):
        with mock.patch.object(AnalyticsEvent.objects, "create", side_effect=DatabaseError):
            track("post_created")


class SignalTests(TestCase):
    def test_garden_activity_is_tracked(self):
        user = User.objects.create_user("u")
        plant = grow(user, "Basil", "growing")
        CareLog.objects.create(user_plant=plant, action="water", performed_on=today())
        Harvest.objects.create(user_plant=plant, harvested_on=today())
        names = set(AnalyticsEvent.objects.values_list("name", flat=True))
        self.assertEqual(names, {"plant_started", "care_logged", "harvest_logged"})


class NorthStarTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u")

    def _plant(self, name, status, harvests=0):
        plant = grow(self.user, name, status)
        for _ in range(harvests):
            Harvest.objects.create(user_plant=plant, harvested_on=today())

    def test_counts_plants_with_a_harvest_log_once(self):
        self._plant("Two harvests", "producing", 2)
        self._plant("No log", "growing", 0)
        self.assertEqual(queries.north_star(), 1)

    def test_success_rate(self):
        self.assertIsNone(queries.harvest_success_rate())
        self._plant("A", "completed", 1)
        self._plant("B", "failed")
        self.assertEqual(queries.harvest_success_rate(), 0.5)


class RetentionTests(TestCase):
    def test_window_is_days_28_to_35(self):
        inside_start, inside_end = user_joined("a", 60), user_joined("b", 60)
        before, after = user_joined("c", 60), user_joined("d", 60)
        event_on_day(inside_start, 28)
        event_on_day(inside_end, 35.5)
        event_on_day(before, 27.9)
        event_on_day(after, 36)
        self.assertEqual(queries.d30_retention(), {"cohort": 4, "retained": 2, "rate": 0.5})

    def test_only_meaningful_events_count(self):
        event_on_day(user_joined("a", 60), 30, name="page_viewed")
        self.assertEqual(queries.d30_retention()["retained"], 0)

    def test_users_still_inside_the_window_are_excluded(self):
        event_on_day(user_joined("a", 30), 29)
        self.assertEqual(queries.d30_retention(), {"cohort": 0, "retained": 0, "rate": None})

    def test_cohort_bounds(self):
        user_joined("old", 200)
        user_joined("new", 60)
        result = queries.d30_retention(joined_after=timezone.now() - timedelta(days=100))
        self.assertEqual(result["cohort"], 1)

    def test_one_user_counted_once_with_many_events(self):
        user = user_joined("a", 60)
        event_on_day(user, 29)
        event_on_day(user, 30, name="care_logged")
        self.assertEqual(queries.d30_retention()["retained"], 1)

    def test_metrics_command(self):
        out = StringIO()
        call_command("metrics", stdout=out)
        self.assertIn("North Star", out.getvalue())
        self.assertIn("D30 retention: n/a", out.getvalue())
