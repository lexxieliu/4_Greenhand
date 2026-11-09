from django.contrib import admin
from .models import GrowingLocation, Profile
# Register your models here.
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('profile_id', 'user', 'experience_level', 'space_type', 'onboarding_completed')
    list_filter = ('onboarding_completed', 'experience_level', 'space_type')
    search_fields = ('user__username',)


@admin.register(GrowingLocation)
class GrowingLocationAdmin(admin.ModelAdmin):
    list_display = ('location_id', 'user', 'city', 'region', 'country_code')
    search_fields = ('user__username', 'city')
