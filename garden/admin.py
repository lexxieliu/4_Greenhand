from django.contrib import admin

from .models import CareLog, Harvest, Problem, TimelineEntry, UserPlant


class TimelineInline(admin.TabularInline):
    model = TimelineEntry
    extra = 0


class CareLogInline(admin.TabularInline):
    model = CareLog
    extra = 0


class HarvestInline(admin.TabularInline):
    model = Harvest
    extra = 0


@admin.register(UserPlant)
class UserPlantAdmin(admin.ModelAdmin):
    list_display = ("nickname", "user", "plant", "status", "setting", "planted_on", "first_harvest_at")
    list_filter = ("status", "setting", "start_method")
    search_fields = ("nickname", "user__username", "plant__common_name")
    raw_id_fields = ("user", "replanted_from")
    inlines = [TimelineInline, CareLogInline, HarvestInline]


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ("title", "user_plant", "category", "severity", "status", "opened_on")
    list_filter = ("status", "severity", "category")
    search_fields = ("title", "user_plant__nickname")

