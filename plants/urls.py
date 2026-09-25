from .views import PlantListView, PlantDetailView
from django.urls import path

urlpatterns = [
    path('plants/', PlantListView.as_view(), name='plants_list'),
    path('plants/<int:primary_key>', PlantDetailView.as_view(), name='plants_detail'),
]