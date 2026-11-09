"""
Mock data for the parts of the Greenhand preview that are not backed by the database yet.

The plant catalog and My Garden now live in the database (plants.Plant, garden.UserPlant …; seed them
with `python manage.py seed_plants` and `seed_demo_garden`).

The remaining views (weather, community, notifications) read from here. Field names follow the PRD schema (section 7) so each block maps onto a model later:

    USER / LOCATION      -> accounts.Profile, accounts.GrowingLocation
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
# Dashboard
# ---------------------------------------------------------------------------
TUTOR_WEEKLY_TIPS = [
    "Your tomato is flowering. Gently shake the stems each morning to help pollination.",
    "Let the basil pot dry out before watering again — yesterday’s rain was plenty.",
    "Thin your lettuce to one seedling every 15 cm this weekend.",
]

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
