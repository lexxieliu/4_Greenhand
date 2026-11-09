"""Garden context for the tutor prompt (PRD 3.4 "Context injected into every conversation"), from the
signed-in user's real data.

Only the minimum the model needs is sent (PRD 8.2): city-level location and hardiness zone, growing space,
the plant's species/stage/logs and the forecast. Never username, email or coordinates. Everything the user
typed is cleaned first, so a nickname or note cannot close the <garden> tag it is placed in.
"""
import re
from datetime import timedelta

from garden.models import CareLog, UserPlant
from greenhand.clock import today
from userprofile.models import Profile
from weather.services import get_snapshot

from .guardrails import clean_text

RECENT_DAYS = 14          # PRD FR-31: recent logs = last ~14 days
FORECAST_DAYS = 3
MAX_GARDEN_LOGS = 8       # whole-garden questions: the model is small, keep the context short
HIDDEN_STATUSES = ("failed", "archived")
FROST_THRESHOLD_C = 2     # PRD FR-42 default
RAIN_SKIP_MM = 5          # PRD FR-41 default
RAIN_SKIP_PROB = 70


def _text(value, limit=160):
    return clean_text(value or "", limit)


class GardenContext:
    """The context for one user. A user of None (e.g. the warm-up command) has an empty garden."""

    def __init__(self, user):
        self.user = user
        self.today = today()        # the garden's own clock, so "last 14 days" matches the dates it logs
        self.since = self.today - timedelta(days=RECENT_DAYS)

    def plants(self):
        """Plants the user can ask about (not failed or archived)."""
        if self.user is None:
            return UserPlant.objects.none()
        return UserPlant.objects.filter(user=self.user).exclude(status__in=HIDDEN_STATUSES).select_related("plant")

    def find(self, plant_id):
        return self.plants().filter(pk=plant_id).first() if str(plant_id).isdigit() else None

    def detect(self, question):
        """The garden plant the question mentions by its full nickname or a species word ('my tomatoes' -> tomato),
        or None. Single nickname words are ignored: 'balcony' must not select 'Balcony Basil'."""
        text = question.lower()
        words = re.findall(r"[a-z]+", text)
        for plant in self.plants():
            keys = {w for w in re.findall(r"[a-z]+", plant.plant.common_name.lower()) if len(w) >= 4}
            if plant.nickname.lower() in text or any(w.startswith(k) for w in words for k in keys):
                return plant
        return None

    def describe(self, plant):
        return {"id": plant.pk, "nickname": plant.nickname, "species": plant.plant.common_name}

    def _plant_line(self, plant):
        when = (f"planned for {plant.planted_on}" if plant.status == "planned"
                else f"day {(self.today - plant.planted_on).days} since planting")
        open_problems = [_text(p.title, 80) for p in plant.problems.exclude(status="resolved")]
        problems = f"; open problem: {', '.join(open_problems)}" if open_problems else ""
        variety = f", {_text(plant.variety, 100)}" if plant.variety else ""
        return f"{_text(plant.nickname, 60)} ({plant.plant.common_name}{variety}): {plant.status}, {when}, {plant.setting}{problems}"

    def _plant_details(self, plant):
        """Recent care logs, timeline notes and open problems for a scoped plant."""
        logs = plant.care_logs.filter(performed_on__gte=self.since)
        lines = [f"Care logs (last {RECENT_DAYS} days): " + ("; ".join(self._log_text(log) for log in logs) or "none")]
        lines += [f"Timeline note {t.recorded_on} ({t.stage}): {_text(t.note)}"
                  for t in plant.timeline.filter(recorded_on__gte=self.since)]
        lines += [f"Open problem since {p.opened_on}: {_text(p.title, 80)} – {_text(p.description)}"
                  for p in plant.problems.exclude(status="resolved")]
        return lines

    @staticmethod
    def _log_text(log):
        amount = f" {_text(log.amount, 50)}" if log.amount else ""
        note = f" ({_text(log.note, 100)})" if log.note else ""
        return f"{log.performed_on} {log.action}{amount}{note}"

    def _garden_logs(self):
        logs = (CareLog.objects.filter(user_plant__in=self.plants(), performed_on__gte=self.since)
                .select_related("user_plant")[:MAX_GARDEN_LOGS])
        return "; ".join(f"{_text(log.user_plant.nickname, 60)}: {self._log_text(log)}" for log in logs)

    @staticmethod
    def _weather_lines(snapshot):
        forecast = " | ".join(f"{d['date']}: high {d['high']} °C, low {d['low']} °C, {d['precip_prob']}% chance of rain"
                              for d in snapshot.forecast[:FORECAST_DAYS])
        lines = [f"Weather: Now {snapshot.current_temp_c} °C; rain in the last 24h: {snapshot.rain_last_24h_mm} mm"
                 + (f" | {forecast}" if forecast else "")]
        if snapshot.min_temp_next_48h_c <= FROST_THRESHOLD_C:
            lines.append(f"Active alert: frost risk within 48h (low {snapshot.min_temp_next_48h_c} °C)")
        if snapshot.rain_last_24h_mm >= RAIN_SKIP_MM or snapshot.precip_prob_next_12h >= RAIN_SKIP_PROB:
            lines.append("Active alert: enough rain to skip watering outdoor plants today")
        return lines

    @staticmethod
    def _setting_rule(plant):
        """The app's weather rules (FR-41/42): rain and frost only apply to outdoor plants."""
        if plant.setting == "outdoor":
            return "Setting rule: outdoor plant, so rain counts as watering and frost can damage it."
        return f"Setting rule: {plant.setting} plant, so rain and frost do NOT affect it; water it by checking its soil."

    def _place_lines(self, plant):
        """Date, location, growing space and the weather that applies to this question."""
        profile = Profile.objects.filter(user=self.user).first() if self.user else None
        lines = [f"Today: {self.today:%A, %B} {self.today.day}, {self.today.year}"]
        if profile:
            place = ", ".join(_text(p, 100) for p in (profile.city, profile.region) if p)
            zone = f"hardiness zone {_text(profile.hardiness_zone, 5)}" if profile.hardiness_zone else ""
            if place or zone:
                lines.append("Location: " + ", ".join(p for p in (place, zone) if p))
            grower = [profile.get_experience_level_display(), profile.get_space_type_display(),
                      profile.get_sunlight_level_display()]
            if any(grower):
                lines.append("Grower: " + ", ".join(g.lower() for g in grower if g))
        outdoor = not plant or plant.setting == "outdoor"      # indoor plants: the outdoor forecast is irrelevant
        if outdoor and profile and profile.latitude is not None and profile.longitude is not None:
            snapshot = get_snapshot(profile.latitude, profile.longitude)
            if snapshot:
                lines += self._weather_lines(snapshot)
        return lines

    def build(self, plant=None):
        """Plain-text context block. With a plant, it is scoped to that plant (PRD FR-32)."""
        lines = self._place_lines(plant)
        if plant:
            lines.append("Plant asked about: " + self._plant_line(plant))
            lines.append(self._setting_rule(plant))
            lines += self._plant_details(plant)
        else:
            plants = self.plants()
            lines.append("Garden: " + (" | ".join(self._plant_line(p) for p in plants) or "no plants yet"))
            logs = self._garden_logs()
            if logs:
                lines.append(f"Recent care (last {RECENT_DAYS} days): {logs}")
        return "\n".join(lines)
