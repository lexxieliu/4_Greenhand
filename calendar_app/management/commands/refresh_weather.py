from django.core.management.base import BaseCommand

from calendar_app.jobs import job_lock
from weather.services import refresh_weather


class Command(BaseCommand):
    help = "Run refresh weather safely; see docs/area3.md."

    def handle(self, *args, **options):
        with job_lock():
            result = refresh_weather()

        self.stdout.write(self.style.SUCCESS(f"Completed refresh_weather: {result}"))
