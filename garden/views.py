from django.shortcuts import render
from greenhand import mock_data as data
from . import services

def dashboard(request):
    featured = next(p for p in data.GARDEN if p["id"] == "tomato")
    same_plant_slugs = {p["plant_slug"] for p in data.GARDEN}
    community = [
        {**p, "author_info": data.AUTHORS[p["author"]], "type_info": data.POST_TYPES[p["post_type"]], "plant_name": data.CATALOG_BY_SLUG[p["plant_slug"]]["common_name"]}
        for p in data.POSTS if p["plant_slug"] in same_plant_slugs and p["author"] != data.USER["username"]
    ][:2]
    return render(request, "garden/dashboard.html", {
        "stats": services.stats(),
        "plants_rows": services.dashboard_rows(),
        "tasks": data.TASKS,
        "alerts": {a["alert_type"]: a for a in data.WEATHER_ALERTS},
        "weather": data.WEATHER,
        "tips": data.TUTOR_WEEKLY_TIPS,
        "activity": data.ACTIVITY,
        "community": community,
        "featured": {**featured, "day": services.day_count(featured)},
        "care_actions": services.CARE_ACTIONS,
        "log_plants": [p for p in data.GARDEN if p["status"] not in ("planned", "failed", "archived")],
        "dashboard_data": {
            "care": data.CARE_CHART,
            "height": data.TOMATO_HEIGHT,
            "events": services.calendar_events(),
        },
    })

def my_garden(request):
    return render(request, "garden/my_garden.html", {
        "stats": services.stats(),
        "garden_data": services.garden_payload(),
    })