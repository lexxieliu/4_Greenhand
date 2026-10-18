from django.urls import path

from . import views

app_name = 'plants'

urlpatterns = [
    path("", views.plant_list, name="list"),
    path("<slug:slug>/", views.plant_detail, name="detail"),
    path("<slug:slug>/plants", views.start_growing, name="start")
]