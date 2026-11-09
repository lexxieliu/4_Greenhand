from django.db.models.signals import post_save
from django.dispatch import receiver

from garden.models import Garden

from .models import ChatMessage, ChatSession

WELCOME = (
    "Congratulations on starting {label}! Three things help most in the first week: keep it where it gets the light "
    "it likes, check the soil with a finger before watering, and log each watering so I can give advice that fits. "
    "Ask me anything along the way, or send a photo if something looks wrong."
)


@receiver(post_save, sender=Garden)
def welcome_first_plant(sender, instance, created, raw=False, **kwargs):
    """Tutor welcome after the user's first plant (PRD 4.1). A template, so adding a plant never waits on the model."""
    if not created or raw or Garden.objects.filter(user=instance.user).exclude(pk=instance.pk).exists():
        return
    session = ChatSession.objects.create(user=instance.user, scoped_plant=instance, title=f"Welcome, {instance.label} grower")
    ChatMessage.objects.create(session=session, role="assistant", model_name="welcome",
                               content=WELCOME.format(label=instance.label))
