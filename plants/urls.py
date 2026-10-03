
from .views import PlantListView, PlantDetailView, plant_category_chart, PlantsAPIView

from .views import PlantListView, PlantDetailView, plant_category_chart, plant_api, api_summary

from django.urls import path

from . import views

urlpatterns = [
    path('plants/', PlantListView.as_view(), name='plants_list'),
    path('plants/<int:primary_key>', PlantDetailView.as_view(), name='plants_detail'),
    path('plants/chart.png', plant_category_chart, name='plants-chart'),

    path('api/plants/', PlantsAPIView.as_view(), name='plants_api'),

    path('api/plants_fbv/', plant_api, name='api_fbv'),
    path('api/summary/', api_summary, name='api_summary'),
    path('plants/vega/', views.vegalitechart, name='vega_chart' ),
]