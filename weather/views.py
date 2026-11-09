from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import LocationForm, PlantWeatherForm
from .models import PlantWeatherSettings, WeatherAlert
from .selectors import active_alerts, weather_cards


@login_required
def weather(request):
    return render(
        request,
        "weather/weather.html",
        {
            "cards": weather_cards(request.user),
            "alerts": active_alerts(request.user),
            "configs": PlantWeatherSettings.objects.filter(
                user_plant__user=request.user
            ).select_related("user_plant__plant", "location"),
        },
    )


@login_required
def setup(request):
    location_form = LocationForm(
        request.POST if request.POST.get("kind") == "location" else None
    )
    config = None
    if request.method == "POST" and request.POST.get("kind") == "plant":
        try:
            plant_id = int(request.POST.get("user_plant", ""))
        except (TypeError, ValueError):
            plant_id = 0
        plant = get_object_or_404(request.user.user_plants, pk=plant_id)
        config = PlantWeatherSettings.objects.filter(user_plant=plant).first()
    plant_form = PlantWeatherForm(
        request.POST if request.POST.get("kind") == "plant" else None,
        user=request.user,
        instance=config,
    )
    if request.method == "POST":
        if request.POST.get("kind") == "location" and location_form.is_valid():
            location = location_form.save(commit=False)
            location.user = request.user
            location.save()
            return redirect("weather:setup")
        if request.POST.get("kind") == "plant" and plant_form.is_valid():
            plant_form.save()
            return redirect("weather:index")
    return render(
        request,
        "weather/setup.html",
        {"location_form": location_form, "plant_form": plant_form},
    )


@login_required
@require_POST
def acknowledge(request, pk):
    alert = get_object_or_404(WeatherAlert, pk=pk, user=request.user)
    alert.acknowledged_at = timezone.now()
    alert.save(update_fields=["acknowledged_at"])
    return redirect("weather:index")
