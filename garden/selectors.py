"""Read queries for My Garden and the dashboard.

garden(user) returns the user's plants as plain dicts in the shape the My Garden script
(static/js/garden.js), the weather page, the community composer and the tutor context use.
"""
from datetime import date, timedelta

from django.http import Http404

from greenhand import mock_data
from greenhand.clock import today
from plants import selectors as plant_selectors
from plants.services import suitability

from .models import Problem, Reminder, UserPlant
from .services import ACTIVE

ENDED_OR_HIDDEN = ("failed", "archived")
HARVESTED = ("producing", "completed")

# CareLog.action choices shown in the dashboard "Log care" dialog: (value, label, icon)
CARE_ACTIONS = [
    ("water", "Water", "i-drop"), ("fertilize", "Fertilize", "i-flask"), ("prune", "Prune", "i-scissors"),
    ("treat_pest", "Treat pest", "i-bug"), ("repot", "Repot", "i-pot"), ("other", "Other", "i-plus"),
]


def user_plants(user):
    return (UserPlant.objects.filter(user=user)
            .select_related("plant")
            .prefetch_related("plant__problem_summaries", "timeline", "care_logs", "problems", "harvests",
                              "reminders__occurrences"))


def get_user_plant(user, user_plant_id):
    """The user's own plant, or 404 (also for other users' plants, so ids can't be probed)."""
    user_plant = UserPlant.objects.select_related("plant").filter(user=user, pk=user_plant_id).first()
    if not user_plant:
        raise Http404("Plant not found")
    return user_plant


def get_problem(user, problem_id):
    problem = Problem.objects.select_related("user_plant__plant").filter(user_plant__user=user, pk=problem_id).first()
    if not problem:
        raise Http404("Problem not found")
    return problem


def get_reminder(user, reminder_id):
    reminder = Reminder.objects.select_related("user_plant__plant").filter(user=user, pk=reminder_id).first()
    if not reminder:
        raise Http404("Reminder not found")
    return reminder


def _photo(field):
    return field.url if field else False


def plant_dict(up):
    """One UserPlant with its logs, in the shape of the former mock_data.GARDEN entries."""
    tips = up.plant.care_tips
    return {
        "id": str(up.pk),
        "type": up.plant.slug,
        "plant_slug": up.plant.slug,
        "species": up.plant.common_name,
        "nickname": up.nickname,
        "variety": up.variety,
        "planted_on": up.planted_on.isoformat(),
        "start_method": up.start_method,
        "setting": up.setting,
        "container": up.container_type,
        "quantity": up.quantity,
        "status": up.status,
        "harvest_mode": up.plant.harvest_mode,
        "watering_interval_days": up.watering_interval_days,
        "failure_reason": up.get_failure_reason_display() if up.failure_reason else "",
        "first_harvest_at": up.first_harvest_at.date().isoformat() if up.first_harvest_at else None,
        "tip": tips[0] if tips else f"Your tutor will tailor tips for {up.nickname} as you log its progress.",
        "timeline": [{"id": str(t.pk), "stage": t.stage, "date": t.recorded_on.isoformat(), "note": t.note,
                      "photo": _photo(t.photo)} for t in up.timeline.all()],
        "care": [{"id": str(c.pk), "action": c.action, "amount": c.amount, "note": c.note,
                  "date": c.performed_on.isoformat(), "source": c.source} for c in up.care_logs.all()],
        "problems": [{
            "id": str(p.pk), "title": p.title, "category": p.category, "severity": p.severity, "status": p.status,
            "description": p.description, "opened": p.opened_on.isoformat(), "photo": _photo(p.photo),
            "resolved": p.resolved_at.date().isoformat() if p.resolved_at else None,
            "resolution_note": p.resolution_note,
        } for p in up.problems.all()],
        "harvests": [{"id": str(h.pk), "date": h.harvested_on.isoformat(),
                      "quantity": float(h.quantity) if h.quantity is not None else None, "unit": h.unit,
                      "note": h.note, "photo": _photo(h.photo)} for h in up.harvests.all()],
        "reminders": [{
            "id": str(r.pk), "type": r.type, "title": r.title, "every": r.interval_days, "time": r.time.strftime("%H:%M"),
            "weather_aware": r.weather_aware, "active": r.is_active, "inapp": r.notify_in_app, "email": r.notify_email,
            "next_due": r.next_due_on.isoformat(),
            "history": [{"date": o.due_on.isoformat(), "status": o.status, "reason": o.reason} for o in r.occurrences.all()],
        } for r in up.reminders.all()],
    }


def garden(user):
    return [plant_dict(up) for up in user_plants(user)]


def plant_payload(user, user_plant_id):
    """Fresh dict for one plant, returned by the JSON endpoints after a change."""
    return plant_dict(user_plants(user).get(pk=user_plant_id))


def in_garden_by_slug(user):
    """{plant slug: [nicknames]} of the user's growing plants (plant list and detail pages)."""
    names = {}
    for up in UserPlant.objects.filter(user=user).exclude(status__in=ENDED_OR_HIDDEN).select_related("plant"):
        names.setdefault(up.plant.slug, []).append(up.nickname)
    return names


# ---------------------------------------------------------------------------
# My Garden page
# ---------------------------------------------------------------------------

def garden_catalog():
    """Catalog subset in the shape the My Garden script expects (keyed by slug). Includes unpublished plants
    so existing garden entries resolve; the Add plant dialog only offers published ones."""
    return {
        p["slug"]: {
            "name": p["common_name"], "sci": p["scientific_name"], "water": p["watering_interval_days"],
            "harvest": p["days_to_harvest"], "frostOk": p["frost_tolerant"], "icon": p["icon"], "grad": p["grad"],
            "harvestMode": p["harvest_mode"], "published": p["published"],
            "suit": suitability(p)["level"], "suitLabel": suitability(p)["reason"],
        }
        for p in plant_selectors.catalog_by_slug().values()
    }


def weather_summary():
    """Rain-skip / frost info for plant badges. Mock weather until the weather area lands."""
    alerts = {a["alert_type"]: a for a in mock_data.WEATHER_ALERTS}
    frost_day = next((d for d in mock_data.WEATHER["daily"] if d["frost"]), None)
    return {
        "rainToday": "rain_skip" in alerts,
        "rainMm": mock_data.WEATHER["current"]["rain_last_24h_mm"],
        "frostDate": frost_day["date"] if frost_day else None,
        "frostLow": frost_day["low"] if frost_day else None,
        "frostThreshold": mock_data.FROST_THRESHOLD_C,
    }


def garden_payload(user):
    """Everything the My Garden page script needs, passed with |json_script."""
    return {"today": today().isoformat(), "plants": garden(user), "catalog": garden_catalog(), "weather": weather_summary()}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def day_count(plant):
    """Days since planting (planting day = day 0)."""
    return (today() - date.fromisoformat(plant["planted_on"])).days


def open_problems(plant):
    return [p for p in plant["problems"] if p["status"] != "resolved"]


def harvest_grams(plant):
    to_g = {"g": 1, "kg": 1000, "oz": 28.35, "lb": 453.6}
    return sum(h["quantity"] * to_g[h["unit"]] for h in plant["harvests"] if h.get("quantity") and h["unit"] in to_g)


def stats(plants):
    harvests = [h for p in plants for h in p["harvests"]]
    return {
        "active": sum(1 for p in plants if p["status"] in ACTIVE),
        "planned": sum(1 for p in plants if p["status"] == "planned"),
        "harvested_plants": sum(1 for p in plants if p["status"] in HARVESTED),
        "harvest_count": len(harvests),
        "harvest_grams": round(sum(harvest_grams(p) for p in plants)),
        "open_problems": sum(len(open_problems(p)) for p in plants),
    }


def _frost_risk(plant, catalog):
    return plant["setting"] == "outdoor" and not catalog[plant["plant_slug"]]["frost_tolerant"] and plant["status"] in ACTIVE


def dashboard_rows(plants, catalog):
    """Compact plant rows for the dashboard 'My plants' card."""
    rows = []
    for p in plants:
        if p["status"] in ENDED_OR_HIDDEN:
            continue
        cat = catalog[p["plant_slug"]]
        problems = open_problems(p)
        frost = _frost_risk(p, catalog)
        if problems:
            sub, sub_cls = f"{problems[0]['title']} · {problems[0]['status']}", "text-amber-700"
            badge = {"icon": "i-alert", "cls": "bg-amber-100 text-amber-700", "title": "Needs attention"}
        elif frost:
            sub, sub_cls = f"{p['status'].capitalize()} · frost risk", "text-indigo-700"
            badge = {"icon": "i-snow", "cls": "bg-indigo-100 text-indigo-700", "title": "Frost risk"}
        elif p["status"] in HARVESTED:
            sub, sub_cls = f"{p['status'].capitalize()} · {round(harvest_grams(p))} g harvested", "text-leaf"
            badge = {"icon": "i-basket", "cls": "bg-amber-100 text-amber-700", "title": "Harvested"}
        elif p["status"] == "planned":
            sub, sub_cls = f"Planned · {suitability(cat)['label'].lower()}", "text-leaf"
            badge = {"icon": "i-calendar", "cls": "bg-mist text-muted ring-1 ring-line", "title": "Planned"}
        else:
            sub, sub_cls = f"{p['status'].capitalize()} · {p['setting']}", "text-leaf"
            badge = {"icon": "i-check", "cls": "bg-emerald-100 text-emerald-700", "title": "Healthy"}
        planted = date.fromisoformat(p["planted_on"])
        value = (f"{len(p['harvests'])}×" if p["status"] in HARVESTED
                 else f"{planted:%b} {planted.day}" if p["status"] == "planned" else f"Day {day_count(p)}")
        rows.append({
            "id": p["id"], "nickname": p["nickname"], "icon": cat["icon"], "grad": cat["grad"],
            "sub": sub, "sub_cls": sub_cls, "value": value, "badge": badge,
            "attention": bool(problems) or frost,
            "search": f"{p['nickname']} {cat['common_name']}".lower(),
        })
    return rows


TASK_STYLE = {
    "water": ("i-drop", "bg-sky-50 text-sky-600", "water"),
    "fertilize": ("i-flask", "bg-lime-50 text-lime-700", "feed"),
    "check_problem": ("i-alert", "bg-amber-50 text-amber-600", ""),
    "harvest_check": ("i-basket", "bg-amber-50 text-amber-700", ""),
    "custom": ("i-bell", "bg-mist text-forest", ""),
}


def tasks(plants):
    """Today's tasks (FR-24): active reminders due today or overdue, plus ones done or skipped today."""
    day = today().isoformat()
    out = []
    for p in plants:
        for r in p["reminders"]:
            done_today = next((h for h in r["history"] if h["date"] == day), None)
            due = r["active"] and r["next_due"] <= day
            if not (due or done_today):
                continue
            icon, tint, care = TASK_STYLE[r["type"]]
            overdue = due and r["next_due"] < day
            out.append({
                "id": r["id"], "plant": p["id"], "title": r["title"],
                "detail": f"{p['setting'].capitalize()} · {p['container'] or p['nickname']}"
                          + (f" · every {r['every']} days" if r["every"] else ""),
                "icon": icon, "tint": tint, "care": care,
                "done": bool(done_today and done_today["status"] == "done"),
                "skipped": "rain" if done_today and done_today["status"] == "skipped_rain" else "",
                "badge": ({"text": "Overdue", "cls": "bg-rose-100 text-rose-700"} if overdue
                          else {"text": r["time"], "cls": "bg-mist text-muted"}),
            })
    return out


ACTIVITY_STYLE = {
    "timeline": ("i-camera", "bg-pink-100 text-pink-700"), "care": ("i-drop", "bg-sky-100 text-sky-700"),
    "problem": ("i-alert", "bg-amber-100 text-amber-700"), "harvest": ("i-basket", "bg-amber-100 text-amber-700"),
}
CARE_PAST = {"water": "watered", "fertilize": "fed", "prune": "pruned", "treat_pest": "treated for pests",
             "repot": "repotted", "transplant": "transplanted", "other": "cared for"}
STAGE_LABELS = {"seed": "Sowed", "seedling": "Seedling", "vegetative": "Vegetative growth", "flowering": "Flowering",
                "fruiting": "Fruiting", "harvest": "Harvest"}


def _when(iso_day):
    days = (today() - date.fromisoformat(iso_day)).days
    if days == 0:
        return "Today"
    if days == 1:
        return "Yesterday"
    d = date.fromisoformat(iso_day)
    return f"{d:%b} {d.day}"


def activity(plants, limit=5):
    """Most recent timeline, care, problem and harvest entries across the garden."""
    items = []
    for p in plants:
        name = p["nickname"]
        items += [(t["date"], "timeline", name, f"timeline: {STAGE_LABELS[t['stage']].lower()}", "Timeline") for t in p["timeline"]]
        items += [(c["date"], "care", name, CARE_PAST[c["action"]] + (f" · {c['amount']}" if c["amount"] else ""), "Care log")
                  for c in p["care"]]
        items += [(x["opened"], "problem", name, f"problem logged: {x['title'].lower()}", "Problem log") for x in p["problems"]]
        items += [(h["date"], "harvest", name, "harvested" + (f" {h['quantity']:g} {h['unit']}" if h["quantity"] else ""),
                   "Harvest log") for h in p["harvests"]]
    items.sort(key=lambda item: item[0], reverse=True)
    return [{"icon": ACTIVITY_STYLE[kind][0], "tint": ACTIVITY_STYLE[kind][1], "subject": name, "text": text,
             "meta": f"{source} · {_when(day)}"} for day, kind, name, text, source in items[:limit]]


CHART_CATEGORY = {"water": "water", "fertilize": "feed", "prune": "prune"}


def care_chart(plants, weeks=12, days=14):
    """Care actions per category for the dashboard chart: last `weeks` weeks and last `days` days."""
    week_start = today() - timedelta(days=today().weekday() + 7 * (weeks - 1))
    week_labels = [week_start + timedelta(weeks=i) for i in range(weeks)]
    chart = {
        "weeks": {"labels": [f"{d:%b} {d.day}" for d in week_labels], **{k: [0] * weeks for k in ("water", "feed", "prune", "harvest")}},
        "days": {k: [0] * days for k in ("water", "feed", "prune", "harvest")},
    }
    events = [(c["date"], CHART_CATEGORY.get(c["action"])) for p in plants for c in p["care"]]
    events += [(h["date"], "harvest") for p in plants for h in p["harvests"]]
    for iso_day, category in events:
        if not category:
            continue
        d = date.fromisoformat(iso_day)
        week = (d - week_start).days // 7
        if 0 <= week < weeks:
            chart["weeks"][category][week] += 1
        day = days - 1 - (today() - d).days
        if 0 <= day < days:
            chart["days"][category][day] += 1
    return chart


def featured(plants):
    """The active plant with the most recent timeline entry, for the dashboard spotlight card."""
    active = [p for p in plants if p["status"] in ACTIVE]
    if not active:
        return None
    plant = max(active, key=lambda p: max((t["date"] for t in p["timeline"]), default=p["planted_on"]))
    return {**plant, "day": day_count(plant)}


def weekly_care(plant, weeks=7):
    """[[week label, care actions that week], …] for the featured plant's sparkline."""
    start = today() - timedelta(days=today().weekday() + 7 * (weeks - 1))
    counts = [0] * weeks
    for c in plant["care"]:
        week = (date.fromisoformat(c["date"]) - start).days // 7
        if 0 <= week < weeks:
            counts[week] += 1
    return [[f"Week of {start + timedelta(weeks=i):%b} {(start + timedelta(weeks=i)).day}", n] for i, n in enumerate(counts)]


STAGE_EVENT = {"seed": "Sowed", **{k: v for k, v in STAGE_LABELS.items() if k != "seed"}}
CARE_LABEL = {"water": "Watered", "fertilize": "Fed", "prune": "Pruned", "treat_pest": "Treated pests on",
              "repot": "Repotted", "transplant": "Transplanted", "other": "Cared for"}
REMINDER_EVENT = {"water": "water", "fertilize": "growth", "check_problem": "problem", "harvest_check": "harvest", "custom": "growth"}


def calendar_events(plants, days_ahead=60):
    """Garden-wide icon calendar (FR-23) as {"YYYY-MM-DD": [{type, label, icon}]}.
    Types match the dashboard legend: water, growth, harvest, weather, problem."""
    events = {}

    def add(day, kind, label, icon=None):
        events.setdefault(day, []).append({"type": kind, "label": label, **({"icon": icon} if icon else {})})

    horizon = today() + timedelta(days=days_ahead)
    for p in plants:
        name = p["nickname"]
        for t in p["timeline"]:
            add(t["date"], "growth", f"{name}: {STAGE_EVENT[t['stage']]}")
        for log in p["care"]:
            add(log["date"], "water" if log["action"] == "water" else "growth", f"{CARE_LABEL[log['action']]} {name}")
        for h in p["harvests"]:
            add(h["date"], "harvest", f"Harvested {name} · {h['quantity']:g} {h['unit']}" if h.get("quantity") else f"Harvested {name}")
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
                if due >= today():
                    add(due.isoformat(), REMINDER_EVENT[r["type"]], r["title"])
                if not r["every"]:
                    break
                due += timedelta(days=r["every"])
    for d in mock_data.WEATHER["daily"]:
        if d["frost"]:
            add(d["date"], "weather", f"Frost risk tonight · {d['low']} °C")
    return events
