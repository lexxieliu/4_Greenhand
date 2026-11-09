"""Plant catalog tests. Run with: python manage.py test --settings=greenhand.settings.test"""
from datetime import date, timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from garden.models import UserPlant
from greenhand.clock import today
from greenhand.users import DEMO_USERNAME

from . import selectors, services
from .models import Plant, PlantProblemSummary


class CatalogTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_plants", stdout=StringIO())


class SeedTests(CatalogTestCase):
    def test_seeds_fifty_plants_once(self):
        call_command("seed_plants", stdout=StringIO())             # running again updates, never duplicates
        self.assertEqual(Plant.objects.count(), 50)
        basil = Plant.objects.get(slug="basil")
        self.assertEqual((basil.harvest_mode, basil.planting_months["5b"]), ("continuous", [5, 6, 7]))
        self.assertEqual(basil.problem_summaries.count(), 3)
        self.assertEqual(PlantProblemSummary.objects.filter(plant=basil).count(), 3)


@mock.patch("plants.services.today", return_value=date(2026, 10, 13))
class SuitabilityTests(CatalogTestCase):
    """Suitability depends on the month: these cases are for Oct 13 in zone 5b."""

    def suit(self, slug):
        return services.suitability(selectors.plant_dict(Plant.objects.get(slug=slug)))["level"]

    def test_badges(self, _):
        self.assertEqual(self.suit("lettuce"), "great")          # sown in October in zone 5b
        self.assertEqual(self.suit("microgreens"), "great")      # indoors all year
        self.assertEqual(self.suit("basil"), "care")             # out of season, but can grow indoors
        self.assertEqual(self.suit("cherry-tomato"), "no")       # out of season and not indoor-friendly


class FilterTests(CatalogTestCase):
    def slugs(self, **params):
        return {p["slug"] for p in services.filter_catalog(params, {})}

    def test_filters(self):
        self.assertTrue(self.slugs(category="herb") >= {"basil", "mint", "thyme"})
        self.assertNotIn("cherry-tomato", self.slugs(category="herb"))
        self.assertTrue(all(p["difficulty"] == "hard" for p in services.filter_catalog({"difficulty": "hard"}, {})))
        self.assertEqual(self.slugs(q="ocimum"), {"basil"})
        self.assertNotIn("zucchini", self.slugs(indoor="1"))
        self.assertIn("garlic", self.slugs(season="fall"))
        self.assertTrue(all(p["suitability"]["level"] == "great" for p in services.filter_catalog({"suitable": "1"}, {})))

    def test_unpublished_plants_are_hidden(self):
        Plant.objects.filter(slug="basil").update(is_published=False)
        self.assertNotIn("basil", self.slugs())
        self.assertEqual(self.client.get(reverse("plants:detail", args=["basil"])).status_code, 404)


class PageTests(CatalogTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username=DEMO_USERNAME, password="test-pass-123")
        self.client.force_login(self.user)
    def test_list_and_detail_render(self):
        self.assertContains(self.client.get(reverse("plants:list"), {"category": "fruit"}), "Blueberries")
        detail = self.client.get(reverse("plants:detail", args=["raspberries"]))   # no germination data
        self.assertContains(detail, "Raspberries")
        self.assertContains(detail, "Japanese beetles")

    def test_start_growing_saves_the_plant_with_a_schedule(self):
        response = self.client.post(reverse("plants:start", args=["kale"]), {
            "planted_on": today().isoformat(), "start_method": "seed", "setting": "outdoor", "nickname": "Winter kale",
        })
        user_plant = UserPlant.objects.get(user__username=DEMO_USERNAME, nickname="Winter kale")
        self.assertRedirects(response, f"{reverse('garden:my_garden')}#plant={user_plant.pk}", fetch_redirect_response=False)
        self.assertEqual(user_plant.reminders.count(), 2)

    def test_start_growing_rejects_bad_dates(self):
        too_far = (today() + timedelta(days=400)).isoformat()
        response = self.client.post(reverse("plants:start", args=["kale"]), {"planted_on": too_far, "start_method": "seed",
                                                                              "setting": "outdoor"}, follow=True)
        self.assertContains(response, "next 12 months")
        self.assertFalse(UserPlant.objects.exists())
        self.assertEqual(self.client.post(reverse("plants:start", args=["no-such-plant"]), {}).status_code, 404)

    def test_start_growing_needs_sign_in(self):
        self.client.logout()
        response = self.client.post(reverse("plants:start", args=["kale"]), {"planted_on": today().isoformat(),
                                                                            "start_method": "seed", "setting": "outdoor"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(UserPlant.objects.exists())

    def test_in_garden_shows_on_the_plant_page(self):
        UserPlant.objects.create(user=self.user, plant=Plant.objects.get(slug="mint"), nickname="Tea mint",
                                 planted_on=today(), watering_interval_days=3, status="growing")
        self.assertContains(self.client.get(reverse("plants:detail", args=["mint"])), "Tea mint")
