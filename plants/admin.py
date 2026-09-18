from django.contrib import admin
from .models import Plant

# Register your models here.
@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    list_display = ('plant_id', 'plant_name', 'category', 'scientific_name', 'usage_type')
    search_fields = ('plant_name', 'category')
    list_filter = ('category',)