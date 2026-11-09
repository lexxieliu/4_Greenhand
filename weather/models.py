from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError("Choose a valid IANA timezone, e.g. America/Chicago.")


class Location(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    label = models.CharField(max_length=100)
    latitude = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    timezone = models.CharField(
        max_length=64, default="UTC", validators=[validate_timezone]
    )

    def __str__(self):
        return self.label


class PlantWeatherSettings(models.Model):
    # Garden is the existing project's UserPlant equivalent.
    user_plant = models.OneToOneField(
        "garden.Garden", on_delete=models.CASCADE, related_name="weather_settings"
    )
    location = models.ForeignKey(Location, on_delete=models.PROTECT)
    setting = models.CharField(
        max_length=10,
        choices=[("outdoor", "Outdoor"), ("indoor", "Indoor")],
        default="outdoor",
    )
    frost_tolerant = models.BooleanField(default=False)
    frost_threshold_c = models.DecimalField(max_digits=4, decimal_places=1, default=2)

    def clean(self):
        if (
            self.user_plant_id
            and self.location_id
            and self.user_plant.user_id != self.location.user_id
        ):
            raise ValidationError(
                "The plant and location must belong to the same user."
            )


class WeatherSnapshot(models.Model):
    lat_rounded = models.DecimalField(max_digits=5, decimal_places=1)
    lon_rounded = models.DecimalField(max_digits=5, decimal_places=1)
    fetched_at = models.DateTimeField(default=timezone.now)
    current_temp_c = models.FloatField()
    rain_last_24h_mm = models.FloatField()
    precip_prob_next_12h = models.PositiveSmallIntegerField()
    min_temp_next_48h_c = models.FloatField()
    max_temp_next_48h_c = models.FloatField()
    forecast = models.JSONField(default=dict)
    provider = models.CharField(max_length=30, default="open_meteo")

    class Meta:
        indexes = [models.Index(fields=["lat_rounded", "lon_rounded", "-fetched_at"])]


class WeatherAlert(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    user_plant = models.ForeignKey("garden.Garden", on_delete=models.CASCADE)
    snapshot = models.ForeignKey(WeatherSnapshot, null=True, on_delete=models.SET_NULL)
    alert_type = models.CharField(
        max_length=20, choices=[(x, x) for x in ("rain_skip", "frost", "heat", "storm")]
    )
    message = models.TextField()
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField(db_index=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    user_overrode = models.BooleanField(default=False)
    dedupe_key = models.CharField(max_length=180, unique=True)

    @property
    def label(self):
        return {
            "rain_skip": "Watering skipped after rain",
            "frost": "Frost alert",
            "heat": "Heat alert",
            "storm": "Storm alert",
        }[self.alert_type]
