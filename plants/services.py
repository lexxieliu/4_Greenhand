"""
Plant database helpers: labels, suitability (PRD 3.2 / FR-12) and catalog filtering (FR-10).
Suitability uses the user's hardiness zone (via planting_months for zone 5b), the current
month and whether the plant can grow indoors or in containers.
"""
import calendar

from greenhand import mock_data as data

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
    month = month or data.TODAY.month
    months = plant["planting_months"]
    if not months and plant["indoor_friendly"]:
        level, reason = "great", "Grows indoors all year"
    elif month in months:
        level, reason = "great", f"Ideal planting time in zone {data.LOCATION['hardiness_zone']}"
    elif plant["indoor_friendly"]:
        level, reason = "care", "Out of season outside — grow it indoors on a sunny sill"
    else:
        upcoming = sorted(months, key=lambda m: (m - month) % 12)
        level, reason = "no", f"Best planted in {calendar.month_name[upcoming[0]]}" if upcoming else "Not suited to your climate"
    return {"level": level, "reason": reason, **SUITABILITY[level]}


def enrich(plant):
    """Add display fields used by the templates."""
    in_garden = [g["nickname"] for g in data.GARDEN if g["plant_slug"] == plant["slug"] and g["status"] not in ("failed", "archived")]
    months = plant["planting_months"]
    g1, (h0, h1) = plant["days_to_germination"][1], plant["days_to_harvest"]
    return {
        **plant,
        "suitability": suitability(plant),
        "category_label": CATEGORIES[plant["category"]],
        "difficulty_label": DIFFICULTY[plant["difficulty"]],
        "sunlight_label": SUNLIGHT[plant["sunlight_requirement"]],
        "seasons": [s for s, ms in SEASONS.items() if set(ms) & set(months)] or ["all year"],
        "months": [
            {"abbr": calendar.month_abbr[m][0], "name": calendar.month_name[m], "plant": (m in months) or not months, "current": m == data.TODAY.month}
            for m in range(1, 13)
        ],
        "in_garden": in_garden,
        # Seed-to-harvest bar segments as % of the longest harvest day
        "timeline_pct": {"germination": round(g1 / h1 * 100), "growing": round((h0 - g1) / h1 * 100), "harvest": round((h1 - h0) / h1 * 100)},
    }


def catalog():
    return [enrich(p) for p in data.CATALOG]


def filter_catalog(params):
    """Apply the GET filters from the Pick a Plant page."""
    plants = catalog()
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
