from django.urls import path

from . import views

app_name = "tutor"

urlpatterns = [
    path("", views.ask, name="ask"),
    path("api/ask/", views.api_ask, name="api_ask"),
]
