from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    """
    Extends the built-in Django User model with additional personal details.
    Stores customizable user attributes such as biography, birthday, and pronouns.
    We use one to one field to make a relationship with the user model, and use cascade rule so if the user got deleted
    the profile also deleted
    """
    profile_id = models.AutoField(primary_key=True)
    bio = models.TextField(max_length=500, blank=True, default="")
    birthdate = models.DateField(null=True, blank=True)
    pronouns = models.CharField(max_length=30, blank=True, default="")

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    class Meta:
        ordering = ['profile_id']

    def __str__(self):
        return f"{self.user.username}'s Profile"
