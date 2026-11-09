from django.urls import path

from . import views

app_name = "notifications"
urlpatterns = [
    path("", views.center, name="center"),
    path("read/", views.mark_read, name="read_all"),
    path("<int:pk>/read/", views.mark_read, name="read"),
    path("settings/", views.preferences, name="preferences"),
    path("stop/<str:token>/", views.unsubscribe, name="unsubscribe"),
]
