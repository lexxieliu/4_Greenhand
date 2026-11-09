import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from plants.models import Plant

from .models import Garden


class ModelTests(TestCase):
    def test_label_prefers_nickname(self):
        user = User.objects.create_user("u")
        garden = Garden(user=user, plant=Plant(plant_name="Basil", category="herb"))
        self.assertEqual(garden.label, "Basil")
        garden.nickname = "Balcony Basil"
        self.assertEqual(garden.label, "Balcony Basil")


class PageTests(TestCase):
    def test_pages_render(self):
        for name in ("garden:dashboard", "plants:list", "community:feed", "landing"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)


class AccessibilityTests(SimpleTestCase):
    """Static checks over every template (PRD 2.2, WCAG 2.1 AA)."""

    def _templates(self):
        return [(p, p.read_text()) for p in Path(settings.BASE_DIR, "templates").rglob("*.html")]

    def test_images_have_alt_text(self):
        for path, text in self._templates():
            for tag in re.findall(r"<img\b[^>]*>", text):
                self.assertIn("alt=", tag, path)

    def test_decorative_icons_are_hidden_from_screen_readers(self):
        for path, text in self._templates():
            if path.name == "icons.html":       # the sprite itself, not an icon in the page
                continue
            for tag in re.findall(r'<svg\b[^>]*class="ic\b[^>]*>', text):
                self.assertIn('aria-hidden="true"', tag, path)

    def test_icon_only_buttons_have_names(self):
        for path, text in self._templates():
            for attrs, inner in re.findall(r"<button\b([^>]*)>\s*(<svg\b(?:(?!</svg>).)*</svg>)\s*</button>", text, re.S):
                self.assertIn("aria-label", attrs, f"{path}: {attrs[:60]}")
