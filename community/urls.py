from django.urls import path

from . import views

app_name = "community"

urlpatterns = [
    path("", views.post_list, name="feed"),
    path("new/", views.create_post, name="create"),
    path("<int:post_id>/comments/", views.add_comment, name="comment"),
    path("<int:post_id>/like/", views.toggle, {"field": "like"}, name="like"),
    path("<int:post_id>/save/", views.toggle, {"field": "save"}, name="save"),
    path("<int:post_id>/report/", views.report_post, name="report"),
]
