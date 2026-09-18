from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Post(models.Model):
    """
    Represents user-generated posts in the community social feed. Each post is related to one user, and one user could have many posts,
    we use cascade relationship so if the user's delete is account the post is also deleted
    """
    post_id = models.AutoField(primary_key=True)
    post_content = models.TextField()
    ai_summary = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_posts")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Post #{self.post_id} by {self.user.username}"