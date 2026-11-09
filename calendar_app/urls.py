from django.urls import path

from . import views

app_name = "calendar_app"
urlpatterns = [
    path("events/new/", views.create_event, name="event_create"),
    path("", views.month_view, name="month"),
    path("reminders/new/", views.create_reminder, name="create"),
    path("occurrences/<int:pk>/", views.occurrence_action, name="action"),
    path("reminders/<int:pk>/pause/", views.pause_reminder, name="pause"),
]
