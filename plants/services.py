"""
Plant database helpers: labels, suitability (PRD 3.2 / FR-12) and catalog filtering (FR-10).
Suitability uses the user's hardiness zone (via the plant's planting_months for that zone), the
current month and whether the plant can grow indoors or in containers.
"""
import calendar

from greenhand.clock import today

from . import selectors

CATEGORIES = {
    "herb": "Herbs", "leafy_green": "Leafy greens", "vegetable": "Vegetables",
    "fruit": "Fruits", "root": "Roots", "legume": "Legumes",
}
DIFFICULTY = {"easy": "Beginner-friendly", "medium": "Some experience", "hard": "Challenging"}
SUNLIGHT = {"full_sun": "Full sun", "partial": "Partial sun", "shade": "Shade"}
SEASONS = {"spring": [3, 4, 5], "summer": [6, 7, 8], "fall": [9, 10, 11], "winter": [12, 1, 2]}

SUITABILITY = {
    "great": {"label": "Great for you now", "cls": "bg-emerald-100 text-emerald-800", "icon": "i-check-circle"},
    "care": {"label": "Possible with care", "cls": "bg-amber-100 text-amber-800", "icon": "i-alert"},
    "no": {"label": "Not recommended now", "cls": "bg-rose-100 text-rose-700", "icon": "i-x-circle"},
}


def suitability(plant, month=None):
    """plant is a catalog dict; planting_months are already for the user's zone."""
    month = month or today().month
    months = plant["planting_months"]
    if not months and plant["indoor_friendly"]:
        level, reason = "great", "Grows indoors all year"
    elif month in months:
        level, reason = "great", f"Ideal planting time in zone {selectors.user_zone()}"
    elif plant["indoor_friendly"]:
        level, reason = "care", "Out of season outside — grow it indoors on a sunny sill"
    else:
        upcoming = sorted(months, key=lambda m: (m - month) % 12)
        level, reason = "no", f"Best planted in {calendar.month_name[upcoming[0]]}" if upcoming else "Not suited to your climate"
    return {"level": level, "reason": reason, **SUITABILITY[level]}


def _timeline_pct(plant):
    """Seed-to-harvest bar segments as % of the longest harvest day."""
    germination = plant["days_to_germination"][1] or 0
    harvest_min, harvest_max = plant["days_to_harvest"]
    if not harvest_max:
        return {"germination": 0, "growing": 100, "harvest": 0}
    harvest_min = harvest_min or harvest_max
    return {
        "germination": round(germination / harvest_max * 100),
        "growing": round((harvest_min - germination) / harvest_max * 100),
        "harvest": round((harvest_max - harvest_min) / harvest_max * 100),
    }


def enrich(plant, in_garden=()):
    """Add display fields used by the templates. in_garden: nicknames of the user's plants of this species."""
    months = plant["planting_months"]
    current = today().month
    return {
        **plant,
        "suitability": suitability(plant),
        "category_label": CATEGORIES[plant["category"]],
        "difficulty_label": DIFFICULTY[plant["difficulty"]],
        "sunlight_label": SUNLIGHT[plant["sunlight_requirement"]],
        "seasons": [s for s, ms in SEASONS.items() if set(ms) & set(months)] or ["all year"],
        "months": [
            {"abbr": calendar.month_abbr[m][0], "name": calendar.month_name[m], "plant": (m in months) or not months, "current": m == current}
            for m in range(1, 13)
        ],
        "in_garden": list(in_garden),
        "timeline_pct": _timeline_pct(plant),
    }


def filter_catalog(params, in_garden_by_slug):
    """Apply the GET filters from the Pick a Plant page (FR-10) and sort by suitability."""
    plants = [enrich(p, in_garden_by_slug.get(p["slug"], ())) for p in selectors.catalog()]
    q = params.get("q", "").strip().lower()
    if q:
        plants = [p for p in plants if q in p["common_name"].lower() or q in p["scientific_name"].lower()]
    if params.get("category") in CATEGORIES:
        plants = [p for p in plants if p["category"] == params["category"]]
    if params.get("difficulty") in DIFFICULTY:
        plants = [p for p in plants if p["difficulty"] == params["difficulty"]]
    if params.get("season") in SEASONS:
        season = SEASONS[params["season"]]
        plants = [p for p in plants if set(season) & set(p["planting_months"]) or not p["planting_months"]]
    if params.get("container"):
        plants = [p for p in plants if p["container_friendly"]]
    if params.get("indoor"):
        plants = [p for p in plants if p["indoor_friendly"]]
    if params.get("suitable"):
        plants = [p for p in plants if p["suitability"]["level"] == "great"]
    order = {"great": 0, "care": 1, "no": 2}
    return sorted(plants, key=lambda p: (order[p["suitability"]["level"]], p["common_name"]))
