"""Derived values for My Garden and the dashboard (PRD 3.3)."""
from datetime import date, timedelta

from greenhand import mock_data as data
from plants.services import suitability

ACTIVE = ("sprouting", "growing", "flowering", "fruiting")

# CareLog.action choices shown in the quick "Log care" dialog: (value, label, icon)
CARE_ACTIONS = [
    ("water", "Water", "i-drop"), ("fertilize", "Fertilize", "i-flask"), ("prune", "Prune", "i-scissors"),
    ("treat_pest", "Treat pest", "i-bug"), ("repot", "Repot", "i-pot"), ("other", "Other", "i-plus"),
]

def day_count(plant):
    """Days since planting (planting day = day 0)."""
    return (data.TODAY - date.fromisoformat(plant["planted_on"])).days


def open_problems(plant):
    return [p for p in plant["problems"] if p["status"] != "resolved"]


def harvest_grams(plant):
    to_g = {"g": 1, "kg": 1000, "oz": 28.35, "lb": 453.6}
    return sum(h["quantity"] * to_g[h["unit"]] for h in plant["harvests"] if h.get("quantity") and h["unit"] in to_g)


def stats():
    garden = data.GARDEN
    harvests = [h for p in garden for h in p["harvests"]]
    return {
        "active": sum(1 for p in garden if p["status"] in ACTIVE),
        "planned": sum(1 for p in garden if p["status"] == "planned"),
        "harvested_plants": sum(1 for p in garden if p["status"] == "harvested"),
        "harvest_count": len(harvests),
        "harvest_grams": round(sum(harvest_grams(p) for p in garden)),
        "open_problems": sum(len(open_problems(p)) for p in garden),
    }


def dashboard_rows():
    """Compact plant rows for the dashboard 'My plants' card."""
    rows = []
    for p in data.GARDEN:
        if p["status"] in ("failed", "archived"):
            continue
        cat = data.CATALOG_BY_SLUG[p["plant_slug"]]
        problems = open_problems(p)
        frost = p["setting"] == "outdoor" and not cat["frost_tolerant"] and p["status"] in ACTIVE
        if problems:
            sub, sub_cls = f"{problems[0]['title']} · {problems[0]['status']}", "text-amber-700"
            badge = {"icon": "i-alert", "cls": "bg-amber-100 text-amber-700", "title": "Needs attention"}
        elif frost:
            sub, sub_cls = f"{p['status'].capitalize()} · frost risk Thu", "text-indigo-700"
            badge = {"icon": "i-snow", "cls": "bg-indigo-100 text-indigo-700", "title": "Frost risk"}
        elif p["status"] == "harvested":
            sub, sub_cls = f"Harvested · {round(harvest_grams(p))} g", "text-leaf"
            badge = {"icon": "i-basket", "cls": "bg-amber-100 text-amber-700", "title": "Harvested"}
        elif p["status"] == "planned":
            sub, sub_cls = f"Planned · {suitability(cat)['label'].lower()}", "text-leaf"
            badge = {"icon": "i-calendar", "cls": "bg-mist text-muted ring-1 ring-line", "title": "Planned"}
        else:
            sub, sub_cls = f"{p['status'].capitalize()} · {p['setting']}", "text-leaf"
            badge = {"icon": "i-check", "cls": "bg-emerald-100 text-emerald-700", "title": "Healthy"}
        if p["status"] == "harvested":
            value = f"{len(p['harvests'])}×"
        elif p["status"] == "planned":
            value = date.fromisoformat(p["planted_on"]).strftime("%b ") + str(date.fromisoformat(p["planted_on"]).day)
        else:
            value = f"Day {day_count(p)}"
        rows.append({
            "id": p["id"], "nickname": p["nickname"], "icon": cat["icon"], "grad": cat["grad"],
            "sub": sub, "sub_cls": sub_cls, "value": value, "badge": badge,
            "attention": bool(problems) or frost,
            "search": f"{p['nickname']} {cat['common_name']}".lower(),
        })
    return rows


def garden_catalog():
    """Catalog subset in the shape the My Garden script expects (keyed by slug)."""
    return {
        p["slug"]: {
            "name": p["common_name"], "sci": p["scientific_name"], "water": p["watering_interval_days"],
            "harvest": p["days_to_harvest"], "frostOk": p["frost_tolerant"], "icon": p["icon"], "grad": p["grad"],
            "suit": suitability(p)["level"], "suitLabel": suitability(p)["reason"],
        }
        for p in data.CATALOG
    }


def garden_payload():
    """Everything the My Garden page script needs, passed with |json_script."""
    plants = [{**p, "type": p["plant_slug"]} for p in data.GARDEN]
    alerts = {a["alert_type"]: a for a in data.WEATHER_ALERTS}
    frost_day = next((d for d in data.WEATHER["daily"] if d["frost"]), None)
    return {
        "today": data.TODAY.isoformat(),
        "plants": plants,
        "catalog": garden_catalog(),
        "weather": {
            "rainToday": "rain_skip" in alerts,
            "rainMm": data.WEATHER["current"]["rain_last_24h_mm"],
            "frostDate": frost_day["date"] if frost_day else None,
            "frostLow": frost_day["low"] if frost_day else None,
            "frostThreshold": data.FROST_THRESHOLD_C,
        },
    }


STAGE_LABELS = {"seed": "Sowed", "seedling": "Seedling", "vegetative": "Vegetative growth", "flowering": "Flowering", "fruiting": "Fruiting", "harvest": "Harvest"}
CARE_PAST = {"water": "Watered", "fertilize": "Fed", "prune": "Pruned", "treat_pest": "Treated pests on", "repot": "Repotted", "transplant": "Transplanted", "other": "Cared for"}
REMINDER_EVENT = {"water": "water", "fertilize": "growth", "check_problem": "problem", "harvest_check": "harvest", "custom": "growth"}


def calendar_events(days_ahead=60):
    """Garden-wide icon calendar (FR-23) as {"YYYY-MM-DD": [{type, label, icon}]}.
    Types match the dashboard legend: water, growth, harvest, weather, problem."""
    events = {}

    def add(day, kind, label, icon=None):
        events.setdefault(day, []).append({"type": kind, "label": label, **({"icon": icon} if icon else {})})

    horizon = data.TODAY + timedelta(days=days_ahead)
    for p in data.GARDEN:
        name = p["nickname"]
        for t in p["timeline"]:
            add(t["date"], "growth", f"{name}: {STAGE_LABELS[t['stage']]}")
        for log in p["care"]:
            add(log["date"], "water" if log["action"] == "water" else "growth", f"{CARE_PAST[log['action']]} {name}")
        for h in p["harvests"]:
            add(h["date"], "harvest", f"Harvested {name} · {h['quantity']} {h['unit']}" if h.get("quantity") else f"Harvested {name}")
        for prob in p["problems"]:
            add(prob["opened"], "problem", f"{name}: {prob['title'].lower()}")
        for r in p["reminders"]:
            for occ in r["history"]:
                if occ["status"] == "skipped_rain":
                    add(occ["date"], "weather", f"{name} watering skipped — rain", "i-rain")
            if not r["active"]:
                continue
            due = date.fromisoformat(r["next_due"])
            while due <= horizon:
                if due >= data.TODAY:
                    add(due.isoformat(), REMINDER_EVENT[r["type"]], r["title"])
                if not r["every"]:
                    break
                due += timedelta(days=r["every"])
    for d in data.WEATHER["daily"]:
        if d["frost"]:
            add(d["date"], "weather", f"Frost risk tonight · {d['low']} °C")
    return events
