from django.contrib import admin

from .models import Post


# Register your models here.
@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('post_id', 'user', 'post_content', 'created_at')
    search_fields = ('user__username', 'post_content')
    list_filter = ('created_at',)