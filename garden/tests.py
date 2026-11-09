"""Garden tests: services without HTTP, photo cleaning, and the JSON endpoints through the test client.
Run with: python manage.py test --settings=greenhand.settings.test"""
import io
import shutil
import tempfile
from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from greenhand.clock import today
from greenhand.users import DEMO_USERNAME
from plants.models import Plant

from . import selectors, services
from .images import clean_photo
from .models import Harvest, Reminder, ReminderOccurrence, TimelineEntry, UserPlant

MEDIA = tempfile.mkdtemp()


def jpeg_with_gps(size=(2400, 1200)):
    """A JPEG carrying EXIF with a GPS block, like a phone photo."""
    image = Image.new("RGB", size, (60, 140, 60))
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"                         # Make
    exif[0x8825] = {1: "N", 2: (41.0, 52.0, 0.0)}       # GPSInfo: latitude
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif)
    return SimpleUploadedFile("leaf.jpg", out.getvalue(), content_type="image/jpeg")


class GardenTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_plants", stdout=StringIO())
        cls.user = User.objects.create(username="grower")
        cls.basil = Plant.objects.get(slug="basil")         # continuous harvest, frost-tender
        cls.radish = Plant.objects.get(slug="radish")       # single harvest

    def grow(self, plant=None, **overrides):
        options = dict(nickname="", planted_on=today(), start_method="seed", setting="outdoor")
        options.update(overrides)
        return services.start_growing(self.user, plant or self.basil, **options)


class StartGrowingTests(GardenTestCase):
    def test_seed_sown_today_sprouts_with_a_care_schedule(self):
        up = self.grow()
        self.assertEqual(up.status, "sprouting")
        self.assertEqual(up.nickname, "Basil")
        self.assertEqual(up.timeline.get().stage, "seed")
        water = up.reminders.get(type="water")
        self.assertEqual((water.interval_days, water.next_due_on), (self.basil.watering_interval_days, today() + timedelta(days=1)))
        self.assertTrue(water.weather_aware)
        feed = up.reminders.get(type="fertilize")
        self.assertEqual(feed.next_due_on, today() + timedelta(days=services.FIRST_FEED_AFTER_DAYS["seed"]))

    def test_seedling_starts_growing_and_indoor_watering_ignores_rain(self):
        up = self.grow(start_method="seedling", setting="indoor")
        self.assertEqual(up.status, "growing")
        self.assertFalse(up.reminders.get(type="water").weather_aware)

    def test_future_date_is_planned_without_timeline(self):
        up = self.grow(planted_on=today() + timedelta(days=10))
        self.assertEqual(up.status, "planned")
        self.assertFalse(up.timeline.exists())
        self.assertEqual(up.reminders.get(type="water").next_due_on, today() + timedelta(days=10))


class TimelineTests(GardenTestCase):
    def test_entry_moves_status_forward_and_fruiting_starts_harvest_checks(self):
        up = self.grow()
        self.assertEqual(services.add_timeline_entry(up, stage="fruiting", recorded_on=today()), "Fruiting")
        self.assertEqual(up.reminders.get(type="harvest_check").interval_days, services.HARVEST_CHECK_INTERVAL_DAYS["continuous"])

    def test_entry_never_moves_status_backwards_or_over_a_user_choice(self):
        up = self.grow(start_method="seedling")
        services.add_timeline_entry(up, stage="flowering", recorded_on=today())
        self.assertIsNone(services.add_timeline_entry(up, stage="seedling", recorded_on=today()))
        self.assertEqual(up.status, "flowering")
        services.change_status(up, "growing")                      # user override
        self.assertIsNone(services.add_timeline_entry(up, stage="fruiting", recorded_on=today()))
        self.assertEqual(UserPlant.objects.get(pk=up.pk).status, "growing")

    def test_planned_plant_starts_when_first_entry_is_logged_even_without_status_update(self):
        up = self.grow(planted_on=today() + timedelta(days=3))
        services.add_timeline_entry(up, stage="seed", recorded_on=today(), update_status=False)
        self.assertEqual(up.status, "sprouting")


class CareAndProblemTests(GardenTestCase):
    def test_watering_completes_the_due_reminder_and_schedules_the_next(self):
        up = self.grow()
        water = up.reminders.get(type="water")
        services.log_care(up, action="water", performed_on=today())
        water.refresh_from_db()
        self.assertEqual(water.next_due_on, today() + timedelta(days=water.interval_days))
        self.assertEqual(water.occurrences.get().status, ReminderOccurrence.Status.DONE)

    def test_pruning_does_not_touch_reminders(self):
        up = self.grow()
        services.log_care(up, action="prune", performed_on=today())
        self.assertFalse(ReminderOccurrence.objects.exists())

    def test_completing_a_task_logs_care_from_the_reminder(self):
        up = self.grow()
        services.complete_reminder(up.reminders.get(type="water"))
        self.assertEqual(up.care_logs.get().source, "reminder")

    def test_problem_schedules_a_check_that_resolving_turns_off(self):
        up = self.grow()
        problem = services.log_problem(up, title="Yellow leaves", severity="medium")
        check = up.reminders.get(type="check_problem")
        self.assertEqual(check.next_due_on, today() + timedelta(days=3))
        services.set_problem_status(problem, "resolved", "Let it dry out")
        check.refresh_from_db()
        self.assertFalse(check.is_active)
        self.assertIsNotNone(problem.resolved_at)


class HarvestTests(GardenTestCase):
    def test_first_harvest_sets_north_star_and_continuous_crop_keeps_producing(self):
        up = self.grow(start_method="seedling")
        services.log_harvest(up, harvested_on=today(), quantity=30, unit="g")
        first = UserPlant.objects.get(pk=up.pk).first_harvest_at
        self.assertIsNotNone(first)
        self.assertEqual(up.status, "producing")
        services.log_harvest(up, harvested_on=today(), quantity=20, unit="g")
        self.assertEqual(UserPlant.objects.get(pk=up.pk).first_harvest_at, first)
        self.assertTrue(up.reminders.filter(is_active=True).exists())

    def test_final_harvest_completes_and_stops_reminders(self):
        up = self.grow(start_method="seedling")
        services.log_harvest(up, harvested_on=today(), final=True)
        self.assertEqual(up.status, "completed")
        self.assertFalse(up.reminders.filter(is_active=True).exists())

    def test_single_harvest_crop_completes_on_first_harvest(self):
        up = self.grow(self.radish)
        services.log_harvest(up, harvested_on=today(), quantity=12, unit="count")
        self.assertEqual(up.status, "completed")

    def test_failed_plant_cannot_be_harvested(self):
        up = self.grow()
        services.change_status(up, "failed", "frost")
        with self.assertRaises(services.GardenError):
            services.log_harvest(up, harvested_on=today())


class StatusTests(GardenTestCase):
    def test_harvest_statuses_need_a_harvest(self):
        up = self.grow()
        with self.assertRaises(services.GardenError):
            services.change_status(up, "producing")

    def test_failure_needs_a_reason_and_stops_reminders(self):
        up = self.grow()
        with self.assertRaises(services.GardenError):
            services.change_status(up, "failed")
        services.change_status(up, "failed", "pest")
        self.assertEqual((up.failure_reason, up.status_source), ("pest", "user"))
        self.assertFalse(up.reminders.filter(is_active=True).exists())


class PhotoTests(TestCase):
    def test_strips_exif_and_shrinks(self):
        cleaned = clean_photo(jpeg_with_gps())
        with Image.open(cleaned) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertLessEqual(max(image.size), 1600)
            self.assertEqual(len(image.getexif()), 0)

    def test_rejects_non_images_unsupported_formats_and_large_files(self):
        with self.assertRaisesMessage(ValidationError, "not a valid image"):
            clean_photo(SimpleUploadedFile("x.jpg", b"not really a jpeg", content_type="image/jpeg"))
        gif = io.BytesIO()
        Image.new("RGB", (10, 10)).save(gif, format="GIF")
        with self.assertRaisesMessage(ValidationError, "JPEG, PNG or WebP"):
            clean_photo(SimpleUploadedFile("x.gif", gif.getvalue(), content_type="image/gif"))
        with override_settings(MAX_UPLOAD_MB=0):
            with self.assertRaisesMessage(ValidationError, "0 MB or smaller"):
                clean_photo(jpeg_with_gps((10, 10)))


@override_settings(MEDIA_ROOT=MEDIA)
class EndpointTests(GardenTestCase):
    """The demo account is used when nobody is signed in (greenhand.users.current_user)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.demo = User.objects.create(username=DEMO_USERNAME)
        cls.mine = services.start_growing(cls.demo, cls.basil, nickname="Balcony Basil", planted_on=today(),
                                          start_method="seedling", setting="outdoor")
        cls.theirs = services.start_growing(cls.user, cls.basil, nickname="Not yours", planted_on=today(),
                                            start_method="seedling", setting="outdoor")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def post(self, name, data, *args):
        return self.client.post(reverse(f"garden:{name}", args=args), data)

    def test_pages_render_from_the_database(self):
        self.client.force_login(self.demo)
        for name in ("garden:my_garden", "weather:index", "community:feed", "plants:list"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertContains(self.client.get(reverse("garden:my_garden")), "Balcony Basil")
        self.assertContains(self.client.get(reverse("weather:index")), "Balcony Basil")
        dashboard = self.client.get(reverse("garden:dashboard"))
        self.assertContains(dashboard, "Balcony Basil")
        self.assertNotContains(dashboard, "Not yours")

    def test_add_plant_returns_the_saved_plant(self):
        response = self.post("add_plant", {"plant": "radish", "planted_on": today().isoformat(), "start_method": "seed",
                                           "setting": "outdoor", "nickname": "Pot radishes"})
        self.assertEqual(response.status_code, 201)
        plant = response.json()["plant"]
        self.assertEqual((plant["nickname"], plant["status"]), ("Pot radishes", "sprouting"))
        self.assertEqual({r["type"] for r in plant["reminders"]}, {"water", "fertilize"})

    def test_timeline_photo_upload_is_saved_without_exif(self):
        response = self.post("add_timeline_entry", {"stage": "flowering", "date": today().isoformat(), "note": "Buds!",
                                                    "photo": jpeg_with_gps(), "update_status": "on"}, self.mine.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["plant"]["status"], "flowering")
        entry = TimelineEntry.objects.get(user_plant=self.mine, stage="flowering")
        with Image.open(entry.photo.path) as image:
            self.assertEqual(len(image.getexif()), 0)

    def test_invalid_input_returns_a_message(self):
        future = (today() + timedelta(days=2)).isoformat()
        response = self.post("log_care", {"action": "water", "date": future}, self.mine.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "That date is in the future.")
        bad_photo = SimpleUploadedFile("x.png", b"\x89PNG broken", content_type="image/png")
        response = self.post("log_problem", {"title": "Spots", "category": "disease", "severity": "low", "photo": bad_photo},
                             self.mine.pk)
        self.assertEqual(response.json()["error"], "That file is not a valid image.")

    def test_rule_violations_return_a_message(self):
        response = self.post("change_status", {"status": "producing"}, self.mine.pk)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Log a harvest first", response.json()["error"])

    def test_harvest_and_reminder_endpoints(self):
        response = self.post("log_harvest", {"date": today().isoformat(), "quantity": "25", "unit": "g"}, self.mine.pk)
        self.assertEqual(response.json()["plant"]["status"], "producing")
        reminder = self.mine.reminders.get(type="water")
        self.post("set_reminder_flag", {"flag": "active", "value": ""}, reminder.pk)
        self.assertFalse(Reminder.objects.get(pk=reminder.pk).is_active)
        self.assertEqual(Harvest.objects.filter(user_plant=self.mine).count(), 1)

    def test_other_users_records_are_404(self):
        problem = services.log_problem(self.theirs, title="Theirs")
        reminder = self.theirs.reminders.first()
        checks = [
            ("add_timeline_entry", {"stage": "seed", "date": today().isoformat()}, self.theirs.pk),
            ("log_care", {"action": "water", "date": today().isoformat()}, self.theirs.pk),
            ("log_harvest", {"date": today().isoformat(), "unit": "g"}, self.theirs.pk),
            ("change_status", {"status": "growing"}, self.theirs.pk),
            ("set_problem_status", {"status": "resolved"}, problem.pk),
            ("set_reminder_flag", {"flag": "active", "value": ""}, reminder.pk),
            ("complete_reminder", {}, reminder.pk),
        ]
        for name, data, pk in checks:
            self.assertEqual(self.post(name, data, pk).status_code, 404, name)
        self.assertFalse(self.theirs.harvests.exists())

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(reverse("garden:log_care", args=[self.mine.pk])).status_code, 405)


class DemoGardenTests(TestCase):
    def test_seed_demo_garden_builds_the_preview_garden(self):
        call_command("seed_demo_garden", stdout=StringIO())
        call_command("seed_demo_garden", stdout=StringIO())        # running twice replaces, never duplicates
        plants = selectors.garden(User.objects.get(username=DEMO_USERNAME))
        self.assertEqual(len(plants), 6)
        mint = next(p for p in plants if p["nickname"] == "Mint")
        self.assertEqual((mint["status"], len(mint["harvests"])), ("producing", 3))
        self.assertIsNotNone(mint["first_harvest_at"])
