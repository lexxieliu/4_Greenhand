"""Garden events are tracked at the model level, so every entry point (forms, admin, API) is counted."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from garden.models import CareLog, Harvest, TimelineEntry, UserPlant

from .services import track


@receiver(post_save, sender=UserPlant)
def plant_started(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        track("plant_started", instance.user, user_plant_id=instance.pk)


@receiver(post_save, sender=CareLog)
def care_logged(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        track("care_logged", instance.user_plant.user, action=instance.action)


@receiver(post_save, sender=TimelineEntry)
def timeline_added(sender, instance, created, raw=False, **kwargs):
    if created and not raw and instance.photo:
        track("photo_uploaded", instance.user_plant.user, user_plant_id=instance.user_plant_id)


@receiver(post_save, sender=Harvest)
def harvest_logged(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        track("harvest_logged", instance.user_plant.user, user_plant_id=instance.user_plant_id)
