from datetime import date

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from garden.demo_data import DEMO_GARDEN
from garden.models import CareLog, Harvest, Problem, Reminder, ReminderOccurrence, TimelineEntry, UserPlant
from greenhand.clock import now as clock_now
from greenhand.users import DEMO_USERNAME
from plants.models import Plant


def _day(iso):
    return date.fromisoformat(iso)


def _create_plant(user, entry, plants):
    """One demo plant with its logs, copied as-is (no services, so the history stays exactly as written)."""
    up = UserPlant.objects.create(
        user=user, plant=plants[entry["plant_slug"]], nickname=entry["nickname"], variety=entry["variety"],
        planted_on=_day(entry["planted_on"]), start_method=entry["start_method"], setting=entry["setting"],
        container_type=entry["container"], quantity=entry["quantity"], status=entry["status"],
        watering_interval_days=entry["watering_interval_days"], failure_reason=entry.get("failure_reason", ""),
        failed_at=clock_now() if entry["status"] == "failed" else None,
        first_harvest_at=timezone.make_aware(timezone.datetime.combine(_day(min(h["date"] for h in entry["harvests"])),
                                                                       timezone.datetime.min.time()))
        if entry["harvests"] else None,
    )
    TimelineEntry.objects.bulk_create([TimelineEntry(user_plant=up, stage=t["stage"], recorded_on=_day(t["date"]),
                                                     note=t["note"]) for t in entry["timeline"]])
    CareLog.objects.bulk_create([CareLog(user_plant=up, action=c["action"], amount=c["amount"], note=c["note"],
                                         performed_on=_day(c["date"]), source=c["source"]) for c in entry["care"]])
    for p in entry["problems"]:
        Problem.objects.create(
            user_plant=up, title=p["title"], description=p["description"], category=p["category"], severity=p["severity"],
            status=p["status"], opened_on=_day(p["opened"]), resolution_note=p.get("resolution_note", ""),
            resolved_at=timezone.make_aware(timezone.datetime.combine(_day(p["resolved"]), timezone.datetime.min.time()))
            if p.get("resolved") else None,
        )
    Harvest.objects.bulk_create([Harvest(user_plant=up, harvested_on=_day(h["date"]), quantity=h.get("quantity"),
                                         unit=h["unit"], note=h["note"]) for h in entry["harvests"]])
    for r in entry["reminders"]:
        reminder = Reminder.objects.create(
            user=user, user_plant=up, type=r["type"], title=r["title"], interval_days=r["every"], time=r["time"],
            next_due_on=_day(r["next_due"]), is_active=r["active"], notify_in_app=r["inapp"], notify_email=r["email"],
            weather_aware=r["weather_aware"],
        )
        ReminderOccurrence.objects.bulk_create([
            ReminderOccurrence(reminder=reminder, due_on=_day(o["date"]), status=o["status"], reason=o.get("reason", ""))
            for o in r["history"]
        ])


class Command(BaseCommand):
    help = f"Replace the demo account's ({DEMO_USERNAME}) garden with the demo plants in garden/demo_data.py."

    @transaction.atomic
    def handle(self, *args, **options):
        if not Plant.objects.exists():
            call_command("seed_plants", stdout=self.stdout)
        plants = {p.slug: p for p in Plant.objects.all()}
        user, _ = User.objects.get_or_create(username=DEMO_USERNAME)
        Reminder.objects.filter(user=user).delete()
        UserPlant.objects.filter(user=user).delete()
        for entry in DEMO_GARDEN:
            _create_plant(user, entry, plants)
        self.stdout.write(self.style.SUCCESS(f"{len(DEMO_GARDEN)} demo plants created for {DEMO_USERNAME}."))
