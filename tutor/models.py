from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

from garden.models import Problem, UserPlant

class AITutorLog(models.Model):
    """
    Tutor model represent a feature for give users an AI based tutor on how to grow plants, so it would be in a form of chatbox
    that is why we make it has question and answer text field, tutor_id represent each session of the conversation.
    We also add user_id as a foreignkey because every session is related to one user, and one user could have many sessions,
    and if the user delete their account, the chat history also deleted (CASCADE)
    """
    log_id = models.AutoField(primary_key=True)
    question = models.TextField()
    answer = models.TextField()
    thinking_process = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tutor_logs")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Tutor Q&A for {self.user.username}"


class ChatSession(models.Model):
    """One conversation with the tutor, optionally scoped to a plant (FR-32)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_sessions")
    scoped_plant = models.ForeignKey(UserPlant, on_delete=models.SET_NULL, null=True, blank=True, related_name="chat_sessions")
    title = models.CharField(max_length=120)
    last_message_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-last_message_at"]

    def __str__(self):
        return self.title


class ChatMessage(models.Model):
    """A chat turn with what is needed for debugging, evals and cost tracking (PRD 6.4 A, 6.6)."""
    ROLES = [("user", "User"), ("assistant", "Assistant"), ("system", "System")]

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLES)
    content = models.TextField()
    result = models.JSONField(default=dict, blank=True)              # the structured answer shown to the user
    raw_output = models.TextField(blank=True, default="")
    context_snapshot = models.TextField(blank=True, default="")
    retrieved_chunks = models.JSONField(default=list, blank=True)    # [{"id", "title", "score", "cited"}]
    suggested_actions = models.JSONField(default=list, blank=True)
    model_name = models.CharField(max_length=60, blank=True, default="")
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    completion_tokens = models.PositiveIntegerField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    feedback = models.SmallIntegerField(null=True, blank=True, choices=[(1, "Helpful"), (-1, "Not helpful")])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class Diagnosis(models.Model):
    """Structured result of a photo diagnosis (FR-33); can be saved to a plant's Problem log."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="diagnoses")
    user_plant = models.ForeignKey(UserPlant, on_delete=models.SET_NULL, null=True, blank=True, related_name="diagnoses")
    problem = models.ForeignKey(Problem, on_delete=models.SET_NULL, null=True, blank=True, related_name="diagnoses")
    image = models.ImageField(upload_to="diagnoses/")
    note = models.CharField(max_length=300, blank=True, default="")
    result = models.JSONField()
    model_name = models.CharField(max_length=60)
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    completion_tokens = models.PositiveIntegerField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "diagnoses"
