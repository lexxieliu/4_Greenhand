"""My Garden data (PRD 7.2 garden app, plus the Reminder tables the care schedule needs).

Every model hangs off UserPlant, and every query in services/selectors filters by the owner, so a
user can only ever see or change their own garden.
"""
from django.contrib.auth.models import User
from django.db import models

from plants.models import Plant


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserPlant(TimeStampedModel):
    """One plant (or batch, see quantity) in a user's garden."""

    class StartMethod(models.TextChoices):
        SEED = "seed", "Seed"
        SEEDLING = "seedling", "Seedling"
        CUTTING = "cutting", "Cutting"

    class Setting(models.TextChoices):
        OUTDOOR = "outdoor", "Outdoor"
        INDOOR = "indoor", "Indoor"
        GREENHOUSE = "greenhouse", "Greenhouse"

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        SPROUTING = "sprouting", "Sprouting"
        GROWING = "growing", "Growing"
        FLOWERING = "flowering", "Flowering"
        FRUITING = "fruiting", "Fruiting"
        PRODUCING = "producing", "Producing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        ARCHIVED = "archived", "Archived"

    class StatusSource(models.TextChoices):
        AUTO = "auto", "Automatic"
        USER = "user", "Set by user"

    class FailureReason(models.TextChoices):
        DISEASE = "disease", "Disease"
        PEST = "pest", "Pests"
        WATERING_ERROR = "watering_error", "Watering error"
        FROST = "frost", "Frost"
        INSUFFICIENT_LIGHT = "insufficient_light", "Not enough light"
        OTHER = "other", "Other"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_plants")
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="user_plants")
    nickname = models.CharField(max_length=60)
    variety = models.CharField(max_length=100, blank=True)
    planted_on = models.DateField()
    start_method = models.CharField(max_length=10, choices=StartMethod.choices, default=StartMethod.SEED)
    setting = models.CharField(max_length=10, choices=Setting.choices, default=Setting.OUTDOOR)
    container_type = models.CharField(max_length=50, blank=True)
    quantity = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANNED)
    status_source = models.CharField(max_length=4, choices=StatusSource.choices, default=StatusSource.AUTO)
    current_stage_updated_at = models.DateTimeField(null=True, blank=True)
    watering_interval_days = models.PositiveSmallIntegerField()
    first_harvest_at = models.DateTimeField(null=True, blank=True, help_text="North Star: set by the first harvest")
    failure_reason = models.CharField(max_length=20, choices=FailureReason.choices, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    replanted_from = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replants")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "status"]), models.Index(fields=["plant", "status"])]

    def __str__(self):
        return f"{self.user.username}'s {self.nickname}"


class TimelineEntry(TimeStampedModel):
    """Photo + note tagged with a growth stage (FR-21)."""

    class Stage(models.TextChoices):
        SEED = "seed", "Seed"
        SEEDLING = "seedling", "Seedling"
        VEGETATIVE = "vegetative", "Vegetative"
        FLOWERING = "flowering", "Flowering"
        FRUITING = "fruiting", "Fruiting"
        HARVEST = "harvest", "Harvest"

    user_plant = models.ForeignKey(UserPlant, on_delete=models.CASCADE, related_name="timeline")
    stage = models.CharField(max_length=10, choices=Stage.choices)
    photo = models.ImageField(upload_to="garden/timeline/%Y/%m/", null=True, blank=True)
    note = models.TextField(blank=True)
    recorded_on = models.DateField()

    class Meta:
        ordering = ["recorded_on", "created_at"]
        verbose_name_plural = "timeline entries"


class CareLog(TimeStampedModel):
    """Watering, feeding, pruning … (FR-22). performed_on is a date because the UI logs days, not times."""

    class Action(models.TextChoices):
        WATER = "water", "Water"
        FERTILIZE = "fertilize", "Fertilize"
        PRUNE = "prune", "Prune"
        REPOT = "repot", "Repot"
        TREAT_PEST = "treat_pest", "Treat pest"
        TRANSPLANT = "transplant", "Transplant"
        OTHER = "other", "Other"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        REMINDER = "reminder", "From reminder"
        TUTOR_SUGGESTION = "tutor_suggestion", "Tutor suggestion"

    user_plant = models.ForeignKey(UserPlant, on_delete=models.CASCADE, related_name="care_logs")
    action = models.CharField(max_length=12, choices=Action.choices)
    amount = models.CharField(max_length=50, blank=True)
    note = models.TextField(blank=True)
    performed_on = models.DateField()
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)

    class Meta:
        ordering = ["-performed_on", "-created_at"]


class Problem(TimeStampedModel):
    """A logged plant problem (FR-25). AI diagnosis (Diagnosis model, FR-33) belongs to the tutor area."""

    class Category(models.TextChoices):
        PEST = "pest", "Pest"
        DISEASE = "disease", "Disease"
        NUTRIENT = "nutrient", "Nutrient"
        WATERING = "watering", "Watering"
        ENVIRONMENT = "environment", "Environment"
        UNKNOWN = "unknown", "Not sure"

    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        MONITORING = "monitoring", "Monitoring"
        RESOLVED = "resolved", "Resolved"

    user_plant = models.ForeignKey(UserPlant, on_delete=models.CASCADE, related_name="problems")
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to="garden/problems/%Y/%m/", null=True, blank=True)
    category = models.CharField(max_length=12, choices=Category.choices, default=Category.UNKNOWN)
    severity = models.CharField(max_length=6, choices=Severity.choices, default=Severity.MEDIUM)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    opened_on = models.DateField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-opened_on", "-created_at"]


class Harvest(TimeStampedModel):
    """A harvest entry (FR-27). The first one sets UserPlant.first_harvest_at (North Star)."""

    class Unit(models.TextChoices):
        G = "g", "g"
        KG = "kg", "kg"
        OZ = "oz", "oz"
        LB = "lb", "lb"
        COUNT = "count", "count"
        BUNCH = "bunch", "bunch"

    user_plant = models.ForeignKey(UserPlant, on_delete=models.CASCADE, related_name="harvests")
    harvested_on = models.DateField()
    quantity = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=5, choices=Unit.choices, default=Unit.G)
    photo = models.ImageField(upload_to="garden/harvests/%Y/%m/", null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-harvested_on", "-created_at"]


class Reminder(TimeStampedModel):
    """A care task (FR-24), generated by Start Growing or added by the user.

    Simplified for Area 2: a fixed interval in days and a due date. The calendar/notifications work
    (PRD 7.2 calendar_app: RRULE, next_due_at in UTC, quiet hours, email) builds on this table.
    """

    class Type(models.TextChoices):
        WATER = "water", "Watering"
        FERTILIZE = "fertilize", "Feeding"
        CHECK_PROBLEM = "check_problem", "Problem check"
        HARVEST_CHECK = "harvest_check", "Harvest check"
        CUSTOM = "custom", "Custom"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reminders")
    user_plant = models.ForeignKey(UserPlant, on_delete=models.CASCADE, null=True, blank=True, related_name="reminders")
    type = models.CharField(max_length=14, choices=Type.choices)
    title = models.CharField(max_length=120)
    interval_days = models.PositiveSmallIntegerField(default=0, help_text="0 = one-off")
    time = models.TimeField(default="08:00")
    next_due_on = models.DateField(db_index=True)
    is_active = models.BooleanField(default=True)
    notify_in_app = models.BooleanField(default=True)
    notify_email = models.BooleanField(default=True)
    weather_aware = models.BooleanField(default=False, help_text="Skip outdoor watering after rain (FR-41)")
    is_auto = models.BooleanField(default=True, help_text="Generated by the system; regenerated on stage changes unless edited")

    class Meta:
        ordering = ["next_due_on", "time"]

    def __str__(self):
        return self.title


class ReminderOccurrence(models.Model):
    """What happened on one due date of a reminder (done, skipped after rain, …)."""

    class Status(models.TextChoices):
        DONE = "done", "Done"
        SKIPPED_RAIN = "skipped_rain", "Skipped · rain"
        SKIPPED_USER = "skipped_user", "Skipped"
        MISSED = "missed", "Missed"

    reminder = models.ForeignKey(Reminder, on_delete=models.CASCADE, related_name="occurrences")
    due_on = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices)
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-due_on"]
