from django import forms

from .models import Location, PlantWeatherSettings


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ["label", "latitude", "longitude", "timezone"]


class PlantWeatherForm(forms.ModelForm):
    class Meta:
        model = PlantWeatherSettings
        fields = [
            "user_plant",
            "location",
            "setting",
            "frost_tolerant",
            "frost_threshold_c",
        ]

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user_plant"].queryset = user.my_garden_plants.all()
        self.fields["location"].queryset = Location.objects.filter(user=user)
