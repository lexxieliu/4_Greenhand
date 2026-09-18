from django.contrib import admin

# Register your models here.
from .models import Garden

@admin.register(Garden)
class GardenAdmin(admin.ModelAdmin):
    list_display = ('garden_id', 'user', 'plant', 'progress', 'added_at')
    search_fields = ('user__username', 'plant__plant_name')
    list_filter = ('progress', 'added_at')