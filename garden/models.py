from django.db import models
from django.contrib.auth.models import User
from plants.models import Plant

# Create your models here.
class Garden(models.Model):
    """
    Represents an individual plant instance tracked in a user's personal garden workspace.
    We use 2 foreignkey which is plant and user, since we need to list some plants in the garden,
    and each garden is related to each user, for plants, we allow to preserve list of plants if the garden is deleted
    but for user, we use cascade since we want each garden is deleted if the user delete its account
    """
    garden_id = models.AutoField(primary_key=True)
    progress = models.CharField(max_length=30, default="Seedling")
    added_at = models.DateTimeField(auto_now_add=True)


    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="garden_instances")

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="my_garden_plants")

    class Meta:
        ordering = ['-added_at']
        constraints = [

            models.UniqueConstraint(fields=['user', 'plant'], name='unique_user_plant_entry')
        ]

    def __str__(self):
        return f"{self.user.username}'s {self.plant.plant_name}"