from django.db import models


class WeatherSnapshot(models.Model):
    """Forecast for one rounded location (0.1 degree), shared by nearby users (PRD 7.2)."""
    lat_rounded = models.DecimalField(max_digits=5, decimal_places=1)
    lon_rounded = models.DecimalField(max_digits=5, decimal_places=1)
    fetched_at = models.DateTimeField(auto_now_add=True)
    current_temp_c = models.DecimalField(max_digits=4, decimal_places=1)
    rain_last_24h_mm = models.DecimalField(max_digits=5, decimal_places=1)
    precip_prob_next_12h = models.PositiveSmallIntegerField()
    min_temp_next_48h_c = models.DecimalField(max_digits=4, decimal_places=1)
    max_temp_next_48h_c = models.DecimalField(max_digits=4, decimal_places=1)
    forecast = models.JSONField(default=list)      # [{"date", "high", "low", "precip_prob", "precip_mm", "code"}]
    details = models.JSONField(default=dict, blank=True)   # {"current", "hourly", "utc_offset"} for the weather page
    provider = models.CharField(max_length=30, default="open_meteo")

    class Meta:
        ordering = ["-fetched_at"]
        indexes = [models.Index(fields=["lat_rounded", "lon_rounded", "-fetched_at"])]
