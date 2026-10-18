from datetime import date

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from greenhand import mock_data as data

from . import services


def plant_list(request):
    params = request.GET
    plants = services.filter_catalog(params)
    active_filters = any(params.get(k) for k in ("q", "category", "difficulty", "season", "container", "indoor", "suitable"))
    return render(request, "plants/plant_list.html", {
        "plants": plants,
        "total": len(data.CATALOG),
        "great_count": sum(1 for p in services.catalog() if p["suitability"]["level"] == "great"),
        "filters": {k: params.get(k, "") for k in ("q", "category", "difficulty", "season", "container", "indoor", "suitable")},
        "active_filters": active_filters,
        "categories": services.CATEGORIES,
        "difficulties": services.DIFFICULTY,
        "seasons": list(services.SEASONS),
    })


def plant_detail(request, slug):
    if slug not in data.CATALOG_BY_SLUG:
        raise Http404("Plant not found")
    plant = services.enrich(data.CATALOG_BY_SLUG[slug])
    related = [p for p in services.catalog() if p["category"] == plant["category"] and p["slug"] != slug][:3]
    posts = [p for p in data.POSTS if p["plant_slug"] == slug][:2]
    return render(request, "plants/plant_detail.html", {
        "plant": plant,
        "related": related,
        "posts": [{**p, "author_info": data.AUTHORS[p["author"]], "type_info": data.POST_TYPES[p["post_type"]]} for p in posts],
        "today": data.TODAY,
    })


@require_POST
def start_growing(request, slug):
    """FR-13: add the plant to My Garden. The preview appends to the in-memory garden."""
    plant = data.CATALOG_BY_SLUG.get(slug)
    if not plant:
        raise Http404("Plant not found")
    try:
        planted_on = date.fromisoformat(request.POST.get("planted_on", ""))
    except ValueError:
        messages.error(request, "Please choose a valid planting date.")
        return redirect("plants:detail", slug=slug)
    method = request.POST.get("start_method") if request.POST.get("start_method") in ("seed", "seedling", "cutting") else "seed"
    setting = request.POST.get("setting") if request.POST.get("setting") in ("outdoor", "indoor", "greenhouse") else "outdoor"
    nickname = (request.POST.get("nickname") or plant["common_name"]).strip()[:60]
    future = planted_on > data.TODAY
    new_id = f"{slug}-{len(data.GARDEN) + 1}"
    data.GARDEN.insert(0, {
        "id": new_id, "type": slug, "plant_slug": slug, "nickname": nickname, "variety": "",
        "planted_on": planted_on.isoformat(), "start_method": method, "setting": setting,
        "container": request.POST.get("container", "").strip()[:50], "quantity": max(1, int(request.POST.get("quantity") or 1)),
        "status": "planned" if future else ("sprouting" if method == "seed" else "growing"),
        "watering_interval_days": plant["watering_interval_days"],
        "tip": f"Your tutor will tailor tips for {nickname} as you log its progress.",
        "timeline": [] if future else [{"id": f"t-{new_id}", "stage": "seed" if method == "seed" else "seedling", "date": planted_on.isoformat(), "note": f"{'Sowed' if method == 'seed' else 'Planted'} {nickname}.", "photo": False}],
        "care": [], "problems": [], "harvests": [],
        "reminders": [{"id": f"r-{new_id}", "type": "water", "title": f"Water {nickname}", "every": plant["watering_interval_days"], "time": "08:00",
                       "weather_aware": setting == "outdoor", "active": True, "inapp": True, "email": True,
                       "next_due": planted_on.isoformat() if future else data.TODAY.isoformat(), "history": []}],
    })
    messages.success(request, f"{nickname} added to My Garden · watering every {plant['watering_interval_days']} days")
    return redirect(f"{reverse('garden:my_garden')}#plant={new_id}")
