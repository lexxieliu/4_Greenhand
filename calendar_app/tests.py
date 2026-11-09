from datetime import date, time, timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.urls import reverse

from notifications.models import Notification
from weather.test_helpers import NOW, Area3Case

from .models import CalendarEvent, Reminder, ReminderOccurrence
from .recurrence import local_to_utc, next_due, parse_rule
from .services import act_on_occurrence, prepare_occurrences, process_due


class ReminderTests(Area3Case):
    def test_dst_gap_moves_to_nearest_valid_minute(self):
        result = local_to_utc(date(2026, 3, 8), time(2, 30), "America/Chicago")
        self.assertEqual(result.isoformat(), "2026-03-08T08:00:00+00:00")

    def test_dst_fold_fires_first_once(self):
        result = local_to_utc(date(2026, 11, 1), time(1, 30), "America/Chicago")
        self.assertEqual(result.isoformat(), "2026-11-01T06:30:00+00:00")
        self.reminder.time_of_day = time(1, 30)
        self.assertEqual(
            next_due(self.reminder, result).isoformat(), "2026-11-02T07:30:00+00:00"
        )

    def test_recurrence_preserves_wall_clock_across_dst(self):
        before = local_to_utc(date(2026, 3, 7), time(8), "America/Chicago")
        self.assertEqual(
            (next_due(self.reminder, before) - before).total_seconds(), 23 * 3600
        )
        before = local_to_utc(date(2026, 10, 31), time(8), "America/Chicago")
        self.assertEqual(
            (next_due(self.reminder, before) - before).total_seconds(), 25 * 3600
        )

    def test_invalid_rules_rejected(self):
        for rule in [
            "FREQ=HOURLY",
            "FREQ=DAILY;COUNT=3",
            "FREQ=DAILY;INTERVAL=0",
            "FREQ=DAILY;INTERVAL=x",
            "FREQ=DAILY;FREQ=WEEKLY",
        ]:
            with self.assertRaises(ValidationError):
                parse_rule(rule)
        self.assertEqual(parse_rule("FREQ=WEEKLY;INTERVAL=2"), timedelta(days=14))
        self.assertIsNone(parse_rule(""))

    def test_due_retry_is_idempotent(self):
        self.assertEqual(process_due(NOW), 1)
        self.assertEqual(process_due(NOW), 0)
        self.assertEqual(Notification.objects.count(), 1)
        self.reminder.refresh_from_db()
        self.assertEqual(self.reminder.next_due_at, NOW + timedelta(days=1))
        self.assertEqual(ReminderOccurrence.objects.get(due_at=NOW).status, "sent")

    def test_rain_check_at_delivery(self):
        self.snapshot(rain_last_24h_mm=5)
        self.assertEqual(process_due(NOW), 0)
        self.assertEqual(
            ReminderOccurrence.objects.get(due_at=NOW).status, "skipped_rain"
        )

    def test_one_off_deactivates_and_done_is_idempotent(self):
        self.reminder.recurrence_rule = ""
        self.reminder.save()
        process_due(NOW)
        self.reminder.refresh_from_db()
        self.assertFalse(self.reminder.is_active)
        occurrence = ReminderOccurrence.objects.get()
        act_on_occurrence(self.user, occurrence.pk, "done")
        act_on_occurrence(self.user, occurrence.pk, "done")
        self.assertEqual(ReminderOccurrence.objects.get().status, "done")

    def test_old_tasks_missed_not_emailed(self):
        self.reminder.next_due_at = NOW - timedelta(days=4)
        self.reminder.save()
        process_due(NOW)
        self.assertEqual(ReminderOccurrence.objects.filter(status="missed").count(), 3)
        self.assertEqual(Notification.objects.count(), 2)

    def test_calendar_no_duplicate_events(self):
        prepare_occurrences(NOW)
        first = CalendarEvent.objects.count()
        prepare_occurrences(NOW)
        self.assertEqual(CalendarEvent.objects.count(), first)

    def test_auth_and_cross_user_permissions(self):
        prepare_occurrences(NOW)
        occurrence = ReminderOccurrence.objects.first()
        self.assertEqual(self.client.get("/calendar/").status_code, 302)
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.post(
                reverse("calendar_app:action", args=[occurrence.pk]), {"action": "done"}
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f"/calendar/?plant={self.garden.pk}").status_code, 404
        )
        self.assertEqual(
            self.client.post(
                reverse("calendar_app:pause", args=[self.reminder.pk])
            ).status_code,
            404,
        )

    def test_calendar_filters_and_invalid_month(self):
        prepare_occurrences(NOW)
        self.client.force_login(self.user)
        response = self.client.get("/calendar/?month=2026-11")
        self.assertContains(response, "Water tomato")
        self.assertEqual(self.client.get("/calendar/?month=bad").status_code, 400)
        self.assertEqual(self.client.get("/calendar/?plant=abc").status_code, 404)
        self.assertEqual(
            self.client.get(reverse("calendar_app:action", args=[1])).status_code, 405
        )

    def test_create_reminder_form(self):
        self.client.force_login(self.user)
        response = self.client.post(
            "/calendar/reminders/new/",
            {
                "user_plant": self.garden.pk,
                "type": "fertilize",
                "title": "Feed tomato",
                "start_date": "2026-11-10",
                "time_of_day": "08:00",
                "timezone": "America/Chicago",
                "frequency": "WEEKLY",
                "interval": 2,
            },
        )
        self.assertEqual(response.status_code, 302)
        reminder = Reminder.objects.get(title="Feed tomato")
        self.assertEqual(reminder.next_due_at.hour, 14)

    def test_pause_removes_future_calendar_entries(self):
        prepare_occurrences(NOW)
        self.client.force_login(self.user)
        with patch("calendar_app.views.timezone.now", return_value=NOW):
            self.client.post(reverse("calendar_app:pause", args=[self.reminder.pk]))
        self.assertFalse(CalendarEvent.objects.filter(date__gt=NOW.date()).exists())

    def test_done_creates_exactly_one_care_log(self):
        from garden.models import CareLog

        prepare_occurrences(NOW)
        occurrence = ReminderOccurrence.objects.get(due_at=NOW)
        act_on_occurrence(self.user, occurrence.pk, "done")
        act_on_occurrence(self.user, occurrence.pk, "done")
        self.assertEqual(CareLog.objects.count(), 1)
        occurrence.refresh_from_db()
        self.assertEqual(occurrence.care_log.action, "water")

    def test_far_future_month_projects_without_writes(self):
        self.client.force_login(self.user)
        response = self.client.get("/calendar/?month=2027-04")
        self.assertContains(response, "Water tomato")
        self.assertFalse(ReminderOccurrence.objects.exists())

    def test_calendar_manual_event_and_owner_scope(self):
        self.client.force_login(self.user)
        response = self.client.post(
            "/calendar/events/new/",
            {
                "user_plant": self.garden.pk,
                "event_type": "germination",
                "title": "First sprout",
                "date": "2026-11-10",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CalendarEvent.objects.get().icon, "i-sprout")
        self.client.force_login(self.other)
        response = self.client.post(
            "/calendar/events/new/",
            {
                "user_plant": self.garden.pk,
                "event_type": "harvest",
                "title": "Not mine",
                "date": "2026-11-10",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CalendarEvent.objects.count(), 1)

    def test_commands_share_lock_and_retry_safely(self):
        from io import StringIO
        from tempfile import TemporaryDirectory

        from django.core.management import CommandError, call_command

        from .jobs import job_lock

        with (
            TemporaryDirectory() as directory,
            self.settings(
                BASE_DIR=directory,
                EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            ),
        ):
            with patch("calendar_app.services.timezone.now", return_value=NOW):
                call_command("process_reminders", stdout=StringIO())
                call_command("process_reminders", stdout=StringIO())
            self.assertEqual(Notification.objects.count(), 1)
            with job_lock():
                with self.assertRaises(CommandError):
                    call_command("send_notifications", stdout=StringIO())
            call_command("send_weekly_digest", stdout=StringIO())
            with patch("weather.client.fetch_forecast", side_effect=OSError):
                call_command("refresh_weather", stdout=StringIO())

    def test_existing_email_login_establishes_session(self):
        response = self.client.post(
            "/accounts/login/",
            {"email": self.user.email, "password": "test-pass-123", "remember": True},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
        self.assertEqual(self.client.get("/calendar/").status_code, 200)
        self.client.post("/accounts/logout/")
        self.assertNotIn("_auth_user_id", self.client.session)
