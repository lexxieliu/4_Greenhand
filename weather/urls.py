from django.urls import path

from . import views

app_name = "weather"
urlpatterns = [
    path("", views.weather, name="index"),
    path("setup/", views.setup, name="setup"),
    path("alerts/<int:pk>/ack/", views.acknowledge, name="acknowledge"),
]
