from django.contrib import admin
from .models import GrowingLocation, Profile
# Register your models here.
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
<<<<<<< HEAD
    list_display = ('profile_id', 'user', 'experience_level', 'space_type', 'onboarding_completed')
    list_filter = ('onboarding_completed', 'experience_level', 'space_type')
    search_fields = ('user__username',)


@admin.register(GrowingLocation)
class GrowingLocationAdmin(admin.ModelAdmin):
    list_display = ('location_id', 'user', 'city', 'region', 'country_code')
    search_fields = ('user__username', 'city')
=======
    list_display = ('profile_id', 'user', 'pronouns', 'birthdate')
    search_fields = ('user__username',)
>>>>>>> ce515f7437e8d5811a6b3a8dd968ddea18c7d2f5
