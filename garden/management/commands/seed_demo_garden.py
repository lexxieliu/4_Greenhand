from datetime import date, datetime, timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from calendar_app.models import Reminder, ReminderOccurrence
from calendar_app.recurrence import local_to_utc
from calendar_app.services import HORIZON_DAYS, materialize, rule_for, user_timezone
from garden.demo_data import DEMO_GARDEN
from garden.models import CareLog, Harvest, Problem, TimelineEntry, UserPlant
from greenhand.clock import today
from greenhand.users import DEMO_USERNAME
from plants.models import Plant

DEMO_WRITTEN_FOR = date(2026, 10, 13)      # demo_data dates are relative to this day; they are shifted to today


class Command(BaseCommand):
    help = (f"Replace the demo account's ({DEMO_USERNAME}) garden with the demo plants in garden/demo_data.py, "
            "dated relative to today. Use --password to be able to sign in as the demo account.")

    def add_arguments(self, parser):
        parser.add_argument("--email", default="maya@greenhand.demo", help="Email to sign in with.")
        parser.add_argument("--password", help="Set (or reset) the demo account's password.")

    @transaction.atomic
    def handle(self, *args, **options):
        if not Plant.objects.exists():
            call_command("seed_plants", stdout=self.stdout)
        self.shift = today() - DEMO_WRITTEN_FOR
        self.plants = {p.slug: p for p in Plant.objects.all()}
        user, _ = User.objects.get_or_create(username=DEMO_USERNAME, defaults={"first_name": "Maya"})
        user.email = options["email"]
        if options["password"]:
            user.set_password(options["password"])
        user.save()
        Reminder.objects.filter(user=user).delete()
        UserPlant.objects.filter(user=user).delete()
        for entry in DEMO_GARDEN:
            self._create_plant(user, entry)
        login = f" Sign in with {user.email}." if user.has_usable_password() else " Pass --password to sign in."
        self.stdout.write(self.style.SUCCESS(f"{len(DEMO_GARDEN)} demo plants created for {DEMO_USERNAME}.{login}"))

    def _day(self, iso):
        return date.fromisoformat(iso) + self.shift

    def _aware(self, iso):
        return timezone.make_aware(datetime.combine(self._day(iso), datetime.min.time()))

    def _create_plant(self, user, entry):
        """One demo plant with its logs, copied as written (no services, so the history stays exact)."""
        up = UserPlant.objects.create(
            user=user, plant=self.plants[entry["plant_slug"]], nickname=entry["nickname"], variety=entry["variety"],
            planted_on=self._day(entry["planted_on"]), start_method=entry["start_method"], setting=entry["setting"],
            container_type=entry["container"], quantity=entry["quantity"], status=entry["status"],
            watering_interval_days=entry["watering_interval_days"], failure_reason=entry.get("failure_reason", ""),
            failed_at=timezone.now() if entry["status"] == "failed" else None,
            first_harvest_at=self._aware(min(h["date"] for h in entry["harvests"])) if entry["harvests"] else None,
        )
        TimelineEntry.objects.bulk_create([TimelineEntry(user_plant=up, stage=t["stage"], recorded_on=self._day(t["date"]),
                                                         note=t["note"]) for t in entry["timeline"]])
        CareLog.objects.bulk_create([CareLog(user_plant=up, action=c["action"], amount=c["amount"], note=c["note"],
                                             performed_on=self._day(c["date"]), source=c["source"]) for c in entry["care"]])
        for p in entry["problems"]:
            Problem.objects.create(
                user_plant=up, title=p["title"], description=p["description"], category=p["category"],
                severity=p["severity"], status=p["status"], opened_on=self._day(p["opened"]),
                resolution_note=p.get("resolution_note", ""),
                resolved_at=self._aware(p["resolved"]) if p.get("resolved") else None,
            )
        Harvest.objects.bulk_create([Harvest(user_plant=up, harvested_on=self._day(h["date"]), quantity=h.get("quantity"),
                                             unit=h["unit"], note=h["note"]) for h in entry["harvests"]])
        for r in entry["reminders"]:
            self._create_reminder(user, up, r)

    def _create_reminder(self, user, up, r):
        """A calendar_app reminder with its past occurrences (done, skipped after rain …) and upcoming ones."""
        zone = user_timezone(user)
        clock = datetime.strptime(r["time"], "%H:%M").time()
        reminder = Reminder.objects.create(
            user=user, user_plant=up, type=r["type"], title=r["title"], recurrence_rule=rule_for(r["every"]),
            next_due_at=local_to_utc(self._day(r["next_due"]), clock, zone), time_of_day=clock, timezone=zone,
            is_active=r["active"], weather_aware=r["weather_aware"],
        )
        ReminderOccurrence.objects.bulk_create([
            ReminderOccurrence(reminder=reminder, due_at=local_to_utc(self._day(o["date"]), clock, zone),
                               status=o["status"], skip_reason=o.get("reason", ""))
            for o in r["history"]
        ])
        if reminder.is_active:
            materialize(reminder, timezone.now() + timedelta(days=HORIZON_DAYS))
