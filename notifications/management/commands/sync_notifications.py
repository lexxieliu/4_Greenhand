from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from notifications.services import sync_weather


class Command(BaseCommand):
    help = "Raise weather notifications for every user with a growing location (run it every few hours, e.g. from cron)."

    def handle(self, *args, **options):
        users = get_user_model().objects.filter(growing_location__isnull=False)
        for user in users:
            sync_weather(user)
        self.stdout.write(self.style.SUCCESS(f"Checked the weather for {users.count()} users."))
