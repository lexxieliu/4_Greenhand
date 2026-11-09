from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Profile

PASSWORD = "garden12345"


class AuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("maya", "maya@example.com", PASSWORD)
        self.login_url = reverse("userprofile:login")

    def _login(self, url=None, **fields):
        return self.client.post(url or self.login_url, {"email": "maya@example.com", "password": PASSWORD, **fields})

    def test_signup_creates_user_and_profile(self):
        data = {"username": "new_grower", "email": "new@example.com", "password": PASSWORD, "terms": "on"}
        self.assertRedirects(self.client.post(reverse("userprofile:signup"), data), self.login_url)
        self.assertTrue(Profile.objects.filter(user__username="new_grower").exists())
        self.assertTrue(User.objects.get(username="new_grower").check_password(PASSWORD))

    def test_signup_rejects_duplicates(self):
        data = {"username": "MAYA", "email": "MAYA@example.com", "password": PASSWORD, "terms": "on"}
        response = self.client.post(reverse("userprofile:signup"), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sorted(response.context["form"].errors), ["email", "username"])

    def test_login_starts_a_session(self):
        self.assertRedirects(self._login(), reverse("garden:dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_wrong_password_and_unknown_email_get_the_same_error(self):
        wrong = self._login(password="nope")
        unknown = self._login(email="ghost@example.com")
        self.assertContains(wrong, "don’t match")
        self.assertContains(unknown, "don’t match")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_next_is_followed_only_on_this_site(self):
        self.assertContains(self.client.get(f"{self.login_url}?next=/tutor/"), 'name="next" value="/tutor/"')
        self.assertRedirects(self._login(next="/tutor/"), "/tutor/")
        self.client.logout()
        self.assertRedirects(self._login(next="https://evil.example/"), reverse("garden:dashboard"))

    def test_logout_ends_the_session(self):
        self.client.force_login(self.user)
        self.client.post(reverse("userprofile:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)
