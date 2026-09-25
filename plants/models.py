from django.db import models

# Create your models here.
class Plant(models.Model):
    """
    Represents a master plant species in the shared plant encyclopedia.
    """
    plant_id = models.AutoField(primary_key=True)
    plant_name = models.CharField(max_length=60, unique=True)
    scientific_name = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=30)
    usage_type = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ['plant_name']

    def __str__(self):
        return f"{self.plant_name} ({self.category})"