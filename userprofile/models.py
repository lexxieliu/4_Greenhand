from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):

    profile_id = models.AutoField(primary_key=True)
    bio = models.TextField(max_length=500, blank=True, default="")
    birthdate = models.DateField(null=True, blank=True)
    pronouns = models.CharField(max_length=30, blank=True, default="")

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    class Meta:
        ordering = ['profile_id']

    def __str__(self):
        return f"{self.user.username}'s Profile"
