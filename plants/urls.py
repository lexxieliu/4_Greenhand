from .views import PlantListView, PlantDetailView, plant_category_chart, plant_api
from django.urls import path

urlpatterns = [
    path('plants/', PlantListView.as_view(), name='plants_list'),
    path('plants/<int:primary_key>', PlantDetailView.as_view(), name='plants_detail'),
    path('plants/chart.png', plant_category_chart, name='plants-chart'),
    path('api/plants_fbv/', plant_api, name='api_fbv'),
]