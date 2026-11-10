"""Live forecast from Open-Meteo (free, no key), cached as WeatherSnapshot for 3 hours (PRD 6.4 C)."""
import json
import logging
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlencode
from urllib.request import urlopen

from django.core.cache import cache
from django.utils import timezone
from django.utils.timesince import timesince

from greenhand import mock_data
from userprofile.models import GrowingLocation

from .models import WeatherSnapshot

logger = logging.getLogger(__name__)

API_URL = "https://api.open-meteo.com/v1/forecast"
MAX_AGE = timedelta(hours=3)
STALE_LIMIT = timedelta(hours=24)     # older than this is worse than saying nothing
RETRY_AFTER = 300                     # seconds to leave a failing API alone, so pages do not wait on it each time
TIMEOUT_SECONDS = 5
HOURLY_POINTS = 25                    # every 3 hours for 72 hours, for the weather page charts
THRESHOLDS = {"frost_c": mock_data.FROST_THRESHOLD_C, "rain_mm": mock_data.RAIN_SKIP_MM,
              "rain_prob": mock_data.RAIN_SKIP_PROB, "heat_c": 32}


def _round(value):
    return Decimal(value).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _fetch(lat, lon):
    query = urlencode({
        "latitude": lat, "longitude": lon, "past_days": 1, "forecast_days": 7, "timezone": "auto",
        "hourly": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,uv_index,weather_code,"
                  "precipitation,precipitation_probability",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,weather_code,"
                 "sunrise,sunset",
    })
    with urlopen(f"{API_URL}?{query}", timeout=TIMEOUT_SECONDS) as response:
        return json.load(response)


def _series(block, name, size):
    """One Open-Meteo series, or a list of None when the API left it out."""
    return block.get(name) or [None] * size


def _snapshot_fields(payload, now):
    """Derive the rule-engine numbers and the weather page data from the hourly series (it starts one day in the past)."""
    hourly, daily = payload["hourly"], payload["daily"]
    offset = payload.get("utc_offset_seconds", 0)            # times are in the location's own time zone
    index = hourly["time"].index((now + timedelta(seconds=offset)).strftime("%Y-%m-%dT%H:00"))
    temps = hourly["temperature_2m"][index:index + 48]
    size = len(hourly["time"])
    rain = [r or 0 for r in hourly["precipitation"]]
    extra = {name: _series(hourly, name, size) for name in
             ("apparent_temperature", "relative_humidity_2m", "wind_speed_10m", "uv_index", "weather_code")}
    days = len(daily["time"])
    codes, rain_sum = _series(daily, "weather_code", days), _series(daily, "precipitation_sum", days)
    sunrise, sunset = _series(daily, "sunrise", days), _series(daily, "sunset", days)
    today = (now + timedelta(seconds=offset)).date().isoformat()
    today_index = daily["time"].index(today) if today in daily["time"] else 0
    return {
        "current_temp_c": _round(hourly["temperature_2m"][index]),
        "rain_last_24h_mm": _round(sum(rain[max(index - 24, 0):index])),
        "precip_prob_next_12h": max(hourly["precipitation_probability"][index:index + 12]),
        "min_temp_next_48h_c": _round(min(temps)),
        "max_temp_next_48h_c": _round(max(temps)),
        "forecast": [
            {"date": day, "high": high, "low": low, "precip_prob": prob, "precip_mm": mm, "code": code}
            for day, high, low, prob, mm, code in zip(daily["time"], daily["temperature_2m_max"], daily["temperature_2m_min"],
                                                       daily["precipitation_probability_max"], rain_sum, codes)
            if day >= today
        ],
        "details": {
            "utc_offset": offset,
            "current": {
                "feels_like": extra["apparent_temperature"][index], "humidity": extra["relative_humidity_2m"][index],
                "wind_kmh": extra["wind_speed_10m"][index], "uv": extra["uv_index"][index],
                "code": extra["weather_code"][index], "sunrise": sunrise[today_index], "sunset": sunset[today_index],
            },
            "hourly": [
                {"iso": hourly["time"][i], "temp": hourly["temperature_2m"][i], "precip_mm": round(sum(rain[i:i + 3]), 1)}
                for i in range(index, min(index + 3 * HOURLY_POINTS, size), 3)
            ],
        },
    }


def get_snapshot(latitude, longitude, need_details=False):
    """A fresh snapshot for this location, or a recent stale one if the API fails, or None (PRD 2.2).
    need_details: skip snapshots saved before the weather page data was stored."""
    lat, lon = _round(latitude), _round(longitude)
    now = timezone.now()
    latest = WeatherSnapshot.objects.filter(lat_rounded=lat, lon_rounded=lon).first()
    if latest and (latest.details or not need_details) and now - latest.fetched_at < MAX_AGE:
        return latest
    failed_key = f"weather-failed:{lat}:{lon}"
    fields = None
    if not cache.get(failed_key):
        try:
            fields = _snapshot_fields(_fetch(lat, lon), now)
        except (OSError, ValueError, KeyError, TypeError):
            logger.warning("Weather fetch failed for %s,%s", lat, lon, exc_info=True)
            cache.set(failed_key, True, RETRY_AFTER)
    if fields is None:
        return latest if latest and now - latest.fetched_at < STALE_LIMIT else None
    return WeatherSnapshot.objects.create(lat_rounded=lat, lon_rounded=lon, **fields)


# ---------------------------------------------------------------------------
# What the templates show
# ---------------------------------------------------------------------------
def _condition(code):
    """WMO weather code -> (text, icon id from templates/partials/icons.html)."""
    if code is None:
        return "Unknown", "i-cloud"
    if code == 0:
        return "Clear", "i-sun"
    if code in (1, 2):
        return "Partly cloudy", "i-sun"
    if code == 3:
        return "Overcast", "i-cloud"
    if code in (45, 48):
        return "Fog", "i-cloud"
    if code in (71, 73, 75, 77, 85, 86):
        return "Snow", "i-snow"
    if code in (51, 53, 55, 56, 57):
        return "Drizzle", "i-rain"
    if code in (95, 96, 99):
        return "Thunderstorm", "i-rain"
    return "Rain", "i-rain"


def _whole(value):
    return None if value is None else int(round(value))


def _clock(iso):
    return datetime.fromisoformat(iso).strftime("%I:%M %p").lstrip("0") if iso else "—"


def _hour_label(moment):
    label = moment.strftime("%I %p").lstrip("0")
    return {"12 PM": "Noon", "12 AM": "Midnight"}.get(label, label)


def build_view(snapshot, label):
    """The snapshot in the shape the weather page, dashboard and header use."""
    details = snapshot.details
    offset = details["utc_offset"]
    local_today = (timezone.now() + timedelta(seconds=offset)).date()
    cur = details["current"]
    text, icon = _condition(cur["code"])
    daily = []
    for entry in snapshot.forecast:
        day = date.fromisoformat(entry["date"])
        day_text, day_icon = _condition(entry.get("code"))
        low = _whole(entry["low"])
        daily.append({
            "date": entry["date"], "day_short": "Today" if day == local_today else day.strftime("%a"),
            "day_long": f"{day:%A, %b} {day.day}", "icon": day_icon, "condition": day_text, "high": _whole(entry["high"]),
            "low": low, "precip_mm": entry.get("precip_mm") or 0, "precip_prob": entry["precip_prob"] or 0,
            "frost": low <= THRESHOLDS["frost_c"],
        })
    hourly = []
    for point in details["hourly"]:
        moment = datetime.fromisoformat(point["iso"])
        hourly.append({"iso": point["iso"], "label": _hour_label(moment),
                       "day": "Today" if moment.date() == local_today else moment.strftime("%a"),
                       "temp": round(point["temp"], 1), "precip_mm": point["precip_mm"]})
    today = daily[0] if daily else {"high": None, "low": None}
    return {
        "location": label,
        "updated": f"{timesince(snapshot.fetched_at)} ago",
        "provider": "Open-Meteo",
        "current": {
            "temp_c": _whole(snapshot.current_temp_c), "feels_like": _whole(cur["feels_like"]), "condition": text, "icon": icon,
            "high": today["high"], "low": today["low"], "humidity": _whole(cur["humidity"]), "wind_kmh": _whole(cur["wind_kmh"]),
            "uv": _whole(cur["uv"]), "rain_last_24h_mm": float(snapshot.rain_last_24h_mm),
            "precip_prob_next_12h": snapshot.precip_prob_next_12h, "min_temp_next_48h_c": float(snapshot.min_temp_next_48h_c),
            "sunrise": _clock(cur["sunrise"]), "sunset": _clock(cur["sunset"]),
        },
        "daily": daily,
        "hourly": hourly,
        "thresholds": THRESHOLDS,
    }


def weather_for(user):
    """Live weather for the user's growing location, or None (no location yet, or the API is down and nothing is cached)."""
    if not user.is_authenticated:
        return None
    location = GrowingLocation.objects.filter(user=user).first()
    snapshot = location and get_snapshot(location.latitude, location.longitude, need_details=True)
    if not snapshot or not snapshot.details:
        return None
    return build_view(snapshot, ", ".join(part for part in (location.city, location.region) if part))


FROST_ACTIONS = [
    "Water the soil the afternoon before (moist soil holds heat)",
    "Cover plants with frost cloth or an old sheet at sunset",
    "Move pots against the wall or indoors",
    "Remove covers in the morning once it is above freezing",
]


def alerts_for(weather, outdoor, frost_sensitive):
    """Rain-skip and frost alerts (FR-41/42) for these outdoor plant names. Indoor plants never get one."""
    if not weather:
        return []
    now, limit = weather["current"], weather["thresholds"]
    alerts = []
    if frost_sensitive and now["min_temp_next_48h_c"] <= limit["frost_c"]:
        day = next((d for d in weather["daily"][:3] if d["frost"]), None)
        when = "tonight" if day and day["day_short"] == "Today" else (day["day_short"] if day else "soon")
        alerts.append({
            "id": f"frost-{day['date'] if day else 'soon'}", "alert_type": "frost", "icon": "i-snow", "when": when,
            "title": f"Frost risk {when}{'' if when == 'tonight' else ' night'} — low of {now['min_temp_next_48h_c']:g} °C",
            "message": f"Frost-sensitive outdoor plants can be damaged below {limit['frost_c']} °C.",
            "valid": f"{day['day_long']} · overnight" if day else "Next 48 hours", "plants": frost_sensitive,
            "actions": FROST_ACTIONS,
        })
    if outdoor and (now["rain_last_24h_mm"] >= limit["rain_mm"] or now["precip_prob_next_12h"] >= limit["rain_prob"]):
        reason = (f"{now['rain_last_24h_mm']:g} mm fell in the last 24h" if now["rain_last_24h_mm"] >= limit["rain_mm"]
                  else f"There is a {now['precip_prob_next_12h']}% chance of rain in the next 12h")
        alerts.append({
            "id": f"rain-{weather['daily'][0]['date'] if weather['daily'] else 'today'}", "alert_type": "rain_skip",
            "icon": "i-rain", "title": "Rain may do the watering today",
            "message": f"{reason}, so outdoor plants probably do not need watering. Indoor plants are unaffected.",
            "valid": "Today", "plants": outdoor, "actions": [],
        })
    return alerts
