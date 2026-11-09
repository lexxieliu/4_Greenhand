from datetime import UTC, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from calendar_app.models import Reminder
from garden.models import Garden
from plants.models import Plant
from weather.models import Location, PlantWeatherSettings, WeatherSnapshot

NOW = datetime(2026, 11, 9, 14, tzinfo=UTC)


class Area3Case(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="grower", email="grower@example.com", password="test-pass-123"
        )
        self.other = get_user_model().objects.create_user(
            username="other", password="test-pass-123"
        )
        self.plant = Plant.objects.create(plant_name="Tomato", category="vegetable")
        self.garden = Garden.objects.create(user=self.user, plant=self.plant)
        self.location = Location.objects.create(
            user=self.user,
            label="Chicago",
            latitude="41.881",
            longitude="-87.629",
            timezone="America/Chicago",
        )
        self.config = PlantWeatherSettings.objects.create(
            user_plant=self.garden, location=self.location
        )
        self.reminder = Reminder.objects.create(
            user=self.user,
            user_plant=self.garden,
            type="water",
            title="Water tomato",
            next_due_at=NOW,
            timezone="America/Chicago",
            recurrence_rule="FREQ=DAILY;INTERVAL=1",
        )

    def snapshot(self, **kwargs):
        values = dict(
            lat_rounded="41.9",
            lon_rounded="-87.6",
            fetched_at=NOW,
            current_temp_c=12,
            rain_last_24h_mm=0,
            precip_prob_next_12h=0,
            min_temp_next_48h_c=8,
            max_temp_next_48h_c=20,
            forecast={},
        )
        values.update(kwargs)
        return WeatherSnapshot.objects.create(**values)
