from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from plants.models import Plant

STATUS_CHOICES = [(s, s.capitalize()) for s in (
    "planned", "sprouting", "growing", "flowering", "fruiting", "harvested", "failed", "archived")]
SETTING_CHOICES = [(s, s.capitalize()) for s in ("outdoor", "indoor", "greenhouse")]
SEVERITY_CHOICES = [(s, s.capitalize()) for s in ("low", "medium", "high")]
PROBLEM_CATEGORIES = [(c, c.capitalize()) for c in ("pest", "disease", "nutrient", "watering", "environment", "unknown")]


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
    nickname = models.CharField(max_length=60, blank=True, default="")
    planted_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="growing")
    setting = models.CharField(max_length=20, choices=SETTING_CHOICES, default="outdoor")

    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="garden_instances")

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="my_garden_plants")

    class Meta:
        ordering = ['-added_at']
        constraints = [

            models.UniqueConstraint(fields=['user', 'plant'], name='unique_user_plant_entry')
        ]

    def __str__(self):
        return f"{self.user.username}'s {self.plant.plant_name}"

    @property
    def label(self):
        return self.nickname or self.plant.plant_name


class CareLog(models.Model):
    """One care event on a garden plant (PRD FR-22)."""
    ACTIONS = [(a, a.replace("_", " ").capitalize()) for a in (
        "water", "fertilize", "prune", "repot", "treat_pest", "transplant", "other")]

    garden = models.ForeignKey(Garden, on_delete=models.CASCADE, related_name="care_logs")
    action = models.CharField(max_length=20, choices=ACTIONS)
    amount = models.CharField(max_length=50, blank=True, default="")
    note = models.TextField(blank=True, default="")
    performed_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-performed_at"]


class TimelineEntry(models.Model):
    """A growth-stage note on a garden plant (PRD FR-21)."""
    STAGES = [(s, s.capitalize()) for s in ("seed", "seedling", "vegetative", "flowering", "fruiting", "harvest")]

    garden = models.ForeignKey(Garden, on_delete=models.CASCADE, related_name="timeline_entries")
    stage = models.CharField(max_length=20, choices=STAGES)
    photo = models.ImageField(upload_to="timeline/", null=True, blank=True)
    note = models.TextField(blank=True, default="")
    recorded_on = models.DateField(default=timezone.localdate, db_index=True)

    class Meta:
        ordering = ["-recorded_on"]
        verbose_name_plural = "timeline entries"


class Problem(models.Model):
    """An issue on a garden plant (PRD FR-25); AI diagnoses can be saved here."""
    STATUSES = [(s, s.capitalize()) for s in ("open", "monitoring", "resolved")]

    garden = models.ForeignKey(Garden, on_delete=models.CASCADE, related_name="problems")
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    photo = models.ImageField(upload_to="problems/", null=True, blank=True)
    category = models.CharField(max_length=20, choices=PROBLEM_CATEGORIES, default="unknown")
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="medium")
    status = models.CharField(max_length=20, choices=STATUSES, default="open")
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Harvest(models.Model):
    """A harvest entry; with status "harvested" it counts toward the North Star (PRD 1.5)."""
    UNITS = [(u, u) for u in ("g", "kg", "oz", "lb", "count", "bunch")]

    garden = models.ForeignKey(Garden, on_delete=models.CASCADE, related_name="harvests")
    harvested_on = models.DateField(default=timezone.localdate)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=10, choices=UNITS, default="count")
    note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-harvested_on"]
