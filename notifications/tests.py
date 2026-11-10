from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from community.models import Post
from garden import services as garden_services
from garden.models import Reminder, ReminderOccurrence
from greenhand.clock import today
from plants.models import Plant
from userprofile.models import GrowingLocation
from weather import services as weather_services
from weather.tests import live_payload

from . import services
from .models import Notification

Type = Notification.Type


class NotifyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("maya", "maya@example.com", "pass12345")

    def test_same_event_notifies_once(self):
        first = services.notify(self.user, Type.LIKE, "Dave liked your post", dedupe_key="like-1-2")
        again = services.notify(self.user, Type.LIKE, "Dave liked your post", dedupe_key="like-1-2")
        self.assertIsNotNone(first)
        self.assertIsNone(again)
        self.assertEqual(Notification.objects.count(), 1)

    def test_without_a_key_every_call_notifies(self):
        services.notify(self.user, Type.COMMENT, "A")
        services.notify(self.user, Type.COMMENT, "A")
        self.assertEqual(Notification.objects.count(), 2)

    def test_panel_counts_unread_and_mark_read(self):
        other = User.objects.create_user("dave", "dave@example.com", "pass12345")
        services.notify(self.user, Type.COMMENT, "One")
        services.notify(self.user, Type.COMMENT, "Two")
        services.notify(other, Type.COMMENT, "Not mine")
        rows, unread = services.panel(self.user)
        self.assertEqual((len(rows), unread), (2, 2))
        services.mark_read(self.user, rows[0]["id"])
        self.assertEqual(services.panel(self.user)[1], 1)
        services.mark_read(self.user)
        self.assertEqual(services.panel(self.user)[1], 0)
        self.assertEqual(services.panel(other)[1], 1)


class ViewTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("maya", "maya@example.com", "pass12345")
        self.other = User.objects.create_user("dave", "dave@example.com", "pass12345")
        self.post = Post.objects.create(author=self.author, body="My basil is leggy")

    def test_comment_and_like_notify_the_author_once(self):
        self.client.force_login(self.other)
        self.client.post(reverse("community:comment", args=[self.post.pk]), {"body": "Pinch the top!"})
        for _ in range(3):      # like, unlike, like again
            self.client.post(reverse("community:like", args=[self.post.pk]))
        kinds = sorted(Notification.objects.filter(recipient=self.author).values_list("type", flat=True))
        self.assertEqual(kinds, [Type.COMMENT, Type.LIKE])

    def test_own_activity_does_not_notify(self):
        self.client.force_login(self.author)
        self.client.post(reverse("community:comment", args=[self.post.pk]), {"body": "Note to self"})
        self.client.post(reverse("community:like", args=[self.post.pk]))
        self.assertEqual(Notification.objects.count(), 0)

    def test_open_marks_read_and_redirects_only_for_the_owner(self):
        note = services.notify(self.author, Type.COMMENT, "Hi", link_url="/community/#post-1")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("notifications:open", args=[note.pk])).status_code, 404)
        self.client.force_login(self.author)
        self.assertRedirects(self.client.get(reverse("notifications:open", args=[note.pk])), "/community/#post-1",
                             fetch_redirect_response=False)
        note.refresh_from_db()
        self.assertIsNotNone(note.read_at)

    def test_read_all_is_post_only_and_clears_the_badge(self):
        services.notify(self.author, Type.COMMENT, "Hi")
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(reverse("notifications:read_all")).status_code, 405)
        self.client.post(reverse("notifications:read_all"))
        self.assertEqual(services.panel(self.author)[1], 0)

    def test_header_shows_real_notifications(self):
        services.notify(self.author, Type.COMMENT, "dave commented on your post")
        self.client.force_login(self.author)
        self.assertContains(self.client.get(reverse("community:feed")), "dave commented on your post")


class WeatherRuleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        call_command("seed_plants", verbosity=0)
        self.user = User.objects.create_user("maya", "maya@example.com", "pass12345")
        GrowingLocation.objects.create(user=self.user, city="Chicago", region="IL", latitude="41.88", longitude="-87.63")
        self.basil = garden_services.start_growing(self.user, Plant.objects.get(slug="basil"), nickname="Balcony Basil",
                                                   planted_on=today(), start_method="seedling", setting="outdoor")
        self.water = Reminder.objects.get(user_plant=self.basil, type="water")
        Reminder.objects.filter(pk=self.water.pk).update(next_due_on=today(), weather_aware=True)

    def sync(self, **kwargs):
        with mock.patch.object(weather_services, "_fetch", return_value=live_payload(timezone.now(), **kwargs)):
            services.sync_weather(self.user)

    def test_frost_and_rain_alerts_are_created_once(self):
        self.sync()
        self.sync()
        titles = list(Notification.objects.filter(recipient=self.user).values_list("title", flat=True))
        self.assertEqual(len(titles), 2)
        self.assertTrue(any("Frost risk" in t for t in titles))
        self.assertTrue(any("Rain" in t for t in titles))

    def test_rain_skips_todays_watering_and_the_user_can_override(self):
        self.sync()
        occurrence = ReminderOccurrence.objects.get(reminder=self.water)
        self.assertEqual((occurrence.status, occurrence.due_on), ("skipped_rain", today()))
        self.water.refresh_from_db()
        self.assertGreater(self.water.next_due_on, today())
        self.sync()      # the same alert never skips twice
        self.assertEqual(ReminderOccurrence.objects.filter(reminder=self.water).count(), 1)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse("garden:unskip_reminder", args=[self.water.pk])).status_code, 200)
        self.water.refresh_from_db()
        self.assertEqual(self.water.next_due_on, today())
        self.assertFalse(ReminderOccurrence.objects.filter(reminder=self.water).exists())
        self.sync()      # and the override sticks
        self.assertFalse(ReminderOccurrence.objects.filter(reminder=self.water).exists())

    def test_indoor_and_weather_blind_reminders_are_left_alone(self):
        Reminder.objects.filter(pk=self.water.pk).update(weather_aware=False)
        self.sync()
        self.assertFalse(ReminderOccurrence.objects.exists())

    def test_undo_without_a_skip_is_refused(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse("garden:unskip_reminder", args=[self.water.pk])).status_code, 400)

    def test_no_location_means_no_notifications(self):
        GrowingLocation.objects.all().delete()
        with mock.patch.object(weather_services, "_fetch") as fetch:
            services.sync_weather(self.user)
        fetch.assert_not_called()
        self.assertEqual(Notification.objects.count(), 0)
