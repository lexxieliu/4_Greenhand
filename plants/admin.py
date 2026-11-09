from django.contrib import admin

from .models import Plant, PlantProblemSummary


class PlantProblemSummaryInline(admin.TabularInline):
    model = PlantProblemSummary
    extra = 0
    fields = ("problem_name", "symptoms", "solution", "source_count")


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    """Plant data is managed here by the `curator` role (PRD 3.8)."""
    list_display = ("common_name", "category", "difficulty", "sunlight_requirement", "watering_interval_days",
                    "frost_tolerant", "container_friendly", "harvest_mode", "is_published")
    list_filter = ("is_published", "category", "difficulty", "sunlight_requirement", "frost_tolerant",
                   "container_friendly", "indoor_friendly", "harvest_mode")
    list_editable = ("is_published",)
    search_fields = ("common_name", "scientific_name", "slug")
    prepopulated_fields = {"slug": ("common_name",)}
    inlines = [PlantProblemSummaryInline]
    fieldsets = (
        (None, {"fields": ("common_name", "slug", "scientific_name", "category", "difficulty", "description", "is_published")}),
        ("Care", {"fields": ("sunlight_requirement", "watering_interval_days", "spacing_cm", "care_guide",
                             ("days_to_germination_min", "days_to_germination_max"),
                             ("days_to_harvest_min", "days_to_harvest_max"), "harvest_mode")}),
        ("Climate", {"fields": (("min_temp_c", "max_temp_c"), "frost_tolerant", "frost_threshold_c",
                                "hardiness_zones", "planting_months", "container_friendly", "indoor_friendly")}),
        ("Source", {"fields": ("external_source_id", "usage_type")}),
    )
