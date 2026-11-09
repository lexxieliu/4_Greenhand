"""Garden context for the tutor prompt (PRD 3.4 "Context injected into every conversation").

Only the minimum the model needs is sent (PRD 8.2): city-level location and hardiness zone,
growing space, the plant's species/stage/logs and the forecast. Never username, email or
coordinates. The garden comes from the database (garden.selectors); profile, location and weather
are still mock data until those areas are built.
"""
import re
from datetime import date, timedelta

from garden import selectors as garden_selectors
from greenhand import mock_data as data
from greenhand.clock import today

RECENT_DAYS = 14          # PRD FR-31: recent logs = last ~14 days
FORECAST_DAYS = 3
HIDDEN_STATUSES = ("failed", "archived")


def garden_plants(user):
    """The user's plants they can ask about (not failed or archived)."""
    return [p for p in garden_selectors.garden(user) if p["status"] not in HIDDEN_STATUSES]


def find_plant(plant_id, user):
    return next((p for p in garden_plants(user) if p["id"] == str(plant_id)), None)


def detect_plant(question, user):
    """The garden plant the question mentions by its full nickname or a species word ('my tomatoes' -> tomato),
    or None. Single nickname words are ignored: 'balcony' must not select 'Balcony Basil'."""
    text = question.lower()
    words = re.findall(r"[a-z]+", text)
    for plant in garden_plants(user):
        species = plant["species"].lower()
        keys = {w for w in re.findall(r"[a-z]+", species) if len(w) >= 4}
        if plant["nickname"].lower() in text or any(word.startswith(key) for word in words for key in keys):
            return plant
    return None


def _days_since(iso_day):
    return (today() - date.fromisoformat(iso_day)).days


def _plant_line(plant):
    species = plant["species"]
    when = (f"planned for {plant['planted_on']}" if plant["status"] == "planned"
            else f"day {_days_since(plant['planted_on'])} since planting")
    open_problems = [p["title"] for p in plant["problems"] if p["status"] != "resolved"]
    problems = f"; open problem: {', '.join(open_problems)}" if open_problems else ""
    return (f"{plant['nickname']} ({species}{', ' + plant['variety'] if plant['variety'] else ''}): "
            f"{plant['status']}, {when}, {plant['setting']}, {plant['container'] or 'no container noted'}{problems}")


def _plant_details(plant):
    """Recent care logs, timeline notes and open problems for a scoped plant."""
    since = today() - timedelta(days=RECENT_DAYS)
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


def build_context(user, plant=None):
    """Plain-text context block for this user's garden. With a plant, it is scoped to that plant (PRD FR-32)."""
    profile = data.USER
    day = today()
    lines = [
        f"Today: {day:%A, %B} {day.day}, {day.year}",
        f"Location: {data.LOCATION['label']}, hardiness zone {data.LOCATION['hardiness_zone']}",
        f"Grower: {profile['experience_level'].lower()}, {profile['space_type'].lower()}, {profile['sunlight_level'].lower()}",
    ]
    if not plant or plant["setting"] == "outdoor":      # indoor plants: the outdoor forecast is irrelevant (FR-45)
        lines.append("Weather: " + " | ".join(_weather_lines()))
        lines += _alert_lines(plant)
    if plant:
        lines.append("Plant asked about: " + _plant_line(plant))
        lines.append(_setting_rule(plant))
        lines += _plant_details(plant)
    else:
        lines.append("Garden: " + " | ".join(_plant_line(p) for p in garden_plants(user)))
    return "\n".join(lines)
