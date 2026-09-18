from django.contrib import admin
from .models import Profile
# Register your models here.
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('profile_id', 'user', 'pronouns', 'birthdate')
    search_fields = ('user__username',)