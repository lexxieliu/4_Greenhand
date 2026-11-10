"""Load the mock data into the database and create two accounts to try the app with.

    python manage.py seed_mock_data            # add what is missing, never overwrite
    python manage.py seed_mock_data --reset    # also rebuild balcony_maya's garden and the mock posts

Loads: the plant catalog (seed_plants), the demo garden for balcony_maya (garden/demo_data.py) and the
community posts, comments, likes and saves from greenhand/mock_data.py. Weather and notifications are not
stored in the database; the app still reads them from mock_data.
"""
import re
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from community.models import Comment, Post, PostLike, PostSave
from garden.models import UserPlant
from greenhand import mock_data
from greenhand.clock import now as clock_now
from plants.models import Plant
from userprofile.models import GrowingLocation, Profile

DEFAULT_PASSWORD = "Sprout123"

# The two accounts that can sign in (email + password). Maya owns the demo garden; Dave starts with an empty one.
LOGIN_ACCOUNTS = [
    {"username": "balcony_maya", "email": "maya@example.com", "display_name": "Maya", "pronouns": "she/her",
     "bio": "Renter growing herbs and tomatoes on a Chicago balcony.", "experience_level": "beginner",
     "space_type": "balcony", "sunlight_level": "partial",
     "city": "Chicago", "region": "IL", "lat": "41.88000", "lon": "-87.63000", "tz": "America/Chicago"},
    {"username": "backyard_dave", "email": "dave@example.com", "display_name": "Dave", "pronouns": "he/him",
     "bio": "Homeowner turning the backyard into a vegetable patch.", "experience_level": "some_experience",
     "space_type": "backyard", "sunlight_level": "full_sun",
     "city": "Naperville", "region": "IL", "lat": "41.78600", "lon": "-88.14700", "tz": "America/Chicago"},
]

_AGE_UNITS = {"m": "minutes", "h": "hours", "d": "days", "w": "weeks"}


def _ago(text):
    """'45m', '2h', '3d', '3w' (as written in mock_data) -> a datetime on the app's "today"."""
    amount, unit = re.fullmatch(r"(\d+)([mhdw])", text).groups()
    return clock_now() - timedelta(**{_AGE_UNITS[unit]: int(amount)})


class Command(BaseCommand):
    help = "Seed the plant catalog, demo garden, community posts and two sign-in accounts (safe to run again)."

    def add_arguments(self, parser):
        parser.add_argument("--password", default=DEFAULT_PASSWORD, help=f"Password for the two accounts (default {DEFAULT_PASSWORD}).")
        parser.add_argument("--reset", action="store_true", help="Rebuild balcony_maya's garden and the mock posts.")

    @transaction.atomic
    def handle(self, *args, password, reset, **options):
        call_command("seed_plants", stdout=self.stdout)
        users = self._users(password)
        self._garden(users["balcony_maya"], reset)
        self._posts(users, reset)
        self.stdout.write(self.style.SUCCESS("Sign in with maya@example.com or dave@example.com."))

    def _users(self, password):
        users = {}
        for spec in LOGIN_ACCOUNTS:
            user, _ = User.objects.get_or_create(username=spec["username"], defaults={"email": spec["email"]})
            user.email = spec["email"]
            user.set_password(password)
            user.save()
            Profile.objects.update_or_create(user=user, defaults={
                "display_name": spec["display_name"], "pronouns": spec["pronouns"], "bio": spec["bio"],
                "experience_level": spec["experience_level"], "space_type": spec["space_type"],
                "sunlight_level": spec["sunlight_level"], "onboarding_completed": True})
            GrowingLocation.objects.update_or_create(user=user, defaults={
                "city": spec["city"], "region": spec["region"], "country_code": "US", "latitude": spec["lat"],
                "longitude": spec["lon"], "timezone": spec["tz"]})
            users[user.username] = user
        # The other post authors only exist so the feed has names; nobody can sign in as them.
        for username in mock_data.AUTHORS:
            if username not in users:
                user, created = User.objects.get_or_create(username=username)
                if created:
                    user.set_unusable_password()
                    user.save()
                users[username] = user
        return users

    def _garden(self, maya, reset):
        if reset or not UserPlant.objects.filter(user=maya).exists():
            call_command("seed_demo_garden", stdout=self.stdout)
        else:
            self.stdout.write("balcony_maya already has plants; keeping them (use --reset to rebuild).")

    def _posts(self, users, reset):
        authors = [users[name] for name in mock_data.AUTHORS]
        if reset:
            Post.objects.filter(author__in=authors).delete()
        elif Post.objects.filter(author__in=authors).exists():
            self.stdout.write("Mock posts already exist; keeping them (use --reset to rebuild).")
            return
        plants = {p.slug: p for p in Plant.objects.all()}
        maya = users["balcony_maya"]
        for row in reversed(mock_data.POSTS):  # oldest first, so ids follow the timeline
            post = Post.objects.create(author=users[row["author"]], plant=plants.get(row["plant_slug"]),
                                       post_type=row["post_type"], body=row["body"], ai_suggestion=row["ai_suggestion"])
            Post.objects.filter(pk=post.pk).update(created_at=_ago(row["created"]))
            for c in row["comments"]:
                comment = Comment.objects.create(post=post, author=users[c["author"]], body=c["body"])
                Comment.objects.filter(pk=comment.pk).update(created_at=_ago(c["created"]))
            if row["liked"]:
                PostLike.objects.create(user=maya, post=post)
            if row["saved"]:
                PostSave.objects.create(user=maya, post=post)
        self.stdout.write(self.style.SUCCESS(f"{len(mock_data.POSTS)} mock posts created."))
