from django.db import models
from django.contrib.auth.models import User

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