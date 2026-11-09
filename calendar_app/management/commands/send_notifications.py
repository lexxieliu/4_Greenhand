from django.core.management.base import BaseCommand

from calendar_app.jobs import job_lock
from notifications.services import deliver_emails


class Command(BaseCommand):
    help = "Run send notifications safely; see docs/area3.md."

    def handle(self, *args, **options):
        with job_lock():
            result = deliver_emails()

        self.stdout.write(self.style.SUCCESS(f"Completed send_notifications: {result}"))
