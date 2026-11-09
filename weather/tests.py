from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import services
from .models import WeatherSnapshot


def payload(now):
    start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=24)
    hours = [start + timedelta(hours=i) for i in range(96)]
    day = now.date().isoformat()
    return {
        "hourly": {
            "time": [h.strftime("%Y-%m-%dT%H:00") for h in hours],
            "temperature_2m": [5 if i != 40 else -1 for i in range(96)],
            "precipitation": [0.5 if i < 24 else 0 for i in range(96)],
            "precipitation_probability": [10 if i != 30 else 80 for i in range(96)],
        },
        "daily": {"time": ["2000-01-01", day], "temperature_2m_max": [9, 12], "temperature_2m_min": [1, 3],
                  "precipitation_probability_max": [5, 50]},
    }


class SnapshotTests(TestCase):
    lat, lon = Decimal("43.07"), Decimal("-89.40")

    def _existing(self, age_hours):
        snapshot = WeatherSnapshot.objects.create(
            lat_rounded=Decimal("43.1"), lon_rounded=Decimal("-89.4"), current_temp_c=1, rain_last_24h_mm=0,
            precip_prob_next_12h=0, min_temp_next_48h_c=0, max_temp_next_48h_c=0)
        WeatherSnapshot.objects.filter(pk=snapshot.pk).update(fetched_at=timezone.now() - timedelta(hours=age_hours))
        return snapshot

    def test_derives_rule_numbers_and_rounds_location(self):
        with mock.patch.object(services, "_fetch", return_value=payload(timezone.now())):
            snapshot = services.get_snapshot(self.lat, self.lon)
        self.assertEqual((snapshot.lat_rounded, snapshot.lon_rounded), (Decimal("43.1"), Decimal("-89.4")))
        self.assertEqual(snapshot.rain_last_24h_mm, Decimal("12.0"))
        self.assertEqual(snapshot.precip_prob_next_12h, 80)
        self.assertEqual(snapshot.min_temp_next_48h_c, Decimal("-1.0"))
        self.assertEqual([d["high"] for d in snapshot.forecast], [12])

    def test_fresh_snapshot_is_reused(self):
        existing = self._existing(1)
        with mock.patch.object(services, "_fetch") as fetch:
            self.assertEqual(services.get_snapshot(self.lat, self.lon), existing)
        fetch.assert_not_called()

    def test_api_failure_falls_back_to_recent_snapshot_then_none(self):
        existing = self._existing(6)
        with mock.patch.object(services, "_fetch", side_effect=OSError):
            self.assertEqual(services.get_snapshot(self.lat, self.lon), existing)
        WeatherSnapshot.objects.update(fetched_at=timezone.now() - timedelta(hours=30))
        with mock.patch.object(services, "_fetch", side_effect=OSError):
            self.assertIsNone(services.get_snapshot(self.lat, self.lon))


class PageTests(TestCase):
    def test_weather_page_renders(self):
        self.client.force_login(User.objects.create_user("grower", "grower@example.com", "pass12345"))
        self.assertEqual(self.client.get(reverse("weather:index")).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("weather:index")).status_code, 302)   # personal page
