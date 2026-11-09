from django.contrib import admin

# Register your models here.
from .models import CareLog, Garden, Harvest, Problem, TimelineEntry

@admin.register(Garden)
class GardenAdmin(admin.ModelAdmin):
    list_display = ('garden_id', 'user', 'plant', 'progress', 'added_at')
    search_fields = ('user__username', 'plant__plant_name')
    list_filter = ('progress', 'added_at')


admin.site.register([CareLog, TimelineEntry, Problem, Harvest])
