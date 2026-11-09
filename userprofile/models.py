from django.db import models
from django.urls import reverse
from django.contrib.auth.models import User


class Profile(models.Model):
    """
    Per-user profile and growing context (PRD FR-02/FR-04). Created automatically for every user
    (see signals.py). Location lives in GrowingLocation; onboarding_completed flips to True when
    the onboarding wizard finishes.
    """

    class Experience(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        SOME = "some_experience", "Some experience"
        EXPERIENCED = "experienced", "Experienced"

    class Space(models.TextChoices):
        BACKYARD = "backyard", "Backyard"
        BALCONY = "balcony", "Balcony"
        WINDOWSILL = "windowsill", "Windowsill"
        INDOOR = "indoor", "Indoor"
        COMMUNITY_GARDEN = "community_garden", "Community garden"

    class Sunlight(models.TextChoices):
        FULL_SUN = "full_sun", "Full sun"
        PARTIAL = "partial", "Partial sun"
        SHADE = "shade", "Shade"

    class Units(models.TextChoices):
        METRIC = "metric", "Metric"
        IMPERIAL = "imperial", "Imperial"

    profile_id = models.AutoField(primary_key=True)
    display_name = models.CharField(max_length=60, blank=True, default="")
    avatar = models.ImageField(upload_to="avatars/", blank=True)
    bio = models.TextField(max_length=500, blank=True, default="")
    birthdate = models.DateField(null=True, blank=True)
    pronouns = models.CharField(max_length=30, blank=True, default="")
    experience_level = models.CharField(max_length=20, choices=Experience.choices, default=Experience.BEGINNER)
    space_type = models.CharField(max_length=20, choices=Space.choices, blank=True, default="")
    sunlight_level = models.CharField(max_length=20, choices=Sunlight.choices, blank=True, default="")
    units = models.CharField(max_length=10, choices=Units.choices, default=Units.METRIC)
    notification_prefs = models.JSONField(default=dict, blank=True)
    onboarding_completed = models.BooleanField(default=False)

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_related_profile')

    def get_absolute_url(self):
        return reverse('userprofile:profile')

    class Meta:
        ordering = ['profile_id']

    def __str__(self):
        return f"{self.user.username}'s Profile"


class GrowingLocation(models.Model):
    """
    Where a user grows (PRD FR-03). Stored at city precision: latitude/longitude are rounded to
    5 decimals at most, and are used for weather and climate lookups.
    """
    location_id = models.AutoField(primary_key=True)
    city = models.CharField(max_length=100)
    region = models.CharField(max_length=100, blank=True, default="")
    country_code = models.CharField(max_length=2, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    latitude = models.DecimalField(max_digits=8, decimal_places=5)
    longitude = models.DecimalField(max_digits=8, decimal_places=5)
    timezone = models.CharField(max_length=50, blank=True, default="")

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='growing_location')

    def __str__(self):
        return f"{self.user.username}: {self.city}"
