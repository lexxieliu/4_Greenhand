import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from plants.models import Plant, PlantProblemSummary

SEED_FILE = Path(__file__).resolve().parents[2] / "data" / "plants.json"
ZONE = "5b"   # the curated planting months are for hardiness zone 5b (Chicago); other zones come later


def plant_fields(row):
    germination = row["days_to_germination"] or [None, None]
    harvest = row["days_to_harvest"] or [None, None]
    return {
        "common_name": row["common_name"], "scientific_name": row["scientific_name"], "category": row["category"],
        "difficulty": row["difficulty"], "description": row["description"],
        "sunlight_requirement": row["sunlight_requirement"], "watering_interval_days": row["watering_interval_days"],
        "min_temp_c": row["min_temp_c"], "max_temp_c": row["max_temp_c"], "frost_tolerant": row["frost_tolerant"],
        "days_to_germination_min": germination[0], "days_to_germination_max": germination[1],
        "days_to_harvest_min": harvest[0], "days_to_harvest_max": harvest[1], "spacing_cm": row["spacing_cm"],
        "container_friendly": row["container_friendly"], "indoor_friendly": row["indoor_friendly"],
        "harvest_mode": row["harvest_mode"], "hardiness_zones": row["hardiness_zones"],
        "planting_months": row["planting_months"], "care_guide": "\n".join(row["care"]), "is_published": True,
    }


class Command(BaseCommand):
    help = "Create or update the curated plant catalog from plants/data/plants.json (safe to run again)."

    @transaction.atomic
    def handle(self, *args, **options):
        rows = json.loads(SEED_FILE.read_text(encoding="utf-8"))
        created = 0
        for row in rows:
            plant, was_created = Plant.objects.update_or_create(slug=row["slug"], defaults=plant_fields(row))
            created += was_created
            plant.problem_summaries.all().delete()
            PlantProblemSummary.objects.bulk_create([
                PlantProblemSummary(plant=plant, problem_name=p["name"], symptoms=p["symptoms"], solution=p["solution"],
                                    source_count=p["source_count"])
                for p in row["problems"]
            ])
        self.stdout.write(self.style.SUCCESS(f"{len(rows)} plants seeded ({created} new, {len(rows) - created} updated)."))
