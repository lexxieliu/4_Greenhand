from django import forms

from .models import Location, PlantWeatherSettings


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ["label", "latitude", "longitude", "timezone"]


class PlantWeatherForm(forms.ModelForm):
    class Meta:
        model = PlantWeatherSettings
        fields = ["user_plant", "location"]   # indoor/outdoor and frost come from the plant itself

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user_plant"].queryset = user.user_plants.all()
        self.fields["location"].queryset = Location.objects.filter(user=user)
