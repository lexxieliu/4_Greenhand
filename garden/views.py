from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from calendar_app.models import ReminderOccurrence
from calendar_app.selectors import calendar_payload
from greenhand import mock_data as data
from weather.selectors import active_alerts, weather_cards

from . import services
from .models import Garden


@login_required
def dashboard(request):
    cards = weather_cards(request.user)
    card = cards[0] if cards else None
    snapshot = card["snapshot"] if card else None
    live_alerts = list(active_alerts(request.user))
    badge_map = {}
    for alert in sorted(
        live_alerts,
        key=lambda item: {"frost": 0, "heat": 1, "rain_skip": 2}.get(
            item.alert_type, 3
        ),
    ):
        badge_map.setdefault(alert.user_plant_id, alert)
    rows = []
    for plant in Garden.objects.filter(user=request.user).select_related("plant"):
        alert = badge_map.get(plant.pk)
        rows.append(
            {
                "id": plant.pk,
                "nickname": plant.plant.plant_name,
                "icon": "i-sprout",
                "grad": "from-lime-100 to-emerald-100",
                "sub": alert.message if alert else plant.progress,
                "sub_cls": "text-leaf",
                "value": "",
                "badge": {
                    "icon": {
                        "frost": "i-snow",
                        "rain_skip": "i-rain",
                        "heat": "i-sun",
                    }.get(alert.alert_type if alert else "", "i-check"),
                    "cls": "bg-leaf-soft text-forest",
                    "title": alert.alert_type if alert else "No active weather alerts",
                },
                "attention": bool(alert),
                "search": plant.plant.plant_name.lower(),
            }
        )
    live_weather = {
        "location": card["location"].label if card else "Location not set",
        "updated": snapshot.fetched_at if snapshot else "Unavailable",
        "daily": [
            {**day, "day_short": day["date"].strftime("%a"), "icon": "i-cloud"}
            for day in card["daily"]
        ]
        if card
        else [],
        "current": {
            "temp_c": snapshot.current_temp_c,
            "icon": "i-cloud",
            "condition": "Cached" if card["stale"] else "Current conditions",
            "rain_last_24h_mm": snapshot.rain_last_24h_mm,
            "precip_prob_next_12h": snapshot.precip_prob_next_12h,
            "min_temp_next_48h_c": snapshot.min_temp_next_48h_c,
            "high": snapshot.max_temp_next_48h_c,
            "low": snapshot.min_temp_next_48h_c,
        }
        if snapshot
        else None,
    }

    featured = next(p for p in data.GARDEN if p["id"] == "tomato")
    same_plant_slugs = {p["plant_slug"] for p in data.GARDEN}
    community = [
        {
            **p,
            "author_info": data.AUTHORS[p["author"]],
            "type_info": data.POST_TYPES[p["post_type"]],
            "plant_name": data.CATALOG_BY_SLUG[p["plant_slug"]]["common_name"],
        }
        for p in data.POSTS
        if p["plant_slug"] in same_plant_slugs and p["author"] != data.USER["username"]
    ][:2]
    return render(
        request,
        "garden/dashboard.html",
        {
            "stats": services.stats(),
            "plant_rows": rows,
            "tasks": ReminderOccurrence.objects.filter(
                reminder__user=request.user, due_at__date=timezone.localdate()
            ).select_related("reminder"),
            "live_alerts": live_alerts,
            "weather": live_weather,
            "tips": data.TUTOR_WEEKLY_TIPS,
            "activity": data.ACTIVITY,
            "community": community,
            "featured": {**featured, "day": services.day_count(featured)},
            "care_actions": services.CARE_ACTIONS,
            "log_plants": [
                p
                for p in data.GARDEN
                if p["status"] not in ("planned", "failed", "archived")
            ],
            "dashboard_data": {
                "care": data.CARE_CHART,
                "height": data.TOMATO_HEIGHT,
                "events": calendar_payload(request.user),
            },
        },
    )


def my_garden(request):
    return render(
        request,
        "garden/my_garden.html",
        {
            "stats": services.stats(),
            "garden_data": services.garden_payload(),
        },
    )
