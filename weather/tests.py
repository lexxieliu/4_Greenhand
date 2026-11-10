from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import services
from userprofile.models import GrowingLocation

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

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

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


    def test_failing_api_is_not_retried_straight_away(self):
        with mock.patch.object(services, "_fetch", side_effect=OSError) as fetch:
            services.get_snapshot(self.lat, self.lon)
            services.get_snapshot(self.lat, self.lon)
        self.assertEqual(fetch.call_count, 1)


def live_payload(now, offset=-18000, low=-1):
    """Open-Meteo-shaped data with every field the weather page shows (Chicago-like, UTC-5)."""
    start = (now + timedelta(seconds=offset)).replace(minute=0, second=0, microsecond=0) - timedelta(hours=24)
    hours = [start + timedelta(hours=i) for i in range(24 * 8)]
    today = (now + timedelta(seconds=offset)).date()
    days = [today + timedelta(days=i) for i in range(7)]
    return {
        "utc_offset_seconds": offset,
        "hourly": {
            "time": [h.strftime("%Y-%m-%dT%H:00") for h in hours],
            "temperature_2m": [low if 24 < i < 30 else 9 for i in range(len(hours))],
            "apparent_temperature": [7] * len(hours), "relative_humidity_2m": [80] * len(hours),
            "wind_speed_10m": [12.4] * len(hours), "uv_index": [1] * len(hours), "weather_code": [61] * len(hours),
            "precipitation": [0.5 if i < 24 else 0 for i in range(len(hours))],
            "precipitation_probability": [20] * len(hours),
        },
        "daily": {
            "time": [d.isoformat() for d in days], "temperature_2m_max": [12] * 7,
            "temperature_2m_min": [low if i == 1 else 6 for i in range(7)], "precipitation_probability_max": [30] * 7,
            "precipitation_sum": [1.2] * 7, "weather_code": [61, 3, 0, 0, 0, 0, 0],
            "sunrise": [f"{d.isoformat()}T07:03" for d in days], "sunset": [f"{d.isoformat()}T18:16" for d in days],
        },
    }


class LiveWeatherTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user("grower", "grower@example.com", "pass12345")
        GrowingLocation.objects.create(user=self.user, city="Chicago", region="IL", latitude="41.88", longitude="-87.63")

    def weather(self, **kwargs):
        with mock.patch.object(services, "_fetch", return_value=live_payload(timezone.now(), **kwargs)):
            return services.weather_for(self.user)

    def test_builds_page_data_from_the_forecast(self):
        weather = self.weather()
        self.assertEqual(weather["location"], "Chicago, IL")
        self.assertEqual(weather["current"]["temp_c"], 9)
        self.assertEqual((weather["current"]["condition"], weather["current"]["icon"]), ("Rain", "i-rain"))
        self.assertEqual((weather["current"]["sunrise"], weather["current"]["sunset"]), ("7:03 AM", "6:16 PM"))
        self.assertEqual(weather["current"]["rain_last_24h_mm"], 12.0)
        self.assertEqual(len(weather["daily"]), 7)
        self.assertEqual(weather["daily"][0]["day_short"], "Today")
        self.assertTrue(weather["daily"][1]["frost"])
        self.assertEqual(len(weather["hourly"]), 25)

    def test_no_location_or_anonymous_gives_no_weather(self):
        GrowingLocation.objects.all().delete()
        with mock.patch.object(services, "_fetch") as fetch:
            self.assertIsNone(services.weather_for(self.user))
        fetch.assert_not_called()

    def test_frost_and_rain_alerts_only_for_outdoor_plants(self):
        weather = self.weather()
        alerts = {a["alert_type"]: a for a in services.alerts_for(weather, ["Basil", "Tomato"], ["Tomato"])}
        self.assertEqual(alerts["frost"]["plants"], ["Tomato"])
        self.assertIn("low of -1 °C", alerts["frost"]["title"])
        self.assertIn("12 mm", alerts["rain_skip"]["message"])
        self.assertEqual(services.alerts_for(weather, [], []), [])
        self.assertEqual(services.alerts_for(None, ["Basil"], ["Basil"]), [])

    def test_calm_weather_has_no_alerts(self):
        with mock.patch.object(services, "_fetch", return_value=live_payload(timezone.now(), low=8)):
            weather = services.weather_for(self.user)
        weather["current"]["rain_last_24h_mm"] = 0
        self.assertEqual(services.alerts_for(weather, ["Basil"], ["Basil"]), [])


class PageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_weather_page_renders(self):
        self.client.force_login(User.objects.create_user("grower", "grower@example.com", "pass12345"))
        self.assertEqual(self.client.get(reverse("weather:index")).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("weather:index")).status_code, 302)   # personal page

    def test_page_shows_live_forecast_or_a_friendly_message(self):
        user = User.objects.create_user("grower", "grower@example.com", "pass12345")
        GrowingLocation.objects.create(user=user, city="Chicago", region="IL", latitude="41.88", longitude="-87.63")
        self.client.force_login(user)
        with mock.patch.object(services, "_fetch", return_value=live_payload(timezone.now())):
            response = self.client.get(reverse("weather:index"))
            dashboard = self.client.get(reverse("garden:dashboard"))
        self.assertContains(response, "Chicago, IL")
        self.assertContains(response, "7:03 AM")
        self.assertContains(dashboard, "Weather · Chicago, IL")
        cache.clear()
        WeatherSnapshot.objects.all().delete()
        with mock.patch.object(services, "_fetch", side_effect=OSError):
            response = self.client.get(reverse("weather:index"))
        self.assertContains(response, "We could not load the forecast")
