from datetime import date

from django.shortcuts import render

from greenhand import mock_data as data
from garden.services import ACTIVE


def _impact(plant):
    """How this week's weather affects one plant (PRD 3.5 rule engine, FR-41/42)."""
    cat = data.CATALOG_BY_SLUG[plant["plant_slug"]]
    water = next((r for r in plant["reminders"] if r["type"] == "water" and r["active"]), None)
    skipped_today = any(h["date"] == data.TODAY.isoformat() and h["status"] == "skipped_rain" for r in plant["reminders"] for h in r["history"])
    outdoor = plant["setting"] == "outdoor"
    frost_risk = outdoor and not cat["frost_tolerant"]
    if not outdoor:
        today = {"text": "Indoor · not affected", "icon": "i-home", "cls": "bg-mist text-muted"}
    elif skipped_today:
        today = {"text": "Watering skipped — rain", "icon": "i-rain", "cls": "bg-sky-50 text-sky-800"}
    else:
        today = {"text": "Normal schedule", "icon": "i-check", "cls": "bg-emerald-50 text-emerald-800"}
    if not outdoor:
        frost = {"text": "Indoors", "cls": "text-muted"}
    elif frost_risk:
        frost = {"text": "At risk Thu night", "cls": "font-medium text-indigo-700"}
    else:
        frost = {"text": "Tolerates light frost", "cls": "text-emerald-700"}
    next_water = None
    if water:
        d = date.fromisoformat(water["next_due"])
        next_water = "Today" if d == data.TODAY else ("Tomorrow" if (d - data.TODAY).days == 1 else f"{d:%a, %b} {d.day}")
    return {
        "id": plant["id"], "nickname": plant["nickname"], "setting": plant["setting"], "icon": cat["icon"], "grad": cat["grad"],
        "today": today, "frost": frost, "frost_risk": frost_risk, "next_water": next_water,
        "weather_aware": bool(water and water["weather_aware"]),
    }


def weather(request):
    plants = [p for p in data.GARDEN if p["status"] in ACTIVE or p["status"] in ("harvested", "planned")]
    impacts = [_impact(p) for p in plants]
    return render(request, "weather/weather.html", {
        "weather": data.WEATHER,
        "now": data.WEATHER["current"],
        "alerts": data.WEATHER_ALERTS,
        "impacts": impacts,
        "at_risk": [i for i in impacts if i["frost_risk"]],
        "thresholds": data.WEATHER["thresholds"],
        "chart_data": {"hourly": data.WEATHER["hourly"], "frost_c": data.FROST_THRESHOLD_C},
    })
