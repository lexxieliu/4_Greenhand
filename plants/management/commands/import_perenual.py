import json
import os
import urllib.parse
import urllib.request

from django.core.management.base import BaseCommand, CommandError

from plants.models import Plant

SEARCH_URL = "https://perenual.com/api/v2/species-list"


def search_species(name, key):
    """First Perenual species matching the name, or None."""
    query = urllib.parse.urlencode({"key": key, "q": name})
    with urllib.request.urlopen(f"{SEARCH_URL}?{query}", timeout=15) as response:
        results = json.load(response).get("data") or []
    return results[0] if results else None


class Command(BaseCommand):
    help = ("Link catalog plants to Perenual species (fills external_source_id and a missing scientific_name). "
            "Needs PERENUAL_API_KEY in the environment; the free plan allows 100 requests a day.")

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50, help="Maximum plants to look up in this run.")

    def handle(self, *args, **options):
        key = os.environ.get("PERENUAL_API_KEY")
        if not key:
            raise CommandError("Set PERENUAL_API_KEY in .env first (https://perenual.com/docs/api).")
        linked = 0
        for plant in Plant.objects.filter(external_source_id="")[:options["limit"]]:
            try:
                species = search_species(plant.common_name, key)
            except OSError as exc:
                raise CommandError(f"Perenual request failed after {linked} plants: {exc}") from exc
            if not species:
                self.stdout.write(f"  no match: {plant.common_name}")
                continue
            plant.external_source_id = str(species["id"])
            if not plant.scientific_name and species.get("scientific_name"):
                plant.scientific_name = species["scientific_name"][0]
            plant.save(update_fields=["external_source_id", "scientific_name"])
            linked += 1
        self.stdout.write(self.style.SUCCESS(f"Linked {linked} plants to Perenual."))
