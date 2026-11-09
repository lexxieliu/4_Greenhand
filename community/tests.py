from io import BytesIO
from unittest import mock

from django.contrib.admin.sites import site
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import reverse
from PIL import Image

from analytics.models import AnalyticsEvent
from garden.models import UserPlant
from greenhand.clock import today
from plants.models import Plant

from . import services, views
from .admin import ReportAdmin
from .models import Comment, Post, PostImage, PostLike, PostSave, Report


def photo(name="p.jpg"):
    buffer = BytesIO()
    Image.new("RGB", (50, 50), "red").save(buffer, "JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


class CommunityBase(TestCase):
    def setUp(self):
        cache.clear()
        self.me = User.objects.create_user("me", "me@example.com", "pass12345")
        self.them = User.objects.create_user("them", "them@example.com", "pass12345")
        self.basil = Plant.objects.create(common_name="Basil", slug="basil")
        self.kale = Plant.objects.create(common_name="Kale", slug="kale")
        self.garden = self.grow(self.me, self.basil, "Balcony Basil")
        self.client.force_login(self.me)
        self.feed = reverse("community:feed")

    def grow(self, user, plant, nickname):
        return UserPlant.objects.create(user=user, plant=plant, nickname=nickname, planted_on=today(), watering_interval_days=3)

    def post(self, author=None, plant=None, **fields):
        return Post.objects.create(author=author or self.them, plant=plant, body=fields.pop("body", "Hello growers"), **fields)


class FeedTests(CommunityBase):
    def test_hidden_posts_and_comments_are_not_shown(self):
        self.post(body="visible post")
        self.post(body="hidden post", is_hidden=True)
        Comment.objects.create(post=Post.objects.get(body="visible post"), author=self.them, body="hidden comment", is_hidden=True)
        response = self.client.get(self.feed)
        self.assertContains(response, "visible post")
        self.assertNotContains(response, "hidden post")
        self.assertNotContains(response, "hidden comment")

    def test_same_plants_filter(self):
        self.post(plant=self.basil, body="about basil")
        self.post(plant=self.kale, body="about kale")
        response = self.client.get(self.feed, {"feed": "same"})
        self.assertContains(response, "about basil")
        self.assertNotContains(response, "about kale")

    def test_saved_and_type_filters(self):
        saved = self.post(body="keep this", post_type="tip")
        self.post(body="other one", post_type="question")
        PostSave.objects.create(user=self.me, post=saved)
        self.assertNotContains(self.client.get(self.feed, {"feed": "saved"}), "other one")
        self.assertNotContains(self.client.get(self.feed, {"type": "tip"}), "other one")

    def test_anonymous_is_sent_to_login_and_cannot_write(self):
        post = self.post(body="public post")
        self.client.logout()                       # team decision (Area 1): every app page needs sign-in
        self.assertEqual(self.client.get(self.feed).status_code, 302)
        self.assertEqual(self.client.post(reverse("community:create"), {"body": "x"}).status_code, 302)
        self.assertEqual(self.client.post(reverse("community:like", args=[post.pk])).status_code, 302)
        self.assertEqual(Post.objects.count(), 1)

    def test_images_render_with_alt_text(self):
        post = self.post()
        PostImage.objects.create(post=post, image="posts/a.jpg", alt_text="A leafy basil plant")
        self.assertContains(self.client.get(self.feed), 'alt="A leafy basil plant"')
        PostImage.objects.update(alt_text="")
        self.assertContains(self.client.get(self.feed), 'alt="Photo shared by them"')


class CreatePostTests(CommunityBase):
    def _create(self, **fields):
        return self.client.post(reverse("community:create"), {"body": "New post", "post_type": "progress", **fields})

    def test_links_own_plant_and_tracks_event(self):
        self._create(user_plant=self.garden.pk)
        post = Post.objects.get()
        self.assertEqual((post.author, post.user_plant, post.plant), (self.me, self.garden, self.basil))
        self.assertTrue(AnalyticsEvent.objects.filter(name="post_created", user=self.me).exists())

    def test_cannot_link_another_users_plant(self):
        theirs = self.grow(self.them, self.kale, "Kale")
        self._create(user_plant=theirs.pk)
        self.assertIsNone(Post.objects.get().user_plant)

    def test_at_most_four_images_and_alt_text_saved(self):
        self._create(images=[photo(f"{i}.jpg") for i in range(6)], image_alt="Seedlings")
        self.assertEqual(PostImage.objects.count(), 4)
        self.assertEqual(PostImage.objects.first().alt_text, "Seedlings")

    def test_bad_image_rejects_the_post(self):
        self._create(images=[SimpleUploadedFile("x.jpg", b"nope", content_type="image/jpeg")])
        self.assertFalse(Post.objects.exists())

    def test_empty_body_rejected_and_bad_type_defaults(self):
        self._create(body="  ")
        self.assertFalse(Post.objects.exists())
        self._create(post_type="spam")
        self.assertEqual(Post.objects.get().post_type, "progress")

    def test_daily_limit(self):
        with mock.patch.object(views, "DAILY_POST_LIMIT", 1):
            self._create()
            self._create()
        self.assertEqual(Post.objects.count(), 1)

    def test_question_schedules_ai_suggestion_others_do_not(self):
        with mock.patch.object(views, "schedule_ai_suggestion") as schedule:
            self._create(post_type="tip")
            schedule.assert_not_called()
            self._create(post_type="question")
            schedule.assert_called_once()


class AiSuggestionTests(CommunityBase):
    @mock.patch.object(services, "suggest_for_post", return_value="Check drainage.")
    def test_suggestion_is_saved_and_labeled(self, suggest):
        post = self.post(plant=self.basil, post_type="question")
        services.attach_ai_suggestion(post.pk)
        suggest.assert_called_once_with("Hello growers", "Basil")
        response = self.client.get(self.feed)
        self.assertContains(response, "Check drainage.")
        self.assertContains(response, "AI suggestion")

    @mock.patch.object(services, "suggest_for_post", return_value="")
    def test_no_suggestion_leaves_post_unchanged(self, _):
        post = self.post(post_type="question")
        services.attach_ai_suggestion(post.pk)
        post.refresh_from_db()
        self.assertEqual(post.ai_suggestion, "")


class InteractionTests(CommunityBase):
    def test_like_toggles(self):
        url = reverse("community:like", args=[self.post().pk])
        self.assertEqual(self.client.post(url).json(), {"active": True, "count": 1})
        self.assertEqual(self.client.post(url).json(), {"active": False, "count": 0})
        self.assertFalse(PostLike.objects.exists())

    def test_save_toggles(self):
        url = reverse("community:save", args=[self.post().pk])
        self.assertTrue(self.client.post(url).json()["active"])
        self.assertTrue(PostSave.objects.filter(user=self.me).exists())

    def test_comment_is_added_and_tracked(self):
        post = self.post()
        self.client.post(reverse("community:comment", args=[post.pk]), {"body": "Nice!"})
        self.assertEqual(Comment.objects.get().author, self.me)
        self.assertTrue(AnalyticsEvent.objects.filter(name="comment_created").exists())

    def test_hidden_post_rejects_interactions(self):
        post = self.post(is_hidden=True)
        for name, data in (("like", {}), ("comment", {"body": "x"}), ("report", {"reason": "spam"})):
            self.assertEqual(self.client.post(reverse(f"community:{name}", args=[post.pk]), data).status_code, 404)


class ModerationTests(CommunityBase):
    def _admin_action(self, name, reports):
        admin = ReportAdmin(Report, site)
        getattr(admin, name)(RequestFactory().post("/"), reports)

    def test_report_post_once_per_user(self):
        post = self.post()
        url = reverse("community:report", args=[post.pk])
        self.client.post(url, {"reason": "spam"})
        self.client.post(url, {"reason": "other"})
        report = Report.objects.get()
        self.assertEqual((report.target, report.reason, report.status), (post, "spam", "open"))

    def test_report_comment_and_invalid_reason(self):
        comment = Comment.objects.create(post=self.post(), author=self.them, body="rude")
        url = reverse("community:report_comment", args=[comment.pk])
        self.client.post(url, {"reason": "bad-value"})
        self.assertFalse(Report.objects.exists())
        self.client.post(url, {"reason": "harassment"})
        self.assertEqual(Report.objects.get().target, comment)

    def _report(self, target):
        return Report.objects.create(reporter=self.me, content_type=ContentType.objects.get_for_model(target),
                                     object_id=target.pk, reason="spam")

    def test_admin_hide_action_removes_content_from_feed(self):
        post = self.post(body="bad advice")
        self._report(post)
        self._admin_action("hide_content", Report.objects.all())
        post.refresh_from_db()
        self.assertTrue(post.is_hidden)
        self.assertEqual(Report.objects.get().status, "actioned")
        self.assertNotContains(self.client.get(self.feed), "bad advice")

    def test_admin_dismiss_keeps_content(self):
        post = self.post()
        self._report(post)
        self._admin_action("dismiss", Report.objects.all())
        post.refresh_from_db()
        self.assertFalse(post.is_hidden)
        self.assertEqual(Report.objects.get().status, "dismissed")

    def test_queue_page_works_for_staff_only(self):
        self._report(self.post(body="queued text"))
        url = reverse("admin:community_report_changelist")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(User.objects.create_superuser("mod", "mod@example.com", "pass12345"))
        self.assertContains(self.client.get(url), "queued text")
