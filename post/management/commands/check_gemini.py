from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from post import gemini


class Command(BaseCommand):
    help = ("Check the Gemini setup. By default sends one tiny sample post and prints the summary; "
            "with --list-models prints the model names your API key can use (set one as API_MODEL in .env).")

    def add_arguments(self, parser):
        parser.add_argument("--list-models", action="store_true", help="List models usable with generateContent.")

    def handle(self, *args, **options):
        if not gemini.is_configured():
            raise CommandError("No API key found. Add  API_KEY=your-key  to .env and try again.")
        try:
            if options["list_models"]:
                self.stdout.write(f"Currently configured model: {settings.GEMINI_MODEL}")
                for name in gemini.list_models():
                    self.stdout.write(f"  {name}")
                return
            self.stdout.write(f"Model: {settings.GEMINI_MODEL}")
            result = gemini.summarize("My tomato plants finally started flowering after three weeks. "
                                      "I water every two days. When will I get fruit?")
        except gemini.GeminiError as exc:
            raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(f"Gemini replied: {result}"))
