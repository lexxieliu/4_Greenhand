<<<<<<< HEAD
from .views import PlantListView, PlantDetailView, plant_category_chart, PlantsAPIView
=======
from .views import PlantListView, PlantDetailView, plant_category_chart, plant_api
>>>>>>> 3c11ffaf86a42f938307c171e1a491891e07ed1a
from django.urls import path

urlpatterns = [
    path('plants/', PlantListView.as_view(), name='plants_list'),
    path('plants/<int:primary_key>', PlantDetailView.as_view(), name='plants_detail'),
    path('plants/chart.png', plant_category_chart, name='plants-chart'),
<<<<<<< HEAD
    path('api/plants/', PlantsAPIView.as_view(), name='plants_api'),
=======
    path('api/plants_fbv/', plant_api, name='api_fbv'),
>>>>>>> 3c11ffaf86a42f938307c171e1a491891e07ed1a
]