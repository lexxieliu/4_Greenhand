from django.core.management.base import BaseCommand

from calendar_app.jobs import job_lock
from calendar_app.services import process_due
from notifications.services import deliver_emails


class Command(BaseCommand):
    help = "Run process reminders safely; see docs/area3.md."

    def handle(self, *args, **options):
        with job_lock():
            result = process_due()
            deliver_emails()
        self.stdout.write(self.style.SUCCESS(f"Completed process_reminders: {result}"))
