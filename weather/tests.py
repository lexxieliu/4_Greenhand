import json
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.core.exceptions import ValidationError

from calendar_app.models import ReminderOccurrence, ReminderOverride
from calendar_app.services import act_on_occurrence, prepare_occurrences
from notifications.models import Notification

from .client import fetch_forecast, get_snapshot, location_key
from .models import WeatherAlert
from .services import apply_rain_to_occurrence, refresh_weather
from .test_helpers import NOW, Area3Case


class WeatherTests(Area3Case):
    def test_shared_rounded_cache_avoids_network(self):
        cached = self.snapshot()
        self.location.latitude = "41.89"
        with patch("weather.client.urlopen") as request:
            self.assertEqual(get_snapshot(self.location, NOW).pk, cached.pk)
            request.assert_not_called()
        self.assertEqual(str(location_key(self.location)[0]), "41.9")

    def test_failure_returns_stale_cache_or_none(self):
        cached = self.snapshot(fetched_at=NOW - timedelta(hours=4))
        with patch("weather.client.fetch_forecast", side_effect=OSError("offline")):
            self.assertEqual(get_snapshot(self.location, NOW), cached)
            cached.delete()
            self.assertIsNone(get_snapshot(self.location, NOW))

    def test_partial_provider_response_falls_back(self):
        cached = self.snapshot(fetched_at=NOW - timedelta(hours=4))
        with patch("weather.client.urlopen", return_value=BytesIO(b'{"hourly":{}}')):
            self.assertEqual(get_snapshot(self.location, NOW), cached)

    def test_exact_hourly_windows_include_showers(self):
        times = [NOW + timedelta(hours=i) for i in range(-48, 170)]
        payload = {
            "current": {"time": NOW.isoformat(), "temperature_2m": 12},
            "hourly": {
                "time": [t.isoformat() for t in times],
                "rain": [1] * len(times),
                "showers": [0.5] * len(times),
                "temperature_2m": [
                    1 if 0 < (t - NOW).total_seconds() <= 48 * 3600 else -20
                    for t in times
                ],
                "precipitation_probability": [
                    70 if 0 < (t - NOW).total_seconds() <= 12 * 3600 else 99
                    for t in times
                ],
            },
        }
        with patch(
            "weather.client.urlopen", return_value=BytesIO(json.dumps(payload).encode())
        ):
            result = fetch_forecast(self.location, NOW)
        self.assertEqual(result["rain_last_24h_mm"], 36)
        self.assertEqual(result["precip_prob_next_12h"], 70)
        self.assertEqual(result["min_temp_next_48h_c"], 1)

    def test_rain_boundary_dedup_and_override(self):
        self.snapshot(rain_last_24h_mm=5)
        refresh_weather(NOW)
        refresh_weather(NOW)
        occurrence = ReminderOccurrence.objects.get(reminder=self.reminder, due_at=NOW)
        self.assertEqual(occurrence.status, "skipped_rain")
        self.assertEqual(WeatherAlert.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 1)
        act_on_occurrence(self.user, occurrence.pk, "override", "Soil is dry")
        refresh_weather(NOW)
        occurrence.refresh_from_db()
        self.assertEqual(occurrence.status, "pending")
        self.assertTrue(WeatherAlert.objects.get().user_overrode)
        self.assertEqual(ReminderOverride.objects.get().reason, "Soil is dry")

    def test_probability_boundary_and_indoor_exclusion(self):
        self.snapshot(
            precip_prob_next_12h=70, min_temp_next_48h_c=2, max_temp_next_48h_c=32
        )
        self.garden.setting = "indoor"
        self.garden.save()
        refresh_weather(NOW)
        self.assertFalse(WeatherAlert.objects.exists())
        self.garden.setting = "outdoor"
        self.garden.save()
        refresh_weather(NOW)
        self.assertEqual(
            set(WeatherAlert.objects.values_list("alert_type", flat=True)),
            {"rain_skip", "frost", "heat"},
        )

    def test_frost_tolerance_and_per_plant_threshold(self):
        self.snapshot(min_temp_next_48h_c=1)
        self.plant.frost_tolerant = True
        self.plant.save()
        refresh_weather(NOW)
        self.assertFalse(WeatherAlert.objects.exists())
        self.plant.frost_tolerant = False
        self.plant.frost_threshold_c = 0
        self.plant.save()
        refresh_weather(NOW)
        self.assertFalse(WeatherAlert.objects.exists())

    def test_stale_data_never_skips(self):
        self.snapshot(fetched_at=NOW - timedelta(hours=4), rain_last_24h_mm=20)
        with patch("weather.client.fetch_forecast", side_effect=OSError):
            refresh_weather(NOW)
        self.assertFalse(WeatherAlert.objects.exists())
        self.assertEqual(ReminderOccurrence.objects.get(due_at=NOW).status, "pending")

    def test_only_location_today_is_skipped(self):
        self.snapshot(rain_last_24h_mm=20)
        prepare_occurrences(NOW)
        future = ReminderOccurrence.objects.get(due_at=NOW + timedelta(days=1))
        apply_rain_to_occurrence(future, NOW)
        future.refresh_from_db()
        self.assertEqual(future.status, "pending")

    def test_location_ownership_validation(self):
        self.location.user = self.other
        self.location.save()
        with self.assertRaises(ValidationError):
            self.config.full_clean()

    def test_weather_and_setup_pages(self):
        self.client.force_login(self.user)
        self.snapshot()
        for path in ["/weather/", "/weather/setup/"]:
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertContains(self.client.get("/weather/"), "Chicago")

    def test_setup_persists_location_and_config(self):
        self.client.force_login(self.user)
        response = self.client.post(
            "/weather/setup/",
            {
                "kind": "location",
                "label": "Second garden",
                "latitude": "40.00",
                "longitude": "-88.00",
                "timezone": "America/Chicago",
            },
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            "/weather/setup/",
            {
                "kind": "plant",
                "user_plant": self.garden.pk,
                "location": self.user.location_set.get(label="Second garden").pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.config.refresh_from_db()
        self.assertEqual(self.config.location.label, "Second garden")
        response = self.client.post(
            "/weather/setup/",
            {
                "kind": "location",
                "label": "Invalid",
                "latitude": "100",
                "longitude": "0",
                "timezone": "bad",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "valid IANA timezone")

    def test_acknowledgement_is_owned_and_persistent(self):
        self.snapshot(min_temp_next_48h_c=2)
        refresh_weather(NOW)
        alert = WeatherAlert.objects.get()
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.post(f"/weather/alerts/{alert.pk}/ack/").status_code, 404
        )
        self.client.force_login(self.user)
        self.assertEqual(
            self.client.post(f"/weather/alerts/{alert.pk}/ack/").status_code, 302
        )
        alert.refresh_from_db()
        self.assertIsNotNone(alert.acknowledged_at)
