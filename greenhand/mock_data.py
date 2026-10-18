"""
Mock data for the Greenhand front-end preview.

Every view reads from here so the templates can be rendered without a database.
Field names follow the PRD schema (section 7) so each block maps onto a model later:

    USER / LOCATION      -> accounts.Profile, accounts.GrowingLocation
    CATALOG              -> plants.Plant (+ PlantProblemSummary)
    GARDEN               -> garden.UserPlant (+ TimelineEntry, CareLog, Problem/Diagnosis, Harvest)
                            and calendar_app.Reminder (+ ReminderOccurrence)
    WEATHER              -> weather.WeatherSnapshot, weather.WeatherAlert
    POSTS                -> community.Post, PostImage, Comment, PostLike, PostSave
    NOTIFICATIONS        -> notifications.Notification

The data is written relative to TODAY. Lists are mutated in memory by the demo POST views,
so new posts/comments persist until the dev server restarts.
"""
from datetime import date, datetime, timedelta

TODAY = date(2026, 10, 13)

# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------
USER = {
    "display_name": "Maya",
    "username": "balcony_maya",
    "initial": "M",
    "experience_level": "Beginner",
    "space_type": "Balcony",
    "sunlight_level": "Partial sun",
}

LOCATION = {"city": "Chicago", "region": "IL", "hardiness_zone": "5b", "label": "Chicago, IL"}

TUTOR_USAGE = {"used": 12, "limit": 50}

NOTIFICATIONS = [
    {"icon": "i-snow", "tint": "bg-indigo-100 text-indigo-700", "title": "Frost risk Thursday night (1 °C)", "body": "Protect your cherry tomato · 2h ago", "unread": True},
    {"icon": "i-rain", "tint": "bg-sky-100 text-sky-700", "title": "Rain did the watering today", "body": "Balcony Basil reminder skipped · 6h ago", "unread": True},
    {"icon": "i-post", "tint": "bg-mist text-forest", "title": "windowsill_sprouts commented", "body": "“Those look amazing! What fertilizer…” · 1d ago", "unread": True},
    {"icon": "i-heart", "tint": "bg-rose-100 text-rose-600", "title": "12 people liked your harvest post", "body": "Mint, 80 g · 2d ago", "unread": False},
    {"icon": "i-sparkles", "tint": "bg-lime-100 text-forest", "title": "Your weekly garden digest is ready", "body": "3 plants growing, 1 harvest · 6d ago", "unread": False},
]

# ---------------------------------------------------------------------------
# Weather (Open-Meteo snapshot for the user's rounded location)
# ---------------------------------------------------------------------------
FROST_THRESHOLD_C = 2
RAIN_SKIP_MM = 5
RAIN_SKIP_PROB = 70


def _daily(offset, icon, condition, high, low, precip_mm, prob):
    d = TODAY + timedelta(days=offset)
    return {
        "date": d.isoformat(),
        "day_short": "Today" if offset == 0 else d.strftime("%a"),
        "day_long": f"{d:%A, %b} {d.day}",
        "icon": icon,
        "condition": condition,
        "high": high,
        "low": low,
        "precip_mm": precip_mm,
        "precip_prob": prob,
        "frost": low <= FROST_THRESHOLD_C,
    }


DAILY_FORECAST = [
    _daily(0, "i-rain", "Light rain", 14, 8, 6.0, 90),
    _daily(1, "i-cloud", "Cloudy", 12, 5, 0.4, 20),
    _daily(2, "i-snow", "Clear, frosty night", 9, 1, 0.0, 5),
    _daily(3, "i-sun", "Sunny", 13, 4, 0.0, 0),
    _daily(4, "i-sun", "Sunny", 16, 7, 0.0, 0),
    _daily(5, "i-cloud", "Partly cloudy", 15, 9, 0.2, 10),
    _daily(6, "i-rain", "Rain", 13, 8, 8.0, 70),
]


def _hourly():
    """3-hourly points for the next 72 hours. Each day's high falls at 3 PM and its low is the
    overnight low (6 AM the next morning), so "Thursday's low" is Thursday night's frost."""
    midnight = datetime(TODAY.year, TODAY.month, TODAY.day)
    anchors = [(midnight + timedelta(hours=6), 9)]
    for i, day in enumerate(DAILY_FORECAST):
        base = midnight + timedelta(days=i)
        anchors += [(base + timedelta(hours=15), day["high"]), (base + timedelta(hours=30), day["low"])]
    rain_by_step = [1.2, 0.8, 0.4, 0.2, 0, 0, 0, 0.1, 0.1, 0.2] + [0] * 15
    start = datetime(TODAY.year, TODAY.month, TODAY.day, 12)
    points = []
    for i in range(25):
        t = start + timedelta(hours=3 * i)
        (t0, v0), (t1, v1) = next((a, b) for a, b in zip(anchors, anchors[1:]) if a[0] <= t <= b[0])
        temp = v0 + (v1 - v0) * (t - t0) / (t1 - t0)
        hour = t.strftime("%I").lstrip("0") + " " + t.strftime("%p")
        points.append({
            "iso": t.isoformat(),
            "label": {"12 PM": "Noon", "12 AM": "Midnight"}.get(hour, hour),
            "day": "Today" if t.date() == TODAY else t.strftime("%a"),
            "temp": round(temp, 1),
            "precip_mm": rain_by_step[i],
        })
    return points


WEATHER = {
    "location": "Chicago, IL",
    "updated": "40 min ago",
    "provider": "Open-Meteo",
    "current": {
        "temp_c": 14, "feels_like": 12, "condition": "Light rain", "icon": "i-rain",
        "high": 14, "low": 8, "humidity": 82, "wind_kmh": 14, "uv": 1,
        "rain_last_24h_mm": 12, "precip_prob_next_12h": 40, "min_temp_next_48h_c": 1,
        "sunrise": "7:03 AM", "sunset": "6:16 PM",
    },
    "daily": DAILY_FORECAST,
    "hourly": _hourly(),
    "thresholds": {"frost_c": FROST_THRESHOLD_C, "rain_mm": RAIN_SKIP_MM, "rain_prob": RAIN_SKIP_PROB, "heat_c": 32},
}

WEATHER_ALERTS = [
    {
        "id": "frost-1015",
        "alert_type": "frost",
        "icon": "i-snow",
        "title": "Frost risk Thursday night — low of 1 °C",
        "message": "Frost-sensitive outdoor plants can be damaged below 2 °C.",
        "valid": "Thu, Oct 15 · 9 PM – 8 AM",
        "plants": ["Cherry Tomato ‘Sungold’", "Balcony Basil"],
        "actions": [
            "Water the soil Wednesday afternoon (moist soil holds heat)",
            "Cover plants with frost cloth or an old sheet at sunset",
            "Move pots against the wall or indoors",
            "Remove covers Friday morning once it’s above freezing",
        ],
    },
    {
        "id": "rain-1013",
        "alert_type": "rain_skip",
        "icon": "i-rain",
        "title": "Rain did the watering today",
        "message": "12 mm fell in the last 24h, so outdoor watering was skipped. Indoor plants are unaffected.",
        "valid": "Today",
        "plants": ["Balcony Basil"],
        "actions": [],
    },
]

# ---------------------------------------------------------------------------
# Plant database (plants.Plant). planting_months = outdoor sowing/planting months for zone 5b.
# ---------------------------------------------------------------------------
CATALOG = [
    {
        "slug": "basil", "common_name": "Basil", "scientific_name": "Ocimum basilicum", "category": "herb", "difficulty": "easy",
        "description": "Fragrant, fast-growing herb that loves warmth. A beginner favourite for sunny windowsills and balconies.",
        "sunlight_requirement": "full_sun", "watering_interval_days": 2, "min_temp_c": 10, "max_temp_c": 35,
        "frost_tolerant": False, "days_to_germination": [5, 10], "days_to_harvest": [60, 90], "spacing_cm": 25,
        "container_friendly": True, "indoor_friendly": True, "planting_months": [5, 6, 7],
        "icon": "i-leaf", "grad": "from-lime-200 to-emerald-300 text-forest",
        "care": ["Pinch the top pair of leaves every 2 weeks to keep it bushy", "Let the soil dry slightly between waterings", "Remove flower buds to keep leaves tender"],
        "problems": [
            {"name": "Yellow lower leaves", "symptoms": "Soft, yellowing older leaves", "solution": "Usually overwatering. Let the pot dry out and check drainage.", "source_count": 34},
            {"name": "Leggy stems", "symptoms": "Tall, thin stems with few leaves", "solution": "Not enough light. Move to the sunniest spot and pinch the tips.", "source_count": 21},
            {"name": "Black spots after cold nights", "symptoms": "Dark patches on leaves", "solution": "Chill damage below 10 °C. Bring indoors in autumn.", "source_count": 12},
        ],
    },
    {
        "slug": "cherry-tomato", "common_name": "Cherry tomato", "scientific_name": "Solanum lycopersicum", "category": "fruit", "difficulty": "medium",
        "description": "Sweet bite-sized tomatoes that crop heavily in containers. Needs warmth, sun, and support.",
        "sunlight_requirement": "full_sun", "watering_interval_days": 2, "min_temp_c": 10, "max_temp_c": 32,
        "frost_tolerant": False, "days_to_germination": [5, 10], "days_to_harvest": [57, 75], "spacing_cm": 45,
        "container_friendly": True, "indoor_friendly": False, "planting_months": [5, 6],
        "icon": "i-apple", "grad": "from-orange-200 to-red-300 text-red-800",
        "care": ["Stake or cage early", "Pinch side shoots (suckers) on vining types", "Water deeply and evenly to prevent split fruit"],
        "problems": [
            {"name": "Aphids on new growth", "symptoms": "Clusters of small insects, sticky leaves", "solution": "Spray with mild soapy water every 2–3 days.", "source_count": 28},
            {"name": "Blossom end rot", "symptoms": "Dark sunken patch at the base of fruit", "solution": "Uneven watering. Keep soil consistently moist and mulch.", "source_count": 19},
            {"name": "Split fruit", "symptoms": "Cracks after heavy rain", "solution": "Pick ripe fruit before storms; water evenly.", "source_count": 11},
        ],
    },
    {
        "slug": "lettuce", "common_name": "Lettuce", "scientific_name": "Lactuca sativa", "category": "leafy_green", "difficulty": "easy",
        "description": "Quick, cool-season salad leaves. Pick outer leaves and it keeps growing for weeks.",
        "sunlight_requirement": "partial", "watering_interval_days": 2, "min_temp_c": 2, "max_temp_c": 24,
        "frost_tolerant": True, "days_to_germination": [4, 10], "days_to_harvest": [45, 55], "spacing_cm": 20,
        "container_friendly": True, "indoor_friendly": True, "planting_months": [3, 4, 5, 8, 9, 10],
        "icon": "i-sprout", "grad": "from-green-100 to-lime-300 text-forest",
        "care": ["Keep soil evenly moist", "Thin seedlings to 15–20 cm apart", "Harvest outer leaves from 10 cm long"],
        "problems": [
            {"name": "Bolting", "symptoms": "Tall flower stalk, bitter leaves", "solution": "Heat stress. Grow in spring or fall and give afternoon shade.", "source_count": 25},
            {"name": "Slugs", "symptoms": "Ragged holes, slime trails", "solution": "Hand-pick at night; use copper tape on pots.", "source_count": 17},
        ],
    },
    {
        "slug": "mint", "common_name": "Mint", "scientific_name": "Mentha spicata", "category": "herb", "difficulty": "easy",
        "description": "Vigorous perennial herb for teas and drinks. Best kept in its own pot — it spreads!",
        "sunlight_requirement": "partial", "watering_interval_days": 3, "min_temp_c": -20, "max_temp_c": 32,
        "frost_tolerant": True, "days_to_germination": [10, 15], "days_to_harvest": [60, 90], "spacing_cm": 45,
        "container_friendly": True, "indoor_friendly": True, "planting_months": [4, 5, 6, 9],
        "icon": "i-leaf", "grad": "from-teal-100 to-emerald-200 text-emerald-800",
        "care": ["Grow in its own container", "Cut back by a third to encourage new growth", "Trim to 5 cm before winter"],
        "problems": [
            {"name": "Rust spots", "symptoms": "Orange pustules under leaves", "solution": "Remove affected stems and improve airflow.", "source_count": 9},
        ],
    },
    {
        "slug": "spinach", "common_name": "Spinach", "scientific_name": "Spinacia oleracea", "category": "leafy_green", "difficulty": "easy",
        "description": "Cold-hardy leafy green that thrives in cool autumn weather and shrugs off light frost.",
        "sunlight_requirement": "partial", "watering_interval_days": 2, "min_temp_c": -5, "max_temp_c": 24,
        "frost_tolerant": True, "days_to_germination": [7, 14], "days_to_harvest": [40, 50], "spacing_cm": 10,
        "container_friendly": True, "indoor_friendly": False, "planting_months": [3, 4, 9, 10],
        "icon": "i-leaf", "grad": "from-emerald-100 to-green-300 text-forest",
        "care": ["Sow 1 cm deep, 5 cm apart", "Keep evenly moist", "Pick outer leaves at 8–10 cm"],
        "problems": [
            {"name": "Bolting", "symptoms": "Flower stalks in warm weather", "solution": "Sow in early spring or late summer.", "source_count": 14},
            {"name": "Leaf miners", "symptoms": "Pale winding trails in leaves", "solution": "Remove affected leaves; cover with fleece.", "source_count": 6},
        ],
    },
    {
        "slug": "cilantro", "common_name": "Cilantro", "scientific_name": "Coriandrum sativum", "category": "herb", "difficulty": "medium",
        "description": "Bright, citrusy herb that prefers cool weather. Sow little and often.",
        "sunlight_requirement": "partial", "watering_interval_days": 2, "min_temp_c": -2, "max_temp_c": 27,
        "frost_tolerant": True, "days_to_germination": [7, 10], "days_to_harvest": [45, 70], "spacing_cm": 15,
        "container_friendly": True, "indoor_friendly": True, "planting_months": [3, 4, 5, 9, 10],
        "icon": "i-leaf", "grad": "from-lime-100 to-green-200 text-forest",
        "care": ["Sow every 3 weeks for a steady supply", "Give afternoon shade", "Harvest outer stems first"],
        "problems": [
            {"name": "Bolting in heat", "symptoms": "Feathery leaves and flowers", "solution": "Grow in spring or fall; it bolts above 27 °C.", "source_count": 31},
        ],
    },
    {
        "slug": "kale", "common_name": "Kale", "scientific_name": "Brassica oleracea", "category": "leafy_green", "difficulty": "easy",
        "description": "Tough, nutritious green that gets sweeter after a frost. Harvest leaves all season.",
        "sunlight_requirement": "full_sun", "watering_interval_days": 3, "min_temp_c": -10, "max_temp_c": 27,
        "frost_tolerant": True, "days_to_germination": [5, 8], "days_to_harvest": [50, 65], "spacing_cm": 40,
        "container_friendly": True, "indoor_friendly": False, "planting_months": [3, 4, 7, 8, 9, 10],
        "icon": "i-leaf", "grad": "from-emerald-200 to-teal-300 text-emerald-900",
        "care": ["Pick lower leaves first", "Feed monthly", "Net against cabbage worms"],
        "problems": [
            {"name": "Cabbage worms", "symptoms": "Green caterpillars, holes in leaves", "solution": "Hand-pick and cover with insect netting.", "source_count": 16},
        ],
    },
    {
        "slug": "radish", "common_name": "Radish", "scientific_name": "Raphanus sativus", "category": "root", "difficulty": "easy",
        "description": "The fastest crop in the garden — crunchy roots in about four weeks.",
        "sunlight_requirement": "full_sun", "watering_interval_days": 2, "min_temp_c": -2, "max_temp_c": 24,
        "frost_tolerant": True, "days_to_germination": [3, 7], "days_to_harvest": [25, 30], "spacing_cm": 5,
        "container_friendly": True, "indoor_friendly": False, "planting_months": [3, 4, 5, 8, 9, 10],
        "icon": "i-sprout", "grad": "from-pink-100 to-rose-300 text-rose-800",
        "care": ["Thin to 5 cm apart", "Keep moist for mild flavour", "Harvest promptly before they turn woody"],
        "problems": [
            {"name": "All leaves, no root", "symptoms": "Lush tops, thin roots", "solution": "Too crowded or too much nitrogen. Thin early.", "source_count": 13},
        ],
    },
    {
        "slug": "arugula", "common_name": "Arugula", "scientific_name": "Eruca vesicaria", "category": "leafy_green", "difficulty": "easy",
        "description": "Peppery salad leaf ready in weeks. Loves cool weather.",
        "sunlight_requirement": "partial", "watering_interval_days": 2, "min_temp_c": -2, "max_temp_c": 24,
        "frost_tolerant": True, "days_to_germination": [4, 7], "days_to_harvest": [30, 40], "spacing_cm": 10,
        "container_friendly": True, "indoor_friendly": True, "planting_months": [3, 4, 5, 8, 9, 10],
        "icon": "i-leaf", "grad": "from-lime-200 to-green-300 text-forest",
        "care": ["Cut leaves at 8 cm, it regrows", "Sow every 2–3 weeks"],
        "problems": [{"name": "Flea beetles", "symptoms": "Tiny shot holes", "solution": "Cover with fleece; keep soil moist.", "source_count": 8}],
    },
    {
        "slug": "green-onion", "common_name": "Green onion", "scientific_name": "Allium fistulosum", "category": "vegetable", "difficulty": "easy",
        "description": "Mild onion stalks you can regrow from kitchen scraps on a sunny sill.",
        "sunlight_requirement": "full_sun", "watering_interval_days": 3, "min_temp_c": -5, "max_temp_c": 30,
        "frost_tolerant": True, "days_to_germination": [7, 14], "days_to_harvest": [60, 70], "spacing_cm": 5,
        "container_friendly": True, "indoor_friendly": True, "planting_months": [3, 4, 5, 8, 9],
        "icon": "i-sprout", "grad": "from-lime-100 to-emerald-200 text-forest",
        "care": ["Snip from the top; leave 3 cm to regrow", "Change water every 2 days if regrowing in a jar"],
        "problems": [{"name": "Thrips", "symptoms": "Silvery streaks on leaves", "solution": "Rinse plants; use sticky traps.", "source_count": 5}],
    },
    {
        "slug": "microgreens", "common_name": "Microgreens", "scientific_name": "Mixed seed", "category": "leafy_green", "difficulty": "easy",
        "description": "Harvest-in-10-days greens grown in a tray indoors any time of year.",
        "sunlight_requirement": "partial", "watering_interval_days": 1, "min_temp_c": 15, "max_temp_c": 27,
        "frost_tolerant": False, "days_to_germination": [2, 4], "days_to_harvest": [10, 14], "spacing_cm": 1,
        "container_friendly": True, "indoor_friendly": True, "planting_months": [],
        "icon": "i-sprout", "grad": "from-green-100 to-emerald-300 text-forest",
        "care": ["Sow thickly on moist soil", "Mist twice a day", "Cut just above the soil when the first true leaves show"],
        "problems": [{"name": "Mould on the tray", "symptoms": "White fuzz at the base", "solution": "Improve airflow and water from below.", "source_count": 10}],
    },
    {
        "slug": "bush-beans", "common_name": "Bush beans", "scientific_name": "Phaseolus vulgaris", "category": "legume", "difficulty": "easy",
        "description": "Compact, productive beans that need no support. A summer crop.",
        "sunlight_requirement": "full_sun", "watering_interval_days": 2, "min_temp_c": 10, "max_temp_c": 32,
        "frost_tolerant": False, "days_to_germination": [7, 10], "days_to_harvest": [50, 60], "spacing_cm": 10,
        "container_friendly": True, "indoor_friendly": False, "planting_months": [5, 6, 7],
        "icon": "i-seed", "grad": "from-lime-100 to-green-300 text-forest",
        "care": ["Sow after the last frost", "Pick often to keep pods coming"],
        "problems": [{"name": "Bean beetles", "symptoms": "Lacy leaves", "solution": "Hand-pick adults and larvae.", "source_count": 7}],
    },
    {
        "slug": "chili-pepper", "common_name": "Chili pepper", "scientific_name": "Capsicum annuum", "category": "vegetable", "difficulty": "medium",
        "description": "Compact, colourful plants that thrive in pots. Needs a long warm season.",
        "sunlight_requirement": "full_sun", "watering_interval_days": 3, "min_temp_c": 12, "max_temp_c": 35,
        "frost_tolerant": False, "days_to_germination": [7, 21], "days_to_harvest": [70, 90], "spacing_cm": 40,
        "container_friendly": True, "indoor_friendly": True, "planting_months": [5, 6],
        "icon": "i-apple", "grad": "from-orange-100 to-red-300 text-red-800",
        "care": ["Start indoors 8 weeks before last frost", "Let soil dry slightly between waterings"],
        "problems": [{"name": "Flower drop", "symptoms": "Flowers fall without fruit", "solution": "Temperatures too high or low; shake to pollinate indoors.", "source_count": 9}],
    },
    {
        "slug": "strawberries", "common_name": "Strawberries", "scientific_name": "Fragaria × ananassa", "category": "fruit", "difficulty": "medium",
        "description": "Perennial berries for hanging baskets and pots. Plant in spring for summer fruit.",
        "sunlight_requirement": "full_sun", "watering_interval_days": 2, "min_temp_c": -15, "max_temp_c": 30,
        "frost_tolerant": True, "days_to_germination": [14, 28], "days_to_harvest": [60, 90], "spacing_cm": 30,
        "container_friendly": True, "indoor_friendly": False, "planting_months": [4, 5],
        "icon": "i-apple", "grad": "from-rose-100 to-pink-300 text-rose-800",
        "care": ["Plant crowns level with the soil", "Remove runners for bigger fruit", "Mulch with straw"],
        "problems": [{"name": "Grey mould", "symptoms": "Fuzzy grey berries", "solution": "Remove affected fruit; keep berries off the soil.", "source_count": 12}],
    },
    {
        "slug": "snap-peas", "common_name": "Snap peas", "scientific_name": "Pisum sativum", "category": "legume", "difficulty": "easy",
        "description": "Sweet, crunchy pods on climbing vines. One of the first crops of spring.",
        "sunlight_requirement": "full_sun", "watering_interval_days": 3, "min_temp_c": -2, "max_temp_c": 24,
        "frost_tolerant": True, "days_to_germination": [7, 14], "days_to_harvest": [60, 70], "spacing_cm": 5,
        "container_friendly": True, "indoor_friendly": False, "planting_months": [3, 4, 8],
        "icon": "i-seed", "grad": "from-green-100 to-lime-300 text-forest",
        "care": ["Give a trellis to climb", "Pick pods daily once they start"],
        "problems": [{"name": "Powdery mildew", "symptoms": "White powder on leaves", "solution": "Improve airflow; water at the base.", "source_count": 11}],
    },
    {
        "slug": "carrots", "common_name": "Carrots", "scientific_name": "Daucus carota", "category": "root", "difficulty": "medium",
        "description": "Sweet roots for deep containers. Short varieties suit balconies.",
        "sunlight_requirement": "full_sun", "watering_interval_days": 3, "min_temp_c": -2, "max_temp_c": 27,
        "frost_tolerant": True, "days_to_germination": [10, 21], "days_to_harvest": [60, 80], "spacing_cm": 5,
        "container_friendly": True, "indoor_friendly": False, "planting_months": [4, 5, 6, 7],
        "icon": "i-sprout", "grad": "from-orange-100 to-amber-300 text-orange-800",
        "care": ["Use a pot at least 30 cm deep", "Keep the surface moist until seedlings appear", "Thin to 5 cm apart"],
        "problems": [{"name": "Forked roots", "symptoms": "Split, twisted carrots", "solution": "Stony or compacted soil; use loose potting mix.", "source_count": 9}],
    },
]
CATALOG_BY_SLUG = {p["slug"]: p for p in CATALOG}

# ---------------------------------------------------------------------------
# My Garden (garden.UserPlant and related records). Dates are ISO strings so the
# same structure can be handed to the page script with |json_script.
# ---------------------------------------------------------------------------
GARDEN = [
    {
        "id": "basil", "type": "basil", "plant_slug": "basil", "nickname": "Balcony Basil", "variety": "Genovese",
        "planted_on": "2026-09-09", "start_method": "seedling", "setting": "outdoor", "container": "Pot · 20 cm", "quantity": 1,
        "status": "growing", "watering_interval_days": 2,
        "tip": "Pinch the top pair of leaves every couple of weeks to keep basil bushy, and let the pot dry out between waterings.",
        "timeline": [
            {"id": "t1", "stage": "seedling", "date": "2026-09-09", "note": "Transplanted a nursery seedling into a 20 cm pot on the balcony.", "photo": True},
            {"id": "t2", "stage": "vegetative", "date": "2026-09-24", "note": "Pinched the top above the third leaf pair. Already bushier.", "photo": True},
            {"id": "t3", "stage": "vegetative", "date": "2026-10-12", "note": "Lower leaves turning yellow and a bit soft.", "photo": True},
        ],
        "care": [
            {"action": "water", "amount": "300 ml", "note": "", "date": "2026-10-07", "source": "reminder"},
            {"action": "water", "amount": "300 ml", "note": "", "date": "2026-10-05", "source": "reminder"},
            {"action": "prune", "amount": "", "note": "Pinched the tops", "date": "2026-09-24", "source": "tutor_suggestion"},
            {"action": "fertilize", "amount": "5 ml/L", "note": "Half-strength liquid feed", "date": "2026-09-20", "source": "manual"},
        ],
        "problems": [
            {
                "id": "p1", "title": "Yellow lower leaves", "category": "watering", "severity": "medium", "status": "monitoring",
                "description": "The lowest leaves are turning yellow and feel soft. New growth at the top looks fine.",
                "opened": "2026-10-12", "photo": True,
                "diagnosis": {
                    "issues": [
                        {"name": "Overwatering", "confidence": "high", "reasoning": "You watered on Oct 5 and 7, then 12 mm of rain fell. Soft, yellow lower leaves usually mean roots are sitting in wet soil."},
                        {"name": "Nitrogen deficiency", "confidence": "low", "reasoning": "Possible if the yellowing keeps moving up the plant after the soil dries."},
                    ],
                    "immediate_actions": ["Skip watering until the top 2 cm of soil is dry", "Check that the pot drains freely", "Pinch off the yellow leaves"],
                    "watch_for": ["Black stems near the soil (root rot)", "New growth turning yellow"],
                },
            },
        ],
        "harvests": [],
        "reminders": [
            {"id": "r1", "type": "water", "title": "Water Balcony Basil", "every": 2, "time": "08:00", "weather_aware": True, "active": True, "inapp": True, "email": True, "next_due": "2026-10-15",
             "history": [
                 {"date": "2026-10-13", "status": "skipped_rain", "reason": "12 mm rain in the last 24h"},
                 {"date": "2026-10-11", "status": "skipped_user", "reason": "Letting the pot dry out"},
                 {"date": "2026-10-09", "status": "missed"},
                 {"date": "2026-10-07", "status": "done"},
                 {"date": "2026-10-05", "status": "done"},
             ]},
            {"id": "r2", "type": "check_problem", "title": "Check basil for new yellow leaves", "every": 0, "time": "09:00", "weather_aware": False, "active": True, "inapp": True, "email": False, "next_due": "2026-10-16", "history": []},
        ],
    },
    {
        "id": "tomato", "type": "tomato", "plant_slug": "cherry-tomato", "nickname": "Cherry Tomato ‘Sungold’", "variety": "Sungold",
        "planted_on": "2026-08-22", "start_method": "seedling", "setting": "outdoor", "container": "Raised bed", "quantity": 1,
        "status": "flowering", "watering_interval_days": 2,
        "tip": "While it flowers, gently shake the stems each morning to help pollination, and keep the soil evenly moist.",
        "timeline": [
            {"id": "t4", "stage": "seedling", "date": "2026-08-22", "note": "Bought a 15 cm seedling and started hardening it off on the balcony.", "photo": False},
            {"id": "t5", "stage": "seedling", "date": "2026-08-29", "note": "Transplanted into the raised bed.", "photo": True},
            {"id": "t6", "stage": "vegetative", "date": "2026-09-20", "note": "Staked and pruned suckers. 45 cm tall.", "photo": True},
            {"id": "t7", "stage": "flowering", "date": "2026-10-12", "note": "First yellow flowers on the top truss.", "photo": True},
        ],
        "care": [
            {"action": "water", "amount": "1 L", "note": "", "date": "2026-10-12", "source": "reminder"},
            {"action": "water", "amount": "1 L", "note": "", "date": "2026-10-10", "source": "reminder"},
            {"action": "prune", "amount": "", "note": "Removed suckers below the first flower truss", "date": "2026-10-08", "source": "manual"},
            {"action": "fertilize", "amount": "10 ml/L", "note": "Tomato feed", "date": "2026-10-03", "source": "reminder"},
            {"action": "treat_pest", "amount": "", "note": "Soapy water spray for aphids", "date": "2026-09-17", "source": "tutor_suggestion"},
        ],
        "problems": [
            {
                "id": "p2", "title": "Aphids on new growth", "category": "pest", "severity": "low", "status": "resolved",
                "description": "Clusters of small green insects under the top leaves, a bit sticky.",
                "opened": "2026-09-15", "resolved": "2026-09-19", "resolution_note": "Sprayed with soapy water twice, 2 days apart. Gone by the 19th.", "photo": True,
                "diagnosis": {
                    "issues": [{"name": "Aphids", "confidence": "high", "reasoning": "Small green clustered insects and sticky honeydew on new growth."}],
                    "immediate_actions": ["Spray with mild soapy water, undersides too", "Repeat in 2–3 days"],
                    "watch_for": ["Curling leaves", "Ants farming the aphids"],
                },
            },
        ],
        "harvests": [],
        "reminders": [
            {"id": "r3", "type": "water", "title": "Water Cherry Tomato", "every": 2, "time": "08:00", "weather_aware": True, "active": True, "inapp": True, "email": True, "next_due": "2026-10-14",
             "history": [{"date": "2026-10-12", "status": "done"}, {"date": "2026-10-10", "status": "done"}, {"date": "2026-10-08", "status": "done"}]},
            {"id": "r4", "type": "fertilize", "title": "Feed Cherry Tomato", "every": 14, "time": "09:00", "weather_aware": False, "active": True, "inapp": True, "email": False, "next_due": "2026-10-17",
             "history": [{"date": "2026-10-03", "status": "done"}]},
            {"id": "r5", "type": "harvest_check", "title": "Check for ripe tomatoes", "every": 0, "time": "09:00", "weather_aware": False, "active": True, "inapp": True, "email": True, "next_due": "2026-11-03", "history": []},
        ],
    },
    {
        "id": "lettuce", "type": "lettuce", "plant_slug": "lettuce", "nickname": "Butterhead Lettuce", "variety": "Butterhead",
        "planted_on": "2026-09-25", "start_method": "seed", "setting": "indoor", "container": "Windowsill tray", "quantity": 6,
        "status": "sprouting", "watering_interval_days": 2,
        "tip": "Thin to one seedling every 15 cm once they have two true leaves, and keep the tray out of direct afternoon heat.",
        "timeline": [
            {"id": "t8", "stage": "seed", "date": "2026-09-25", "note": "Sowed 6 seeds, 0.5 cm deep, in a windowsill tray.", "photo": False},
            {"id": "t9", "stage": "seedling", "date": "2026-10-05", "note": "Germinated! 5 of 6 seeds are up.", "photo": True},
        ],
        "care": [
            {"action": "water", "amount": "200 ml", "note": "", "date": "2026-10-11", "source": "reminder"},
            {"action": "water", "amount": "200 ml", "note": "", "date": "2026-10-09", "source": "reminder"},
            {"action": "water", "amount": "200 ml", "note": "Misted the surface", "date": "2026-10-07", "source": "reminder"},
        ],
        "problems": [],
        "harvests": [],
        "reminders": [
            {"id": "r6", "type": "water", "title": "Water Butterhead Lettuce", "every": 2, "time": "08:00", "weather_aware": False, "active": True, "inapp": True, "email": True, "next_due": "2026-10-13",
             "history": [{"date": "2026-10-11", "status": "done"}, {"date": "2026-10-09", "status": "done"}, {"date": "2026-10-07", "status": "done"}]},
            {"id": "r7", "type": "custom", "title": "Thin lettuce seedlings", "every": 0, "time": "10:00", "weather_aware": False, "active": True, "inapp": True, "email": False, "next_due": "2026-10-17", "history": []},
        ],
    },
    {
        "id": "mint", "type": "mint", "plant_slug": "mint", "nickname": "Mint", "variety": "Spearmint",
        "planted_on": "2026-06-14", "start_method": "seedling", "setting": "outdoor", "container": "Balcony pot · 25 cm", "quantity": 1,
        "status": "harvested", "watering_interval_days": 3,
        "tip": "Mint survives frost, but trim it back before the first hard freeze and it will regrow in spring.",
        "timeline": [
            {"id": "t10", "stage": "seedling", "date": "2026-06-14", "note": "Potted up a small mint plant from the market.", "photo": False},
            {"id": "t11", "stage": "vegetative", "date": "2026-07-20", "note": "Spreading fast. Moved to a bigger pot.", "photo": True},
            {"id": "t12", "stage": "harvest", "date": "2026-09-20", "note": "First harvest — 100 g for tea.", "photo": True},
        ],
        "care": [
            {"action": "prune", "amount": "", "note": "Harvest cut, back to 10 cm", "date": "2026-10-10", "source": "manual"},
            {"action": "water", "amount": "400 ml", "note": "", "date": "2026-10-08", "source": "reminder"},
            {"action": "repot", "amount": "", "note": "Moved to 25 cm pot", "date": "2026-07-20", "source": "manual"},
        ],
        "problems": [],
        "harvests": [
            {"date": "2026-10-10", "quantity": 80, "unit": "g", "note": "Mojitos!"},
            {"date": "2026-09-28", "quantity": 60, "unit": "g", "note": ""},
            {"date": "2026-09-20", "quantity": 100, "unit": "g", "note": "Fresh mint tea"},
        ],
        "reminders": [
            {"id": "r8", "type": "water", "title": "Water Mint", "every": 3, "time": "08:00", "weather_aware": True, "active": True, "inapp": True, "email": False, "next_due": "2026-10-14",
             "history": [{"date": "2026-10-11", "status": "skipped_rain", "reason": "6 mm rain"}, {"date": "2026-10-08", "status": "done"}]},
            {"id": "r9", "type": "custom", "title": "Trim mint before frost", "every": 0, "time": "17:00", "weather_aware": False, "active": True, "inapp": True, "email": True, "next_due": "2026-10-14", "history": []},
        ],
    },
    {
        "id": "spinach", "type": "spinach", "plant_slug": "spinach", "nickname": "Spinach", "variety": "Bloomsdale",
        "planted_on": "2026-10-20", "start_method": "seed", "setting": "outdoor", "container": "Raised bed", "quantity": 12,
        "status": "planned", "watering_interval_days": 2,
        "tip": "Cool weather suits spinach. Sow 1 cm deep, 5 cm apart, and it will shrug off light frosts.",
        "timeline": [], "care": [], "problems": [], "harvests": [],
        "reminders": [{"id": "r10", "type": "custom", "title": "Sow spinach", "every": 0, "time": "10:00", "weather_aware": False, "active": True, "inapp": True, "email": True, "next_due": "2026-10-20", "history": []}],
    },
    {
        "id": "cilantro", "type": "cilantro", "plant_slug": "cilantro", "nickname": "Cilantro", "variety": "",
        "planted_on": "2026-07-10", "start_method": "seed", "setting": "outdoor", "container": "Balcony pot", "quantity": 8,
        "status": "failed", "failure_reason": "Bolted (went to seed) during the late-July heat wave", "watering_interval_days": 2,
        "tip": "Cilantro bolts in summer heat. Try again in early spring or right now in a shady spot — it loves cool weather.",
        "timeline": [
            {"id": "t13", "stage": "seed", "date": "2026-07-10", "note": "Sowed 8 seeds in a balcony pot.", "photo": False},
            {"id": "t14", "stage": "seedling", "date": "2026-07-18", "note": "Up and growing.", "photo": True},
            {"id": "t15", "stage": "flowering", "date": "2026-08-02", "note": "Already flowering — leaves turned thin and feathery.", "photo": True},
        ],
        "care": [{"action": "water", "amount": "300 ml", "note": "", "date": "2026-07-30", "source": "reminder"}],
        "problems": [
            {
                "id": "p3", "title": "Bolting in the heat", "category": "environment", "severity": "high", "status": "resolved",
                "description": "Tall flower stalks appeared after a week above 32 °C.",
                "opened": "2026-08-02", "resolved": "2026-08-15", "resolution_note": "Plant lost. Lesson: sow cilantro in spring or fall, not mid-summer.", "photo": False,
                "diagnosis": {
                    "issues": [{"name": "Heat-triggered bolting", "confidence": "high", "reasoning": "Cilantro flowers quickly when temperatures stay above 30 °C and days are long."}],
                    "immediate_actions": ["Harvest any usable leaves now", "Let a few flowers set seed (coriander) if you like"],
                    "watch_for": ["Next time: sow in spring or fall, in partial shade"],
                },
            },
        ],
        "harvests": [],
        "reminders": [{"id": "r11", "type": "water", "title": "Water Cilantro", "every": 2, "time": "08:00", "weather_aware": True, "active": False, "inapp": True, "email": False, "next_due": "2026-08-16", "history": [{"date": "2026-08-01", "status": "done"}]}],
    },
]

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
TASKS = [
    {"id": "water-lettuce", "plant": "lettuce", "title": "Water Butterhead Lettuce", "detail": "Indoor · windowsill · every 2 days", "icon": "i-drop", "tint": "bg-sky-50 text-sky-600", "care": "water", "done": False, "badge": {"text": "8:00 AM", "cls": "bg-mist text-muted"}},
    {"id": "water-basil", "plant": "basil", "title": "Water Balcony Basil", "detail": "Outdoor · balcony pot", "icon": "i-drop", "tint": "bg-sky-50 text-sky-600", "care": "", "done": True, "skipped": "rain"},
    {"id": "check-basil", "plant": "basil", "title": "Check basil for new yellow leaves", "detail": "Follow-up from your tutor diagnosis", "icon": "i-alert", "tint": "bg-amber-50 text-amber-600", "care": "", "done": False, "badge": {"text": "Problem", "cls": "bg-amber-100 text-amber-800"}},
    {"id": "frost-cover", "plant": "tomato", "title": "Get a frost cover ready for the tomato", "detail": "Before Thursday night", "icon": "i-snow", "tint": "bg-indigo-50 text-indigo-600", "care": "", "done": False, "badge": {"text": "Weather", "cls": "bg-indigo-100 text-indigo-800"}},
]

ACTIVITY = [
    {"icon": "i-camera", "tint": "bg-pink-100 text-pink-700", "subject": "Cherry Tomato", "text": "reached Flowering", "meta": "Timeline photo · Yesterday"},
    {"icon": "i-alert", "tint": "bg-amber-100 text-amber-700", "subject": "Balcony Basil", "text": "problem logged: yellow lower leaves", "meta": "AI diagnosis: overwatering · Yesterday"},
    {"icon": "i-drop", "tint": "bg-sky-100 text-sky-700", "subject": "Butterhead Lettuce", "text": "watered", "meta": "Care log · Oct 11"},
    {"icon": "i-basket", "tint": "bg-amber-100 text-amber-700", "subject": "Mint", "text": "harvested 80 g", "meta": "Harvest log · Oct 10"},
]

TUTOR_WEEKLY_TIPS = [
    "Your tomato is flowering. Gently shake the stems each morning to help pollination.",
    "Let the basil pot dry out before watering again — yesterday’s rain was plenty.",
    "Thin your lettuce to one seedling every 15 cm this weekend.",
]

# Care activity chart (counts per category) — built from CareLog + Harvest aggregates
CARE_CHART = {
    "weeks": {
        "labels": ["Jul 27", "Aug 3", "Aug 10", "Aug 17", "Aug 24", "Aug 31", "Sep 7", "Sep 14", "Sep 21", "Sep 28", "Oct 5", "Oct 12"],
        "water": [3, 4, 4, 5, 6, 6, 7, 7, 8, 8, 8, 0],
        "feed": [0, 1, 0, 1, 1, 0, 1, 1, 1, 1, 0, 0],
        "prune": [1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0],
        "harvest": [0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 1, 0],
    },
    "days": {
        "water": [0, 1, 0, 1, 1, 2, 0, 2, 1, 1, 1, 1, 0, 0],
        "feed": [0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "prune": [0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
        "harvest": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
    },
}

TOMATO_HEIGHT = [["Aug 29", 8], ["Sep 5", 15], ["Sep 12", 28], ["Sep 19", 45], ["Sep 26", 58], ["Oct 3", 70], ["Oct 10", 78]]

# ---------------------------------------------------------------------------
# Community posts
# ---------------------------------------------------------------------------
POST_TYPES = {
    "progress": {"label": "Progress", "cls": "bg-emerald-100 text-emerald-800"},
    "harvest": {"label": "Harvest", "cls": "bg-amber-100 text-amber-800"},
    "question": {"label": "Question", "cls": "bg-sky-100 text-sky-800"},
    "tip": {"label": "Tip", "cls": "bg-violet-100 text-violet-800"},
}

AUTHORS = {
    "balcony_maya": {"username": "balcony_maya", "initials": "M", "grad": "from-lime-200 to-emerald-400 text-forest"},
    "windowsill_sprouts": {"username": "windowsill_sprouts", "initials": "WS", "grad": "from-sky-200 to-indigo-300 text-indigo-900"},
    "balcony_grower": {"username": "balcony_grower", "initials": "BG", "grad": "from-amber-200 to-orange-300 text-orange-900"},
    "backyard_dave": {"username": "backyard_dave", "initials": "BD", "grad": "from-emerald-200 to-teal-300 text-emerald-900"},
    "linda_grows": {"username": "linda_grows", "initials": "LG", "grad": "from-pink-200 to-rose-300 text-rose-900"},
    "rooftop_ravi": {"username": "rooftop_ravi", "initials": "RR", "grad": "from-violet-200 to-fuchsia-300 text-violet-900"},
}

POSTS = [
    {
        "id": 8, "author": "windowsill_sprouts", "plant_slug": "basil", "post_type": "question", "created": "2h",
        "body": "My basil is getting tall and leggy on the windowsill. Should I move it or prune it?",
        "images": 1, "likes": 9, "saves": 2, "liked": False, "saved": False,
        "ai_suggestion": "Leggy growth usually means not enough light. Move it to your brightest window and pinch the top just above a leaf pair — it will branch out within a week.",
        "comments": [
            {"author": "balcony_grower", "body": "Same thing happened to mine in October. A cheap grow light fixed it!", "created": "1h"},
            {"author": "linda_grows", "body": "Pinch it! The tops make great pesto too.", "created": "45m"},
        ],
    },
    {
        "id": 7, "author": "balcony_grower", "plant_slug": "cherry-tomato", "post_type": "tip", "created": "5h",
        "body": "Frost tip for this week: old bedsheets make great covers. Keep them off the leaves with a few stakes, and take them off in the morning.",
        "images": 0, "likes": 31, "saves": 14, "liked": True, "saved": False, "ai_suggestion": "",
        "comments": [{"author": "backyard_dave", "body": "Also water the soil the afternoon before — moist soil holds heat.", "created": "4h"}],
    },
    {
        "id": 6, "author": "balcony_maya", "plant_slug": "mint", "post_type": "harvest", "created": "2d",
        "body": "Third mint harvest — 80 g! Turned it into mojitos. 240 g total since September from one pot.",
        "images": 2, "likes": 12, "saves": 1, "liked": False, "saved": False, "ai_suggestion": "",
        "comments": [{"author": "windowsill_sprouts", "body": "Those look amazing! What fertilizer do you use?", "created": "1d"}],
    },
    {
        "id": 5, "author": "backyard_dave", "plant_slug": "kale", "post_type": "progress", "created": "2d",
        "body": "Kale bed at week 6. Netting kept the cabbage worms off completely this time.",
        "images": 3, "likes": 18, "saves": 5, "liked": False, "saved": True, "ai_suggestion": "", "comments": [],
    },
    {
        "id": 4, "author": "linda_grows", "plant_slug": "lettuce", "post_type": "question", "created": "3d",
        "body": "Lettuce seedlings keep flopping over at the base after a few days. What am I doing wrong?",
        "images": 1, "likes": 6, "saves": 0, "liked": False, "saved": False,
        "ai_suggestion": "Seedlings that collapse at the soil line often have damping-off, a fungal problem. Water from below, improve airflow, and use fresh seed-starting mix for the next sowing.",
        "comments": [{"author": "backyard_dave", "body": "Damping off! Cinnamon on the soil helped me.", "created": "3d"}],
    },
    {
        "id": 3, "author": "rooftop_ravi", "plant_slug": "chili-pepper", "post_type": "harvest", "created": "4d",
        "body": "First chili harvest from the rooftop — 14 peppers before bringing the pots inside for winter.",
        "images": 4, "likes": 22, "saves": 3, "liked": False, "saved": False, "ai_suggestion": "", "comments": [],
    },
    {
        "id": 2, "author": "windowsill_sprouts", "plant_slug": "microgreens", "post_type": "tip", "created": "5d",
        "body": "Microgreens are the easiest win for winter. Radish microgreens are ready in 8 days on a sunny sill.",
        "images": 1, "likes": 15, "saves": 9, "liked": False, "saved": False, "ai_suggestion": "", "comments": [],
    },
    {
        "id": 1, "author": "balcony_maya", "plant_slug": "cherry-tomato", "post_type": "progress", "created": "3w",
        "body": "Staked the tomato and pinched out the suckers — 45 cm tall at four weeks. Hoping for flowers before it gets cold!",
        "images": 1, "likes": 8, "saves": 0, "liked": False, "saved": False, "ai_suggestion": "", "comments": [],
    },
]
