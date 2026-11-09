"""Context for `evaluate_tutor`: the seeded demo garden (seed_demo_garden) plus the mock location and weather
the eval cases in test_cases.json were written against, so results stay comparable with docs/ai_eval/."""
from django.contrib.auth.models import User

from greenhand import mock_data as data
from greenhand.users import DEMO_USERNAME
from tutor.context import FORECAST_DAYS, GardenContext


class DemoContext(GardenContext):
    def __init__(self):
        super().__init__(User.objects.get_or_create(username=DEMO_USERNAME)[0])

    def find(self, plant_id):
        """Eval cases name a plant by a word of its slug ('lettuce')."""
        return self.plants().filter(plant__slug__icontains=plant_id).first()

    def _place_lines(self, plant):
        user = data.USER
        lines = [
            f"Today: {self.today:%A, %B} {self.today.day}, {self.today.year}",
            f"Location: {data.LOCATION['label']}, hardiness zone {data.LOCATION['hardiness_zone']}",
            f"Grower: {user['experience_level'].lower()}, {user['space_type'].lower()}, {user['sunlight_level'].lower()}",
        ]
        if plant and plant.setting != "outdoor":
            return lines
        now = data.WEATHER["current"]
        days = [f"{d['day_long']}: {d['condition'].lower()}, high {d['high']} °C, low {d['low']} °C{' – FROST RISK' if d['frost'] else ''}"
                for d in data.WEATHER["daily"][:FORECAST_DAYS]]
        lines.append(" | ".join([f"Weather: Now {now['temp_c']} °C, {now['condition'].lower()}; "
                                 f"rain in the last 24h: {now['rain_last_24h_mm']} mm", *days]))
        alerts = [a for a in data.WEATHER_ALERTS if not plant or plant.nickname in a["plants"]]
        return lines + [f"Active alert: {a['title']} ({a['valid']}); affects {', '.join(a['plants'])}" for a in alerts]
