from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from garden.models import UserPlant
from plants.models import Plant

User = settings.AUTH_USER_MODEL
MAX_POST_IMAGES = 4


class Post(models.Model):
    TYPES = [("progress", "Progress"), ("harvest", "Harvest"), ("question", "Question"), ("tip", "Tip")]

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="community_posts")
    user_plant = models.ForeignKey(UserPlant, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts")
    plant = models.ForeignKey(Plant, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts")
    post_type = models.CharField(max_length=10, choices=TYPES, default="progress")
    body = models.TextField(max_length=2000)
    ai_suggestion = models.TextField(blank=True, default="")
    is_hidden = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.get_post_type_display()} by {self.author}: {self.body[:40]}"


class PostImage(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="posts/")
    order = models.PositiveSmallIntegerField(default=0)
    alt_text = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["order"]


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="community_comments")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies")
    body = models.TextField(max_length=1000)
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.author}: {self.body[:40]}"


class PostLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_likes")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "post"], name="unique_post_like")]


class PostSave(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_saves")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="saves")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "post"], name="unique_post_save")]


class Report(models.Model):
    REASONS = [("spam", "Spam"), ("harmful_advice", "Harmful advice"), ("harassment", "Harassment"),
               ("other", "Something else")]
    STATUSES = [("open", "Open"), ("actioned", "Actioned"), ("dismissed", "Dismissed")]

    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    target = GenericForeignKey("content_type", "object_id")
    reason = models.CharField(max_length=20, choices=REASONS)
    status = models.CharField(max_length=10, choices=STATUSES, default="open", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [models.UniqueConstraint(fields=["reporter", "content_type", "object_id"],
                                               name="unique_report_per_user")]
