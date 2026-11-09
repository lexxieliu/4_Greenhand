from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from garden import services as garden_services
from garden.forms import StartGrowingForm
from garden.selectors import in_garden_by_slug
from greenhand import mock_data as data
from greenhand.clock import today
from greenhand.users import current_user

from . import selectors, services

FILTERS = ("q", "category", "difficulty", "season", "container", "indoor", "suitable")


def plant_list(request):
    params = request.GET
    plants = services.filter_catalog(params, in_garden_by_slug(current_user(request)))
    all_plants = [services.enrich(p) for p in selectors.catalog()]
    return render(request, "plants/plant_list.html", {
        "plants": plants,
        "total": len(all_plants),
        "great_count": sum(1 for p in all_plants if p["suitability"]["level"] == "great"),
        "filters": {k: params.get(k, "") for k in FILTERS},
        "active_filters": any(params.get(k) for k in FILTERS),
        "categories": services.CATEGORIES,
        "difficulties": services.DIFFICULTY,
        "seasons": list(services.SEASONS),
    })


def plant_detail(request, slug):
    plant = selectors.get_plant(slug)
    if not plant:
        raise Http404("Plant not found")
    in_garden = in_garden_by_slug(current_user(request))
    plant = services.enrich(selectors.plant_dict(plant), in_garden.get(slug, ()))
    related = [services.enrich(p) for p in selectors.catalog() if p["category"] == plant["category"] and p["slug"] != slug][:3]
    posts = [p for p in data.POSTS if p["plant_slug"] == slug][:2]
    return render(request, "plants/plant_detail.html", {
        "plant": plant,
        "related": related,
        "posts": [{**p, "author_info": data.AUTHORS[p["author"]], "type_info": data.POST_TYPES[p["post_type"]]} for p in posts],
        "today": today(),
    })


@require_POST
def start_growing(request, slug):
    """FR-13: add the plant to My Garden with an automatic care schedule (garden.services.start_growing)."""
    form = StartGrowingForm({**request.POST.dict(), "plant": slug})
    if not form.is_valid():
        if "plant" in form.errors:
            raise Http404("Plant not found")
        messages.error(request, next(iter(form.errors.values()))[0])
        return redirect(f"{reverse('plants:detail', args=[slug])}#start")
    d = form.cleaned_data
    user_plant = garden_services.start_growing(
        current_user(request), d["plant"], nickname=d["nickname"].strip(), planted_on=d["planted_on"],
        start_method=d["start_method"], setting=d["setting"], container_type=d["container"].strip(),
        quantity=d["quantity"] or 1,
    )
    messages.success(request, f"{user_plant.nickname} added to My Garden · watering every "
                              f"{user_plant.watering_interval_days} days")
    return redirect(f"{reverse('garden:my_garden')}#plant={user_plant.pk}")
