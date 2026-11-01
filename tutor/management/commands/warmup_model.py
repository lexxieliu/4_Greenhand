import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from tutor import knowledge, llm
from tutor.services import ask_tutor


class Command(BaseCommand):
    help = "Download (first run only) and load the tutor's embedding model and LLM, then answer one test question."

    def handle(self, *args, **options):
        self.stdout.write(f"Embedding model: {settings.EMBEDDING_MODEL_ID}\nLLM: {settings.LOCAL_MODEL_ID}")
        start = time.time()
        try:
            knowledge.search("warm up")
            llm.get_model()
        except Exception as exc:
            raise CommandError(f"Could not load the models: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Models loaded in {time.time() - start:.1f}s"))
        start = time.time()
        result = ask_tutor("How often should I water basil in a pot?")
        self.stdout.write(f"Test answer ({time.time() - start:.1f}s): {result.get('answer') or result.get('message')}")
