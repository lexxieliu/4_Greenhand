"""Garden context for the tutor prompt (PRD 3.4 "Context injected into every conversation").

Only the minimum the model needs is sent (PRD 8.2): city-level location and hardiness zone,
growing space, the plant's species/stage/logs and the forecast. Never username, email or
coordinates. Reads the same mock data as the rest of the preview app.
"""
import re
from datetime import date, timedelta

from greenhand import mock_data as data

RECENT_DAYS = 14          # PRD FR-31: recent logs = last ~14 days
FORECAST_DAYS = 3
HIDDEN_STATUSES = ("failed", "archived")


def garden_plants():
    """Plants the user can ask about (not failed or archived)."""
    return [p for p in data.GARDEN if p["status"] not in HIDDEN_STATUSES]


def find_plant(plant_id):
    return next((p for p in garden_plants() if p["id"] == plant_id), None)


def detect_plant(question):
    """The garden plant the question mentions by its full nickname or a species word ('my tomatoes' -> tomato),
    or None. Single nickname words are ignored: 'balcony' must not select 'Balcony Basil'."""
    text = question.lower()
    words = re.findall(r"[a-z]+", text)
    for plant in garden_plants():
        species = data.CATALOG_BY_SLUG[plant["plant_slug"]]["common_name"].lower()
        keys = {w for w in re.findall(r"[a-z]+", species) if len(w) >= 4}
        if plant["nickname"].lower() in text or any(word.startswith(key) for word in words for key in keys):
            return plant
    return None


def _days_since(iso_day):
    return (data.TODAY - date.fromisoformat(iso_day)).days


def _plant_line(plant):
    species = data.CATALOG_BY_SLUG[plant["plant_slug"]]["common_name"]
    when = (f"planned for {plant['planted_on']}" if plant["status"] == "planned"
            else f"day {_days_since(plant['planted_on'])} since planting")
    open_problems = [p["title"] for p in plant["problems"] if p["status"] != "resolved"]
    problems = f"; open problem: {', '.join(open_problems)}" if open_problems else ""
    return (f"{plant['nickname']} ({species}{', ' + plant['variety'] if plant['variety'] else ''}): "
            f"{plant['status']}, {when}, {plant['setting']}, {plant['container'] or 'no container noted'}{problems}")


def _plant_details(plant):
    """Recent care logs, timeline notes and open problems for a scoped plant."""
    since = data.TODAY - timedelta(days=RECENT_DAYS)
    recent = lambda items: [i for i in items if date.fromisoformat(i["date"]) >= since]
    lines = [f"Care logs (last {RECENT_DAYS} days): " + ("; ".join(
        f"{c['date']} {c['action']}{' ' + c['amount'] if c['amount'] else ''}{' (' + c['note'] + ')' if c['note'] else ''}"
        for c in recent(plant["care"])) or "none")]
    lines += [f"Timeline note {t['date']} ({t['stage']}): {t['note']}" for t in recent(plant["timeline"])]
    for problem in plant["problems"]:
        if problem["status"] != "resolved":
            lines.append(f"Open problem since {problem['opened']}: {problem['title']} – {problem['description']}")
    return lines


def _weather_lines():
    now = data.WEATHER["current"]
    lines = [f"Now {now['temp_c']} °C, {now['condition'].lower()}; rain in the last 24h: {now['rain_last_24h_mm']} mm"]
    for day in data.WEATHER["daily"][:FORECAST_DAYS]:
        frost = " – FROST RISK" if day["frost"] else ""
        lines.append(f"{day['day_long']}: {day['condition'].lower()}, high {day['high']} °C, low {day['low']} °C{frost}")
    return lines


def _alert_lines(plant):
    """Active weather alerts (PRD 3.4 context), limited to the scoped plant when there is one."""
    alerts = [a for a in data.WEATHER_ALERTS if not plant or plant["nickname"] in a["plants"]]
    return [f"Active alert: {a['title']} ({a['valid']}); affects {', '.join(a['plants'])}" for a in alerts]


def _setting_rule(plant):
    """The app's weather rules (FR-41/42/45): rain and frost only apply to outdoor plants."""
    if plant["setting"] == "outdoor":
        return "Setting rule: outdoor plant, so rain counts as watering and frost can damage it."
    return f"Setting rule: {plant['setting']} plant, so rain and frost do NOT affect it; water it by checking its soil."


def build_context(plant=None):
    """Plain-text context block. With a plant, it is scoped to that plant (PRD FR-32)."""
    user = data.USER
    lines = [
        f"Today: {data.TODAY:%A, %B} {data.TODAY.day}, {data.TODAY.year}",
        f"Location: {data.LOCATION['label']}, hardiness zone {data.LOCATION['hardiness_zone']}",
        f"Grower: {user['experience_level'].lower()}, {user['space_type'].lower()}, {user['sunlight_level'].lower()}",
    ]
    if not plant or plant["setting"] == "outdoor":      # indoor plants: the outdoor forecast is irrelevant (FR-45)
        lines.append("Weather: " + " | ".join(_weather_lines()))
        lines += _alert_lines(plant)
    if plant:
        lines.append("Plant asked about: " + _plant_line(plant))
        lines.append(_setting_rule(plant))
        lines += _plant_details(plant)
    else:
        lines.append("Garden: " + " | ".join(_plant_line(p) for p in garden_plants()))
    return "\n".join(lines)
