from django.contrib import admin
from .models import AITutorLog
# Register your models here.
@admin.register(AITutorLog)
class AITutorLogAdmin(admin.ModelAdmin):
    list_display = ('log_id', 'user', 'question', 'created_at')
    search_fields = ('user__username', 'question')
    list_filter = ('created_at',)