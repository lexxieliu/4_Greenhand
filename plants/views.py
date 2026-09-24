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

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(plant_name__icontains=query)

        category = self.request.POST.get('category')
        if category:
            queryset = queryset.filter(category=category)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        context['selected_category'] = self.request.POST.get('category', '')
        context['categories'] = Plant.objects.values_list('category', flat=True).distinct()
        return context

    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        return self.render_to_response(context)

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

