from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse


class Profile(models.Model):
    profile_id = models.AutoField(primary_key=True)
    bio = models.TextField(max_length=500, blank=True, default="")
    birthdate = models.DateField(null=True, blank=True)
    pronouns = models.CharField(max_length=30, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    region = models.CharField(max_length=100, blank=True, default="")
    latitude = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)
    longitude = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)
    hardiness_zone = models.CharField(max_length=5, blank=True, default="")
    space_type = models.CharField(max_length=20, blank=True, default="", choices=[
        (s, s.capitalize()) for s in ("backyard", "balcony", "windowsill", "indoor")])
    sunlight_level = models.CharField(max_length=20, blank=True, default="", choices=[
        ("full_sun", "Full sun"), ("partial", "Partial"), ("shade", "Shade")])
    experience_level = models.CharField(max_length=20, blank=True, default="", choices=[
        ("beginner", "Beginner"), ("some_experience", "Some experience"), ("experienced", "Experienced")])

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_related_profile')

    def get_absolute_url(self):
        return reverse('profile-detail-url', kwargs={'primary_key': self.pk})

    class Meta:
        ordering = ['profile_id']

    def __str__(self):
        return f"{self.user.username}'s Profile"
