from datetime import time

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from calendar_app.models import ReminderOccurrence
from calendar_app.selectors import calendar_payload
from greenhand import mock_data as data
from plants.selectors import catalog_by_slug
from weather.selectors import weather_cards

from . import selectors, services
from .forms import (CareLogForm, HarvestForm, ProblemForm, ProblemStatusForm, ReminderFlagForm, ReminderForm,
                    StartGrowingForm, StatusForm, TimelineForm)
from .models import UserPlant


def _live_weather(user):
    """The first location's cached weather (Area 3) in the shape the dashboard weather card uses."""
    card = next(iter(weather_cards(user)), None)
    snapshot = card["snapshot"] if card else None
    return {
        "location": card["location"].label if card else "Location not set",
        "updated": snapshot.fetched_at if snapshot else "Unavailable",
        "daily": [{**day, "day_short": day["date"].strftime("%a"), "icon": "i-cloud"} for day in card["daily"]] if card else [],
        "current": {
            "temp_c": snapshot.current_temp_c,
            "icon": "i-cloud",
            "condition": "Cached" if card["stale"] else "Current conditions",
            "rain_last_24h_mm": snapshot.rain_last_24h_mm,
            "precip_prob_next_12h": snapshot.precip_prob_next_12h,
            "min_temp_next_48h_c": snapshot.min_temp_next_48h_c,
            "high": snapshot.max_temp_next_48h_c,
            "low": snapshot.min_temp_next_48h_c,
        } if snapshot else None,
    }


def _merge_events(*sources):
    events = {}
    for source in sources:
        for day, items in source.items():
            events.setdefault(day, []).extend(items)
    return events


@login_required
def dashboard(request):
    user = request.user
    plants = selectors.garden(user)
    catalog = catalog_by_slug()
    alerts = selectors.alerts_by_plant(user)
    featured = selectors.featured(plants)
    same_plant_slugs = {p["plant_slug"] for p in plants}
    community = [
        {**p, "author_info": data.AUTHORS[p["author"]], "type_info": data.POST_TYPES[p["post_type"]],
         "plant_name": catalog[p["plant_slug"]]["common_name"] if p["plant_slug"] in catalog else ""}
        for p in data.POSTS if p["plant_slug"] in same_plant_slugs and p["author"] != user.username
    ][:2]
    return render(request, "garden/dashboard.html", {
        "stats": selectors.stats(plants),
        "plant_rows": selectors.dashboard_rows(plants, catalog, alerts),
        "tasks": ReminderOccurrence.objects.filter(reminder__user=user, due_at__date=timezone.localdate())
                 .select_related("reminder"),
        "live_alerts": list(alerts.values()),
        "weather": _live_weather(user),
        "tips": data.TUTOR_WEEKLY_TIPS,
        "activity": selectors.activity(plants),
        "community": community,
        "featured": featured,
        "care_actions": selectors.CARE_ACTIONS,
        "garden_api": reverse("garden:dashboard"),
        "log_plants": [p for p in plants if p["status"] not in ("planned", "failed", "archived")],
        "dashboard_data": {
            "care": selectors.care_chart(plants),
            "featured": selectors.weekly_care(featured) if featured else [],
            # garden logs + stored calendar events (reminder occurrences, frost alerts, manual events)
            "events": _merge_events(selectors.calendar_events(plants), calendar_payload(user)),
        },
    })


@login_required
def my_garden(request):
    payload = {**selectors.garden_payload(request.user), "api": reverse("garden:dashboard"),
               "communityUrl": reverse("community:feed"),
               "notificationSettingsUrl": reverse("notifications:preferences")}
    return render(request, "garden/my_garden.html", {
        "stats": selectors.stats(payload["plants"]),
        "garden_data": payload,
        "failure_reasons": UserPlant.FailureReason.choices,
    })


# ---------------------------------------------------------------------------
# JSON endpoints used by static/js/garden.js and dashboard.js. Each validates with a form, calls one
# service, and returns the refreshed plant so the page re-renders from saved data.
# ---------------------------------------------------------------------------

def _invalid(form):
    message = next(iter(form.errors.values()))[0]
    return JsonResponse({"error": message, "fields": form.errors}, status=400)


def _plant_response(user, user_plant_id, message="", status=200):
    return JsonResponse({"plant": selectors.plant_payload(user, user_plant_id), "message": message}, status=status)


def _run(user, user_plant_id, action):
    """Run a service call; GardenError becomes a 400 with its user-facing message."""
    try:
        message = action()
    except services.GardenError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return _plant_response(user, user_plant_id, message or "")


@login_required
@require_POST
def add_plant(request):
    """Start Growing from the My Garden "Add plant" dialog (FR-13)."""
    user = request.user
    form = StartGrowingForm(request.POST)
    if not form.is_valid():
        return _invalid(form)
    d = form.cleaned_data
    user_plant = services.start_growing(user, d["plant"], nickname=d["nickname"].strip(), planted_on=d["planted_on"],
                                        start_method=d["start_method"], setting=d["setting"],
                                        container_type=d["container"].strip(), quantity=d["quantity"] or 1)
    return _plant_response(user, user_plant.pk, f"{user_plant.nickname} added · watering every "
                                                f"{user_plant.watering_interval_days} days", status=201)


@login_required
@require_POST
def add_timeline_entry(request, user_plant_id):
    user = request.user
    user_plant = selectors.get_user_plant(user, user_plant_id)
    form = TimelineForm(request.POST, request.FILES)
    if not form.is_valid():
        return _invalid(form)
    d = form.cleaned_data
    new_status = services.add_timeline_entry(user_plant, stage=d["stage"], recorded_on=d["date"], note=d["note"].strip(),
                                             photo=d["photo"], update_status=d["update_status"])
    return _plant_response(user, user_plant.pk, f"Entry added · status now {new_status}" if new_status else "Timeline entry added")


@login_required
@require_POST
def log_care(request, user_plant_id):
    user = request.user
    user_plant = selectors.get_user_plant(user, user_plant_id)
    form = CareLogForm(request.POST)
    if not form.is_valid():
        return _invalid(form)
    d = form.cleaned_data
    log = services.log_care(user_plant, action=d["action"], performed_on=d["date"], amount=d["amount"].strip(),
                            note=d["note"].strip())
    return _plant_response(user, user_plant.pk, f"{log.get_action_display()} logged for {user_plant.nickname}")


@login_required
@require_POST
def log_problem(request, user_plant_id):
    user = request.user
    user_plant = selectors.get_user_plant(user, user_plant_id)
    form = ProblemForm(request.POST, request.FILES)
    if not form.is_valid():
        return _invalid(form)
    d = form.cleaned_data
    services.log_problem(user_plant, title=d["title"].strip(), description=d["description"].strip(),
                         category=d["category"], severity=d["severity"], photo=d["photo"])
    return _plant_response(user, user_plant.pk, "Problem logged · follow-up reminder set for 3 days")


@login_required
@require_POST
def set_problem_status(request, problem_id):
    user = request.user
    problem = selectors.get_problem(user, problem_id)
    form = ProblemStatusForm(request.POST)
    if not form.is_valid():
        return _invalid(form)
    services.set_problem_status(problem, form.cleaned_data["status"], form.cleaned_data["resolution_note"].strip())
    return _plant_response(user, problem.user_plant_id, f"Problem marked {problem.get_status_display().lower()}")


@login_required
@require_POST
def log_harvest(request, user_plant_id):
    user = request.user
    user_plant = selectors.get_user_plant(user, user_plant_id)
    form = HarvestForm(request.POST, request.FILES)
    if not form.is_valid():
        return _invalid(form)
    d = form.cleaned_data

    def action():
        services.log_harvest(user_plant, harvested_on=d["date"], quantity=d["quantity"], unit=d["unit"],
                             note=d["note"].strip(), photo=d["photo"], final=d["final"])
        if user_plant.status == "completed":
            return f"{user_plant.nickname} harvested — congratulations!"
        return "Harvest logged"
    return _run(user, user_plant.pk, action)


@login_required
@require_POST
def change_status(request, user_plant_id):
    user = request.user
    user_plant = selectors.get_user_plant(user, user_plant_id)
    form = StatusForm(request.POST)
    if not form.is_valid():
        return _invalid(form)

    def action():
        services.change_status(user_plant, form.cleaned_data["status"], form.cleaned_data["failure_reason"])
        return f"Status changed to {user_plant.get_status_display()}"
    return _run(user, user_plant.pk, action)


@login_required
@require_POST
def add_reminder(request, user_plant_id):
    user = request.user
    user_plant = selectors.get_user_plant(user, user_plant_id)
    form = ReminderForm(request.POST)
    if not form.is_valid():
        return _invalid(form)
    d = form.cleaned_data
    services.add_reminder(user_plant, type_=d["type"], interval_days=d["every"], time_of_day=d["time"] or time(8))
    return _plant_response(user, user_plant.pk, "Reminder added")


@login_required
@require_POST
def set_reminder_flag(request, reminder_id):
    user = request.user
    reminder = selectors.get_reminder(user, reminder_id)
    form = ReminderFlagForm(request.POST)
    if not form.is_valid():
        return _invalid(form)
    services.set_reminder_flag(reminder, form.cleaned_data["flag"], form.cleaned_data["value"])
    return _plant_response(user, reminder.user_plant_id)
