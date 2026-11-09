from django.db import models


class Plant(models.Model):
    """
    A plant species in the shared catalog (PRD 7.2 plants.Plant). Curated by the `curator` role in
    Django admin; seeded with `python manage.py seed_plants`.
    """

    class Category(models.TextChoices):
        HERB = "herb", "Herb"
        LEAFY_GREEN = "leafy_green", "Leafy green"
        VEGETABLE = "vegetable", "Vegetable"
        FRUIT = "fruit", "Fruit"
        ROOT = "root", "Root"
        LEGUME = "legume", "Legume"

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    class Sunlight(models.TextChoices):
        FULL_SUN = "full_sun", "Full sun"
        PARTIAL = "partial", "Partial sun"
        SHADE = "shade", "Shade"

    class HarvestMode(models.TextChoices):
        SINGLE = "single", "Single harvest"
        CONTINUOUS = "continuous", "Continuous harvest"

    plant_id = models.AutoField(primary_key=True)
    common_name = models.CharField(max_length=100, unique=True)
    scientific_name = models.CharField(max_length=150, blank=True)
    slug = models.SlugField(max_length=100, unique=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.VEGETABLE)
    usage_type = models.CharField(max_length=60, blank=True)
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, default=Difficulty.EASY)
    description = models.TextField(blank=True)

    # Care requirements (FR-11)
    sunlight_requirement = models.CharField(max_length=10, choices=Sunlight.choices, default=Sunlight.FULL_SUN)
    watering_interval_days = models.PositiveSmallIntegerField(default=3)
    min_temp_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    max_temp_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    frost_tolerant = models.BooleanField(default=False)
    frost_threshold_c = models.DecimalField(max_digits=4, decimal_places=1, default=2.0)
    days_to_germination_min = models.PositiveSmallIntegerField(null=True, blank=True)
    days_to_germination_max = models.PositiveSmallIntegerField(null=True, blank=True)
    days_to_harvest_min = models.PositiveSmallIntegerField(null=True, blank=True)
    days_to_harvest_max = models.PositiveSmallIntegerField(null=True, blank=True)
    spacing_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    container_friendly = models.BooleanField(default=False)
    indoor_friendly = models.BooleanField(default=False)
    harvest_mode = models.CharField(max_length=10, choices=HarvestMode.choices, default=HarvestMode.CONTINUOUS)

    # Climate (FR-12). JSON instead of ArrayField so the model also runs on SQLite in tests.
    hardiness_zones = models.JSONField(default=list, blank=True, help_text='Perennials only, e.g. ["4", "5", "6"]')
    planting_months = models.JSONField(default=dict, blank=True,
                                       help_text='Outdoor planting months by zone, e.g. {"5b": [4, 5, 6]}; empty list = indoors any time')

    care_guide = models.TextField(blank=True, help_text="One care tip per line")
    external_source_id = models.CharField(max_length=40, blank=True, help_text="Perenual species id")
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["common_name"]

    def __str__(self):
        return self.common_name

    @property
    def care_tips(self):
        return [line.strip() for line in self.care_guide.splitlines() if line.strip()]


class PlantProblemSummary(models.Model):
    """Common problems for a plant (PRD 7.2; P1 AI-summarized from community data, curated for now)."""

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="problem_summaries")
    problem_name = models.CharField(max_length=120)
    symptoms = models.TextField()
    solution = models.TextField()
    source_count = models.PositiveIntegerField(default=0)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-source_count", "problem_name"]
        verbose_name_plural = "plant problem summaries"

    def __str__(self):
        return f"{self.plant}: {self.problem_name}"
