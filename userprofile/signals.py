from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """Every new user gets a Profile so the rest of the app can rely on user.user_related_profile."""
    if created:
        Profile.objects.get_or_create(user=instance)
