from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("read-all/", views.read_all, name="read_all"),
    path("<int:notification_id>/open/", views.open_notification, name="open"),
]
