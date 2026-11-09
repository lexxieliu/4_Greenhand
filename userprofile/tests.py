from django.contrib.auth.models import User
<<<<<<< HEAD
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import GrowingLocation, Profile


class AuthFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("maya_g", "maya@example.com", "Sprout123")
        Profile.objects.filter(user=self.user).update(onboarding_completed=True)

    def login(self, email="maya@example.com", password="Sprout123", **extra):
        return self.client.post(reverse("userprofile:login"), {"email": email, "password": password, **extra})

    def test_login_with_email_starts_session(self):
        response = self.login(remember="on")
        self.assertRedirects(response, reverse("garden:dashboard"), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_wrong_password_or_unknown_email_fails(self):
        for kwargs in ({"password": "Wrong123"}, {"email": "nobody@example.com"}):
            response = self.login(**kwargs)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Incorrect email or password.")
            self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_ignores_offsite_next(self):
        response = self.client.post(reverse("userprofile:login") + "?next=https://evil.example/", {"email": "maya@example.com", "password": "Sprout123"})
        self.assertRedirects(response, reverse("garden:dashboard"), fetch_redirect_response=False)

    def test_signup_creates_user_who_can_log_in(self):
        response = self.client.post(reverse("userprofile:signup"), {"username": "new_grower", "email": "new@example.com", "password": "Basil2026", "terms": "on"})
        self.assertRedirects(response, reverse("userprofile:login"), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(username="new_grower", email="new@example.com").exists())
        self.assertEqual(self.login(email="new@example.com", password="Basil2026").status_code, 302)

    def test_signup_rejects_duplicates(self):
        response = self.client.post(reverse("userprofile:signup"), {"username": "MAYA_G", "email": "MAYA@example.com", "password": "Basil2026", "terms": "on"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "taken")
        self.assertContains(response, "already exists")
        self.assertEqual(User.objects.count(), 1)

    def test_logout_ends_session_and_requires_post(self):
        self.login()
        self.assertEqual(self.client.get(reverse("userprofile:logout")).status_code, 405)
        response = self.client.post(reverse("userprofile:logout"))
        self.assertRedirects(response, reverse("userprofile:login"))
        self.assertNotIn("_auth_user_id", self.client.session)


class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("maya_g", "maya@example.com", "Sprout123")

    def request_reset(self, email="maya@example.com"):
        return self.client.post(reverse("userprofile:password_reset"), {"email": email})

    def reset_link(self):
        from django.core import mail
        import re
        return re.search(r"https?://testserver(\S+)", mail.outbox[0].body).group(1)

    def test_known_email_sends_link(self):
        from django.core import mail
        response = self.request_reset()
        self.assertRedirects(response, reverse("userprofile:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["maya@example.com"])

    def test_unknown_email_looks_the_same_and_sends_nothing(self):
        from django.core import mail
        response = self.request_reset("nobody@example.com")
        self.assertRedirects(response, reverse("userprofile:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_full_reset_changes_password_and_link_works_once(self):
        self.request_reset()
        confirm = self.client.get(self.reset_link(), follow=True)
        post_url = confirm.redirect_chain[-1][0]
        response = self.client.post(post_url, {"new_password1": "Tomato2026", "new_password2": "Tomato2026"})
        self.assertRedirects(response, reverse("userprofile:password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Tomato2026"))
        self.assertContains(self.client.get(self.reset_link()), "Link expired")

    def test_new_password_must_follow_signup_rule(self):
        self.request_reset()
        post_url = self.client.get(self.reset_link(), follow=True).redirect_chain[-1][0]
        response = self.client.post(post_url, {"new_password1": "onlyletters", "new_password2": "onlyletters"})
        self.assertContains(response, "at least one letter and one number")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Sprout123"))

    def test_bad_token_rejected(self):
        response = self.client.get(reverse("userprofile:password_reset_confirm", args=["bad", "bad-token"]))
        self.assertContains(response, "Link expired")


class ProfileModelTests(TestCase):
    def test_signup_creates_profile_with_defaults(self):
        self.client.post(reverse("userprofile:signup"), {"username": "new_grower", "email": "new@example.com", "password": "Basil2026", "terms": "on"})
        profile = User.objects.get(username="new_grower").user_related_profile
        self.assertFalse(profile.onboarding_completed)
        self.assertEqual(profile.experience_level, "beginner")
        self.assertEqual(profile.units, "metric")
        self.assertEqual(profile.notification_prefs, {})

    def test_profile_not_duplicated_on_user_save(self):
        user = User.objects.create_user("maya_g", "maya@example.com", "Sprout123")
        user.save()
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)

    def test_growing_location_is_one_per_user(self):
        user = User.objects.create_user("maya_g", "maya@example.com", "Sprout123")
        GrowingLocation.objects.create(user=user, city="Champaign", region="Illinois", country_code="US", latitude="40.11642", longitude="-88.24338", timezone="America/Chicago")
        self.assertEqual(user.growing_location.city, "Champaign")
        with self.assertRaises(IntegrityError), transaction.atomic():
            GrowingLocation.objects.create(user=user, city="Urbana", latitude="40.11059", longitude="-88.20727")


CHAMPAIGN = {"city": "Champaign", "region": "Illinois", "country_code": "US", "latitude": 40.12, "longitude": -88.24,
             "timezone": "America/Chicago", "label": "Champaign, Illinois, United States"}


class OnboardingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("maya_g", "maya@example.com", "Sprout123")
        self.client.login(username="maya_g", password="Sprout123")

    def step(self, n, data=None):
        return self.client.post(reverse("userprofile:onboarding", kwargs={"step": n}), data or {})

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("userprofile:onboarding"))
        self.assertRedirects(response, f"{reverse('userprofile:login')}?next={reverse('userprofile:onboarding')}")

    def test_login_sends_unfinished_user_to_onboarding(self):
        self.client.logout()
        response = self.client.post(reverse("userprofile:login"), {"email": "maya@example.com", "password": "Sprout123"})
        self.assertRedirects(response, reverse("userprofile:onboarding"), fetch_redirect_response=False)

    def test_search_lists_places(self):
        from unittest import mock
        with mock.patch("userprofile.views.search_places", return_value=[CHAMPAIGN]) as search:
            response = self.step(1, {"query": " Champaign "})
        search.assert_called_once_with("Champaign")
        self.assertContains(response, "Champaign, Illinois, United States")

    def test_search_failure_shows_friendly_error(self):
        from unittest import mock
        from .services import GeocodingError
        with mock.patch("userprofile.views.search_places", side_effect=GeocodingError("down")):
            response = self.step(1, {"query": "Champaign"})
        self.assertContains(response, "couldn&#x27;t look that up")

    def test_choosing_place_saves_rounded_location(self):
        import json
        place = {k: v for k, v in CHAMPAIGN.items() if k != "label"} | {"latitude": 40.123456, "longitude": -88.249999}
        response = self.step(1, {"place": json.dumps(place)})
        self.assertRedirects(response, reverse("userprofile:onboarding", kwargs={"step": 2}))
        loc = self.user.growing_location
        self.assertEqual((loc.city, str(loc.latitude), str(loc.longitude)), ("Champaign", "40.12000", "-88.25000"))

    def test_garbage_place_is_rejected(self):
        response = self.step(1, {"place": "not json"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(GrowingLocation.objects.exists())

    def test_later_steps_need_a_location(self):
        response = self.client.get(reverse("userprofile:onboarding", kwargs={"step": 3}))
        self.assertRedirects(response, reverse("userprofile:onboarding", kwargs={"step": 1}))

    def test_invalid_choice_is_rejected(self):
        GrowingLocation.objects.create(user=self.user, city="Champaign", latitude="40.12", longitude="-88.24")
        self.assertContains(self.step(2, {"space_type": "moon"}), "Select a valid choice")
        self.assertContains(self.step(2, {}), "Pick the space you will grow in.")

    def test_full_wizard_completes_onboarding(self):
        GrowingLocation.objects.create(user=self.user, city="Champaign", latitude="40.12", longitude="-88.24")
        self.assertRedirects(self.step(2, {"space_type": "balcony"}), reverse("userprofile:onboarding", kwargs={"step": 3}))
        self.assertRedirects(self.step(3, {"sunlight_level": "partial"}), reverse("userprofile:onboarding", kwargs={"step": 4}))
        response = self.step(4, {"experience_level": "some_experience"})
        self.assertRedirects(response, reverse("plants:list"), fetch_redirect_response=False)
        profile = Profile.objects.get(user=self.user)
        self.assertEqual((profile.space_type, profile.sunlight_level, profile.experience_level, profile.onboarding_completed),
                         ("balcony", "partial", "some_experience", True))

    def test_finished_user_skips_wizard_and_logs_in_to_dashboard(self):
        Profile.objects.filter(user=self.user).update(onboarding_completed=True)
        self.assertRedirects(self.client.get(reverse("userprofile:onboarding")), reverse("garden:dashboard"), fetch_redirect_response=False)
        self.client.logout()
        response = self.client.post(reverse("userprofile:login"), {"email": "maya@example.com", "password": "Sprout123"})
        self.assertRedirects(response, reverse("garden:dashboard"), fetch_redirect_response=False)


def _image_upload(name="photo.jpg", fmt="JPEG", size=(1200, 800), exif=False):
    from io import BytesIO
    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image
    buffer = BytesIO()
    image = Image.new("RGB", size, (30, 140, 60))
    if exif:
        data = Image.Exif()
        data[0x010F] = "TestCamera"  # Make
        data[0x8825] = {1: "N", 2: (40.0, 6.0, 58.0)}  # GPS block
        image.save(buffer, fmt, exif=data)
    else:
        image.save(buffer, fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{fmt.lower()}")


class ProfilePageTests(TestCase):
    def setUp(self):
        import shutil, tempfile
        from django.test import override_settings
        self.media = tempfile.mkdtemp()
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        self.user = User.objects.create_user("maya_g", "maya@example.com", "Sprout123")
        Profile.objects.filter(user=self.user).update(onboarding_completed=True, space_type="balcony", sunlight_level="partial")
        self.client.login(username="maya_g", password="Sprout123")
        self.url = reverse("userprofile:profile_edit")

    def form_data(self, **overrides):
        return {"display_name": "Maya", "bio": "Balcony grower", "pronouns": "she/her", "birthdate": "1999-05-04",
                "space_type": "balcony", "sunlight_level": "partial", "experience_level": "beginner", "units": "metric", **overrides}

    def test_pages_require_login(self):
        self.client.logout()
        for name in ("profile", "profile_edit", "location_edit"):
            response = self.client.get(reverse(f"userprofile:{name}"))
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("userprofile:login"), response["Location"])

    def test_profile_page_shows_details(self):
        GrowingLocation.objects.create(user=self.user, city="Champaign", region="Illinois", latitude="40.12", longitude="-88.24")
        response = self.client.get(reverse("userprofile:profile"))
        self.assertContains(response, "@maya_g")
        self.assertContains(response, "Champaign, Illinois")
        self.assertContains(response, "Balcony")

    def test_edit_saves_fields(self):
        response = self.client.post(self.url, self.form_data())
        self.assertRedirects(response, reverse("userprofile:profile"))
        profile = Profile.objects.get(user=self.user)
        self.assertEqual((profile.display_name, profile.bio, profile.pronouns, str(profile.birthdate)), ("Maya", "Balcony grower", "she/her", "1999-05-04"))

    def test_edit_rejects_future_birthday_and_blank_space(self):
        response = self.client.post(self.url, self.form_data(birthdate="2999-01-01", space_type=""))
        self.assertContains(response, "Birthday can&#x27;t be in the future.")
        self.assertContains(response, "This field is required.")

    def test_header_uses_real_user_not_mock(self):
        Profile.objects.filter(user=self.user).update(display_name="Maya Real")
        response = self.client.get(reverse("userprofile:profile"))
        self.assertContains(response, "Maya Real")
        self.assertNotContains(response, "balcony_maya")

    def test_avatar_is_reencoded_resized_and_stripped_of_exif(self):
        from PIL import Image
        upload = _image_upload(size=(2000, 1000), exif=True)
        self.assertTrue(Image.open(upload).getexif())  # sanity: source has metadata
        upload.seek(0)
        self.client.post(self.url, self.form_data(avatar=upload))
        avatar = Profile.objects.get(user=self.user).avatar
        self.assertTrue(avatar.name.startswith("avatars/") and avatar.name.endswith(".jpg"))
        saved = Image.open(avatar.path)
        self.assertEqual(max(saved.size), 512)
        self.assertEqual(len(saved.getexif()), 0)

    def test_avatar_rejects_non_images_and_wrong_formats(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake = SimpleUploadedFile("evil.jpg", b"<?php echo 1; ?>", content_type="image/jpeg")
        self.assertContains(self.client.post(self.url, self.form_data(avatar=fake)), "valid image")
        gif = _image_upload("a.gif", "GIF")
        self.assertContains(self.client.post(self.url, self.form_data(avatar=gif)), "JPEG, PNG, or WebP")
        self.assertFalse(Profile.objects.get(user=self.user).avatar)

    def test_avatar_over_10mb_rejected(self):
        from unittest import mock
        upload = _image_upload()
        with mock.patch("userprofile.services.AVATAR_MAX_BYTES", 10):
            response = self.client.post(self.url, self.form_data(avatar=upload))
        self.assertContains(response, "over 10 MB")

    def test_replacing_and_removing_avatar_deletes_old_file(self):
        import os
        self.client.post(self.url, self.form_data(avatar=_image_upload()))
        first = Profile.objects.get(user=self.user).avatar.path
        self.assertTrue(os.path.exists(first))
        self.client.post(self.url, self.form_data(avatar=_image_upload("b.jpg")))
        second = Profile.objects.get(user=self.user).avatar.path
        self.assertNotEqual(first, second)
        self.assertFalse(os.path.exists(first))
        self.client.post(self.url, self.form_data(**{"avatar-clear": "on"}))
        self.assertFalse(Profile.objects.get(user=self.user).avatar)
        self.assertFalse(os.path.exists(second))

    def test_saving_without_new_file_keeps_avatar(self):
        self.client.post(self.url, self.form_data(avatar=_image_upload()))
        name = Profile.objects.get(user=self.user).avatar.name
        self.client.post(self.url, self.form_data(bio="Updated"))
        self.assertEqual(Profile.objects.get(user=self.user).avatar.name, name)

    def test_change_location_after_onboarding(self):
        import json
        from unittest import mock
        with mock.patch("userprofile.views.search_places", return_value=[CHAMPAIGN]):
            self.assertContains(self.client.post(reverse("userprofile:location_edit"), {"query": "Champaign"}), "Champaign, Illinois")
        place = {k: v for k, v in CHAMPAIGN.items() if k != "label"}
        response = self.client.post(reverse("userprofile:location_edit"), {"place": json.dumps(place)})
        self.assertRedirects(response, reverse("userprofile:profile"))
        self.assertEqual(self.user.growing_location.city, "Champaign")


class AccessControlTests(TestCase):
    """Every app page needs a signed-in user; only the landing and auth pages are public."""
    PAGES = ["garden:dashboard", "garden:my_garden", "plants:list", "weather:index", "community:feed", "tutor:ask"]

    def test_anonymous_is_sent_to_login_with_next(self):
        for name in self.PAGES:
            url = reverse(name)
            response = self.client.get(url)
            self.assertRedirects(response, f"{reverse('userprofile:login')}?next={url}", fetch_redirect_response=False, msg_prefix=name)

    def test_detail_and_actions_are_protected(self):
        for method, url in [("get", reverse("plants:detail", args=["basil"])), ("post", reverse("plants:start", args=["basil"])),
                            ("post", reverse("community:create")), ("post", reverse("community:like", args=[1])),
                            ("post", reverse("community:report", args=[1])), ("post", reverse("community:comment", args=[1]))]:
            response = getattr(self.client, method)(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertIn(reverse("userprofile:login"), response["Location"], url)

    def test_signed_in_user_can_open_pages(self):
        User.objects.create_user("maya_g", "maya@example.com", "Sprout123")
        self.client.login(username="maya_g", password="Sprout123")
        for name in self.PAGES:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_landing_and_auth_pages_stay_public(self):
        for name in ("landing", "userprofile:login", "userprofile:signup", "userprofile:password_reset"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
=======
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
>>>>>>> ce515f7437e8d5811a6b3a8dd968ddea18c7d2f5
