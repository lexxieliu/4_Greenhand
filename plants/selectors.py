"""Read queries for the plant catalog.

catalog() returns plain dicts in the shape the templates, the My Garden script, the tutor and the
community feed already use (the former mock_data.CATALOG), built from the Plant table.
"""
from greenhand import mock_data

from .models import Plant

# Card icon and gradient by category (display only, so not stored per plant)
STYLE = {
    "herb": ("i-leaf", "from-lime-200 to-emerald-300 text-forest"),
    "leafy_green": ("i-leaf", "from-emerald-100 to-green-300 text-forest"),
    "vegetable": ("i-sprout", "from-lime-100 to-emerald-200 text-forest"),
    "fruit": ("i-apple", "from-orange-200 to-red-300 text-red-800"),
    "root": ("i-sprout", "from-orange-100 to-amber-300 text-orange-800"),
    "legume": ("i-seed", "from-lime-100 to-green-300 text-forest"),
}


def user_zone():
    """Hardiness zone used for suitability. From the profile's location once Area 1 lands."""
    return mock_data.LOCATION["hardiness_zone"]


def _float(value):
    return float(value) if value is not None else None


def plant_dict(plant, zone=None):
    icon, grad = STYLE[plant.category]
    return {
        "id": plant.plant_id,
        "published": plant.is_published,
        "slug": plant.slug,
        "common_name": plant.common_name,
        "scientific_name": plant.scientific_name,
        "category": plant.category,
        "difficulty": plant.difficulty,
        "description": plant.description,
        "sunlight_requirement": plant.sunlight_requirement,
        "watering_interval_days": plant.watering_interval_days,
        "min_temp_c": _float(plant.min_temp_c),
        "max_temp_c": _float(plant.max_temp_c),
        "frost_tolerant": plant.frost_tolerant,
        "frost_threshold_c": _float(plant.frost_threshold_c),
        "days_to_germination": [plant.days_to_germination_min, plant.days_to_germination_max],
        "days_to_harvest": [plant.days_to_harvest_min, plant.days_to_harvest_max],
        "spacing_cm": plant.spacing_cm,
        "container_friendly": plant.container_friendly,
        "indoor_friendly": plant.indoor_friendly,
        "harvest_mode": plant.harvest_mode,
        "planting_months": plant.planting_months.get(zone or user_zone(), []),
        "care": plant.care_tips,
        "problems": [
            {"name": p.problem_name, "symptoms": p.symptoms, "solution": p.solution, "source_count": p.source_count}
            for p in plant.problem_summaries.all()
        ],
        "icon": icon,
        "grad": grad,
    }


def published_plants():
    return Plant.objects.filter(is_published=True).prefetch_related("problem_summaries")


def catalog():
    zone = user_zone()
    return [plant_dict(p, zone) for p in published_plants()]


def catalog_by_slug():
    """Every plant by slug, unpublished ones included, so plants already in a garden always resolve."""
    zone = user_zone()
    return {p.slug: plant_dict(p, zone) for p in Plant.objects.prefetch_related("problem_summaries")}


def get_plant(slug):
    """The published Plant with this slug, or None."""
    return published_plants().filter(slug=slug).first()
