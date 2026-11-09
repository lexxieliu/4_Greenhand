"""Open-Meteo adapter; all aggregate windows use UTC hourly timestamps."""

import json
import math
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlencode
from urllib.request import urlopen

from django.utils import timezone as dj_timezone

from .models import WeatherSnapshot

TTL = timedelta(hours=3)


def location_key(location):
    return tuple(
        Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        for value in (location.latitude, location.longitude)
    )


def cached_snapshot(location):
    lat, lon = location_key(location)
    return (
        WeatherSnapshot.objects.filter(lat_rounded=lat, lon_rounded=lon)
        .order_by("-fetched_at")
        .first()
    )


def is_fresh(snapshot, now=None):
    return (
        snapshot is not None
        and timedelta(0) <= (now or dj_timezone.now()) - snapshot.fetched_at < TTL
    )


def number(value):
    if value is None or isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError("Incomplete weather response")
    return float(value)


def fetch_forecast(location, now):
    lat, lon = location_key(location)
    query = urlencode(
        {
            "latitude": str(lat),
            "longitude": str(lon),
            "timezone": "UTC",
            "past_days": 2,
            "forecast_days": 8,
            "current": "temperature_2m,weather_code",
            "hourly": "temperature_2m,rain,showers,precipitation_probability",
            "daily": "temperature_2m_min,temperature_2m_max,precipitation_probability_max,weather_code",
        }
    )
    with urlopen(
        "https://api.open-meteo.com/v1/forecast?" + query, timeout=8
    ) as response:
        payload = json.load(response)
    hourly = payload["hourly"]
    times = [
        datetime.fromisoformat(value).replace(tzinfo=UTC) for value in hourly["time"]
    ]
    rain_indices = [
        i for i, t in enumerate(times) if now - timedelta(hours=24) < t <= now
    ]
    prob_indices = [
        i for i, t in enumerate(times) if now < t <= now + timedelta(hours=12)
    ]
    temp_indices = [
        i for i, t in enumerate(times) if now < t <= now + timedelta(hours=48)
    ]
    if len(rain_indices) != 24 or len(prob_indices) != 12 or len(temp_indices) != 48:
        raise ValueError("Incomplete forecast windows")
    rain = sum(
        number(hourly["rain"][i]) + number(hourly["showers"][i]) for i in rain_indices
    )
    probability = max(
        number(hourly["precipitation_probability"][i]) for i in prob_indices
    )
    temps = [number(hourly["temperature_2m"][i]) for i in temp_indices]
    if not 0 <= probability <= 100 or rain < 0:
        raise ValueError("Invalid weather values")
    current_time = datetime.fromisoformat(payload["current"]["time"]).replace(
        tzinfo=UTC
    )
    if abs(now - current_time) > TTL:
        raise ValueError("Stale provider response")
    return dict(
        current_temp_c=number(payload["current"]["temperature_2m"]),
        rain_last_24h_mm=round(rain, 1),
        precip_prob_next_12h=round(probability),
        min_temp_next_48h_c=min(temps),
        max_temp_next_48h_c=max(temps),
        forecast=payload,
    )


def get_snapshot(location, now=None):
    now = now or dj_timezone.now()
    cached = cached_snapshot(location)
    if is_fresh(cached, now):
        return cached
    try:
        values = fetch_forecast(location, now)
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return cached
    lat, lon = location_key(location)
    return WeatherSnapshot.objects.create(
        lat_rounded=lat, lon_rounded=lon, fetched_at=now, **values
    )
