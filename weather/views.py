from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from garden.selectors import HARVESTED, garden, weather_alerts
from garden.services import ACTIVE
from greenhand import clock
from greenhand.users import current_user
from notifications import services as notification_services
from plants.selectors import catalog_by_slug

from .services import weather_for


def _impact(plant, catalog, frost_day):
    """How this week's weather affects one plant (PRD 3.5 rule engine, FR-41/42)."""
    cat = catalog[plant["plant_slug"]]
    water = next((r for r in plant["reminders"] if r["type"] == "water" and r["active"]), None)
    skipped_today = any(h["date"] == clock.today().isoformat() and h["status"] == "skipped_rain" for r in plant["reminders"] for h in r["history"])
    outdoor = plant["setting"] == "outdoor"
    frost_risk = bool(outdoor and frost_day and not cat["frost_tolerant"])
    if not outdoor:
        today = {"text": "Indoor · not affected", "icon": "i-home", "cls": "bg-mist text-muted"}
    elif skipped_today:
        today = {"text": "Watering skipped — rain", "icon": "i-rain", "cls": "bg-sky-50 text-sky-800"}
    else:
        today = {"text": "Normal schedule", "icon": "i-check", "cls": "bg-emerald-50 text-emerald-800"}
    if not outdoor:
        frost = {"text": "Indoors", "cls": "text-muted"}
    elif frost_risk:
        frost = {"text": f"At risk {frost_day['day_short']} night", "cls": "font-medium text-indigo-700"}
    else:
        frost = {"text": "Tolerates light frost" if cat["frost_tolerant"] else "No frost expected", "cls": "text-emerald-700"}
    next_water = None
    if water:
        d = date.fromisoformat(water["next_due"])
        next_water = "Today" if d == clock.today() else ("Tomorrow" if (d - clock.today()).days == 1 else f"{d:%a, %b} {d.day}")
    return {
        "id": plant["id"], "nickname": plant["nickname"], "setting": plant["setting"], "icon": cat["icon"], "grad": cat["grad"],
        "today": today, "frost": frost, "frost_risk": frost_risk, "next_water": next_water,
        "weather_aware": bool(water and water["weather_aware"]),
    }


@login_required
def weather(request):
    user = current_user(request)
    notification_services.sync_weather(user)
    weather = weather_for(user)
    if not weather:
        return render(request, "weather/weather.html", {"weather": None})
    catalog = catalog_by_slug()
    all_plants = garden(user)
    plants = [p for p in all_plants if p["status"] in ACTIVE or p["status"] in (*HARVESTED, "planned")]
    frost_day = next((d for d in weather["daily"] if d["frost"]), None)
    impacts = [_impact(p, catalog, frost_day) for p in plants]
    return render(request, "weather/weather.html", {
        "weather": weather,
        "now": weather["current"],
        "alerts": weather_alerts(weather, all_plants, catalog),
        "impacts": impacts,
        "at_risk": [i for i in impacts if i["frost_risk"]],
        "thresholds": weather["thresholds"],
        "chart_data": {"hourly": weather["hourly"], "frost_c": weather["thresholds"]["frost_c"]},
    })
