from django.contrib import admin
from .models import AITutorLog, ChatMessage, ChatSession, Diagnosis
# Register your models here.
@admin.register(AITutorLog)
class AITutorLogAdmin(admin.ModelAdmin):
    list_display = ('log_id', 'user', 'question', 'created_at')
    search_fields = ('user__username', 'question')
    list_filter = ('created_at',)


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'last_message_at')
    search_fields = ('user__username', 'title')


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'role', 'feedback', 'model_name', 'prompt_tokens', 'completion_tokens', 'latency_ms', 'created_at')
    list_filter = ('role', 'feedback', 'model_name')


@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'user_plant', 'problem', 'model_name', 'latency_ms', 'created_at')
