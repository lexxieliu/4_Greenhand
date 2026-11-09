"""Garden events are tracked at the model level, so every entry point (forms, admin, API) is counted."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from garden.models import CareLog, Garden, Harvest, TimelineEntry

from .services import track


@receiver(post_save, sender=Garden)
def plant_started(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        track("plant_started", instance.user, garden_id=instance.pk)


@receiver(post_save, sender=CareLog)
def care_logged(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        track("care_logged", instance.garden.user, action=instance.action)


@receiver(post_save, sender=TimelineEntry)
def timeline_added(sender, instance, created, raw=False, **kwargs):
    if created and not raw and instance.photo:
        track("photo_uploaded", instance.garden.user, garden_id=instance.garden_id)


@receiver(post_save, sender=Harvest)
def harvest_logged(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        track("harvest_logged", instance.garden.user, garden_id=instance.garden_id)
