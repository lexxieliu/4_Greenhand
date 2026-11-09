from django.contrib import admin

from .models import Comment, Post, PostImage, Report


class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 0


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "post_type", "is_hidden", "created_at")
    list_filter = ("post_type", "is_hidden")
    search_fields = ("author__username", "body")
    inlines = [PostImageInline]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "post", "is_hidden", "created_at")
    list_filter = ("is_hidden",)
    search_fields = ("author__username", "body")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """Moderation queue (FR-56): oldest open reports first; filter by status to see past decisions."""
    list_display = ("id", "status", "reason", "reporter", "content_type", "preview", "created_at")
    list_filter = ("status", "reason", "content_type")
    actions = ["hide_content", "dismiss"]

    @admin.display(description="Reported content")
    def preview(self, report):
        return report.target.body[:80] if report.target else "(deleted)"

    @admin.action(description="Hide content and mark actioned")
    def hide_content(self, request, queryset):
        for report in queryset.select_related("content_type"):
            if report.target:
                report.target.is_hidden = True
                report.target.save(update_fields=["is_hidden"])
        queryset.update(status="actioned")

    @admin.action(description="Dismiss report")
    def dismiss(self, request, queryset):
        queryset.update(status="dismissed")
