import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from tutor import llm


class Command(BaseCommand):
    help = "Download (first run only) and load the local LLM, then answer one test question."

    def handle(self, *args, **options):
        self.stdout.write(f"Model: {settings.LOCAL_MODEL_ID}")
        start = time.time()
        try:
            llm.get_model()
        except Exception as exc:
            raise CommandError(f"Could not load the model: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Loaded in {time.time() - start:.1f}s"))
        start = time.time()
        result, raw = llm.generate("care", "How often should I water a tomato plant in summer?")
        self.stdout.write(f"Test answer ({time.time() - start:.1f}s): {result}")
