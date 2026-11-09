from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import override_settings

from weather.test_helpers import NOW, Area3Case

from .models import Notification, NotificationPreference
from .services import deliver_emails, notify, stop_url, weekly_digest


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SITE_URL="https://garden.example",
    EMAIL_POSTAL_ADDRESS="123 Garden St",
)
class NotificationTests(Area3Case):
    def setUp(self):
        super().setUp()
        self.pref = NotificationPreference.objects.create(
            user=self.user, timezone="America/Chicago"
        )

    def note(self, key="one", **kwargs):
        return notify(
            recipient=self.user,
            key=key,
            title="Water tomato",
            body="Task due",
            plant=self.garden,
            **kwargs,
        )

    def test_retry_dedupe(self):
        self.note()
        self.note()
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(deliver_emails(NOW), 1)
        self.assertEqual(deliver_emails(NOW), 0)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Stop reminders for this plant", mail.outbox[0].body)

    def test_quiet_hours_defer_except_frost(self):
        self.note()
        self.note("frost", kind="weather_alert", priority=0)
        quiet = NOW.replace(hour=4)
        self.assertEqual(deliver_emails(quiet), 1)
        self.assertEqual(Notification.objects.get(dedupe_key="frost").emailed_at, quiet)
        self.assertEqual(deliver_emails(NOW), 1)

    def test_daily_cap_and_priority(self):
        for i in range(4):
            self.note(str(i))
        self.note("frost", kind="weather_alert", priority=0)
        self.assertEqual(deliver_emails(NOW), 3)
        self.assertIsNotNone(Notification.objects.get(dedupe_key="frost").emailed_at)
        self.assertEqual(deliver_emails(NOW + timedelta(hours=1)), 0)
        self.assertEqual(deliver_emails(NOW + timedelta(days=1)), 2)

    def test_preferences_and_suppression(self):
        self.pref.reminder_email = False
        self.pref.frost_email = False
        self.pref.save()
        self.note()
        self.note("frost", kind="weather_alert", priority=0)
        self.assertEqual(deliver_emails(NOW), 0)
        self.pref.reminder_email = True
        self.pref.save()
        self.pref.suppressed_plants.add(self.garden)
        self.assertEqual(deliver_emails(NOW), 0)

    def test_email_failure_remains_retryable(self):
        self.note()
        with patch(
            "notifications.services.EmailMessage.send", side_effect=OSError("offline")
        ):
            self.assertEqual(deliver_emails(NOW), 0)
        self.assertIsNone(Notification.objects.get().emailed_at)
        self.assertEqual(deliver_emails(NOW), 1)
        self.assertEqual(Notification.objects.get().email_error, "")

    def test_digest_opt_in_and_weekly_dedupe(self):
        weekly_digest(NOW)
        self.assertFalse(Notification.objects.exists())
        self.pref.digest_email = True
        self.pref.save()
        weekly_digest(NOW)
        weekly_digest(NOW)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(deliver_emails(NOW), 1)
        self.assertIn("List-Unsubscribe", mail.outbox[0].extra_headers)

    def test_signed_unsubscribe_no_login_and_safe_get(self):
        url = stop_url(self.user.pk, self.garden.pk).replace(
            "https://garden.example", ""
        )
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertFalse(self.pref.suppressed_plants.exists())
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertTrue(self.pref.suppressed_plants.filter(pk=self.garden.pk).exists())
        self.assertEqual(
            self.client.post("/notifications/stop/invalid/").status_code, 400
        )

    def test_center_read_and_owner_boundaries(self):
        note = self.note()
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get("/notifications/"), "Water tomato")
        self.assertEqual(
            self.client.post(f"/notifications/{note.pk}/read/").status_code, 404
        )
        self.client.force_login(self.user)
        self.assertContains(self.client.get("/notifications/"), "Water tomato")
        self.client.post("/notifications/read/")
        note.refresh_from_db()
        self.assertIsNotNone(note.read_at)
        self.assertEqual(self.client.get("/notifications/settings/").status_code, 200)

    def test_dashboard_has_real_weather_not_mock(self):
        self.snapshot(current_temp_c=27.3)
        self.client.force_login(self.user)
        response = self.client.get("/garden/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "27.3")
        self.assertContains(response, 'data-name="tomato tomato"')   # row search text: nickname + species
        self.assertNotContains(response, "frost risk Thu")
