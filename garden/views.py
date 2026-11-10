from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from greenhand import mock_data as data
from greenhand.users import current_user
from notifications import services as notification_services
from plants.selectors import catalog_by_slug
from weather import services as weather_services

from . import selectors, services
from .forms import (CareLogForm, HarvestForm, ProblemForm, ProblemStatusForm, ReminderFlagForm, ReminderForm,
                    StartGrowingForm, StatusForm, TimelineForm)
from .models import UserPlant


@login_required
def dashboard(request):
    user = current_user(request)
    notification_services.sync_weather(user)     # may skip today's watering after rain, so run it before reading tasks
    plants = selectors.garden(user)
    catalog = catalog_by_slug()
    featured = selectors.featured(plants)
    weather = weather_services.weather_for(user)
    same_plant_slugs = {p["plant_slug"] for p in plants}
    community = [
        {**p, "author_info": data.AUTHORS[p["author"]], "type_info": data.POST_TYPES[p["post_type"]],
         "plant_name": catalog[p["plant_slug"]]["common_name"] if p["plant_slug"] in catalog else ""}
        for p in data.POSTS if p["plant_slug"] in same_plant_slugs and p["author"] != data.USER["username"]
    ][:2]
    return render(request, "garden/dashboard.html", {
        "stats": selectors.stats(plants),
        "plant_rows": selectors.dashboard_rows(plants, catalog),
        "tasks": selectors.tasks(plants),
        "alerts": {a["alert_type"]: a for a in selectors.weather_alerts(weather, plants, catalog)},
        "weather": weather,
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
            "events": selectors.calendar_events(plants, weather),
        },
    })

@login_required
def my_garden(request):
    user = current_user(request)
    payload = {**selectors.garden_payload(user), "api": reverse("garden:dashboard"),
               "communityUrl": reverse("community:feed")}
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


@require_POST
def add_plant(request):
    """Start Growing from the My Garden "Add plant" dialog (FR-13)."""
    user = current_user(request)
    form = StartGrowingForm(request.POST)
    if not form.is_valid():
        return _invalid(form)
    d = form.cleaned_data
    user_plant = services.start_growing(user, d["plant"], nickname=d["nickname"].strip(), planted_on=d["planted_on"],
                                        start_method=d["start_method"], setting=d["setting"],
                                        container_type=d["container"].strip(), quantity=d["quantity"] or 1)
    return _plant_response(user, user_plant.pk, f"{user_plant.nickname} added · watering every "
                                                f"{user_plant.watering_interval_days} days", status=201)


@require_POST
def add_timeline_entry(request, user_plant_id):
    user = current_user(request)
    user_plant = selectors.get_user_plant(user, user_plant_id)
    form = TimelineForm(request.POST, request.FILES)
    if not form.is_valid():
        return _invalid(form)
    d = form.cleaned_data
    new_status = services.add_timeline_entry(user_plant, stage=d["stage"], recorded_on=d["date"], note=d["note"].strip(),
                                             photo=d["photo"], update_status=d["update_status"])
    return _plant_response(user, user_plant.pk, f"Entry added · status now {new_status}" if new_status else "Timeline entry added")


@require_POST
def log_care(request, user_plant_id):
    user = current_user(request)
    user_plant = selectors.get_user_plant(user, user_plant_id)
    form = CareLogForm(request.POST)
    if not form.is_valid():
        return _invalid(form)
    d = form.cleaned_data
    log = services.log_care(user_plant, action=d["action"], performed_on=d["date"], amount=d["amount"].strip(),
                            note=d["note"].strip())
    return _plant_response(user, user_plant.pk, f"{log.get_action_display()} logged for {user_plant.nickname}")


@require_POST
def log_problem(request, user_plant_id):
    user = current_user(request)
    user_plant = selectors.get_user_plant(user, user_plant_id)
    form = ProblemForm(request.POST, request.FILES)
    if not form.is_valid():
        return _invalid(form)
    d = form.cleaned_data
    services.log_problem(user_plant, title=d["title"].strip(), description=d["description"].strip(),
                         category=d["category"], severity=d["severity"], photo=d["photo"])
    return _plant_response(user, user_plant.pk, "Problem logged · follow-up reminder set for 3 days")


@require_POST
def set_problem_status(request, problem_id):
    user = current_user(request)
    problem = selectors.get_problem(user, problem_id)
    form = ProblemStatusForm(request.POST)
    if not form.is_valid():
        return _invalid(form)
    services.set_problem_status(problem, form.cleaned_data["status"], form.cleaned_data["resolution_note"].strip())
    return _plant_response(user, problem.user_plant_id, f"Problem marked {problem.get_status_display().lower()}")


@require_POST
def log_harvest(request, user_plant_id):
    user = current_user(request)
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


@require_POST
def change_status(request, user_plant_id):
    user = current_user(request)
    user_plant = selectors.get_user_plant(user, user_plant_id)
    form = StatusForm(request.POST)
    if not form.is_valid():
        return _invalid(form)

    def action():
        services.change_status(user_plant, form.cleaned_data["status"], form.cleaned_data["failure_reason"])
        return f"Status changed to {user_plant.get_status_display()}"
    return _run(user, user_plant.pk, action)


@require_POST
def add_reminder(request, user_plant_id):
    user = current_user(request)
    user_plant = selectors.get_user_plant(user, user_plant_id)
    form = ReminderForm(request.POST)
    if not form.is_valid():
        return _invalid(form)
    d = form.cleaned_data
    services.add_reminder(user_plant, type_=d["type"], interval_days=d["every"], time=d["time"] or "08:00")
    return _plant_response(user, user_plant.pk, "Reminder added")


@require_POST
def set_reminder_flag(request, reminder_id):
    user = current_user(request)
    reminder = selectors.get_reminder(user, reminder_id)
    form = ReminderFlagForm(request.POST)
    if not form.is_valid():
        return _invalid(form)
    services.set_reminder_flag(reminder, form.cleaned_data["flag"], form.cleaned_data["value"])
    return _plant_response(user, reminder.user_plant_id)


@require_POST
def complete_reminder(request, reminder_id):
    """One-tap Done on a dashboard task (FR-24)."""
    user = current_user(request)
    reminder = selectors.get_reminder(user, reminder_id)
    services.complete_reminder(reminder)
    return _plant_response(user, reminder.user_plant_id, f"Done: {reminder.title}")


@require_POST
def unskip_reminder(request, reminder_id):
    """"Water anyway": put today's rain-skipped watering back (FR-41 override)."""
    user = current_user(request)
    reminder = selectors.get_reminder(user, reminder_id)
    return _run(user, reminder.user_plant_id, lambda: services.undo_rain_skip(reminder) or "Watering added back for today")

