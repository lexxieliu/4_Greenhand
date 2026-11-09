from django.contrib import admin

from .models import Location, PlantWeatherSettings, WeatherAlert, WeatherSnapshot

admin.site.register([Location, PlantWeatherSettings, WeatherSnapshot, WeatherAlert])
