"""Live forecast from Open-Meteo (free, no key), cached as WeatherSnapshot for 3 hours (PRD 6.4 C)."""
import json
import logging
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlencode
from urllib.request import urlopen

from django.utils import timezone

from .models import WeatherSnapshot

logger = logging.getLogger(__name__)

API_URL = "https://api.open-meteo.com/v1/forecast"
MAX_AGE = timedelta(hours=3)
STALE_LIMIT = timedelta(hours=24)     # older than this is worse than saying nothing
TIMEOUT_SECONDS = 5


def _round(value):
    return Decimal(value).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _fetch(lat, lon):
    query = urlencode({
        "latitude": lat, "longitude": lon, "past_days": 1, "forecast_days": 7, "timezone": "UTC",
        "hourly": "temperature_2m,precipitation,precipitation_probability",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
    })
    with urlopen(f"{API_URL}?{query}", timeout=TIMEOUT_SECONDS) as response:
        return json.load(response)


def _snapshot_fields(payload, now):
    """Derive the rule-engine numbers from the hourly series (it starts one day in the past)."""
    hourly, daily = payload["hourly"], payload["daily"]
    index = hourly["time"].index(now.strftime("%Y-%m-%dT%H:00"))
    temps = hourly["temperature_2m"][index:index + 48]
    return {
        "current_temp_c": _round(hourly["temperature_2m"][index]),
        "rain_last_24h_mm": _round(sum(hourly["precipitation"][max(index - 24, 0):index])),
        "precip_prob_next_12h": max(hourly["precipitation_probability"][index:index + 12]),
        "min_temp_next_48h_c": _round(min(temps)),
        "max_temp_next_48h_c": _round(max(temps)),
        "forecast": [
            {"date": day, "high": high, "low": low, "precip_prob": prob}
            for day, high, low, prob in zip(daily["time"], daily["temperature_2m_max"], daily["temperature_2m_min"],
                                            daily["precipitation_probability_max"])
            if day >= now.date().isoformat()
        ],
    }


def get_snapshot(latitude, longitude):
    """A fresh snapshot for this location, or a recent stale one if the API fails, or None (PRD 2.2)."""
    lat, lon = _round(latitude), _round(longitude)
    now = timezone.now()
    latest = WeatherSnapshot.objects.filter(lat_rounded=lat, lon_rounded=lon).first()
    if latest and now - latest.fetched_at < MAX_AGE:
        return latest
    try:
        fields = _snapshot_fields(_fetch(lat, lon), now)
    except (OSError, ValueError, KeyError, TypeError):
        logger.warning("Weather fetch failed for %s,%s", lat, lon, exc_info=True)
        return latest if latest and now - latest.fetched_at < STALE_LIMIT else None
    return WeatherSnapshot.objects.create(lat_rounded=lat, lon_rounded=lon, **fields)
