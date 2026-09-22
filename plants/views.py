from django.shortcuts import render
from .models import Plant
from django.views import View
from django.views.generic import ListView
from django.shortcuts import get_object_or_404



# Create your views here.
class PlantListView(ListView):
    model = Plant
    template_name = 'plant/plant_list.html'
    context_object_name = 'plants_list'

class PlantDetailView(View):

    def get(self, request, primary_key):
        plant = get_object_or_404(Plant, pk=primary_key)

        return render(
            request,
            'plant/plant_detail.html',
            {
                'single_plant': plant,
            },
        )

