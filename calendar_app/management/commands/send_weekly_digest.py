from django.core.management.base import BaseCommand

from calendar_app.jobs import job_lock
from notifications.services import deliver_emails, weekly_digest


class Command(BaseCommand):
    help = "Run send weekly digest safely; see docs/area3.md."

    def handle(self, *args, **options):
        with job_lock():
            result = weekly_digest()
            deliver_emails()
        self.stdout.write(self.style.SUCCESS(f"Completed send_weekly_digest: {result}"))
