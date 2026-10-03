from django.shortcuts import render
from .models import Plant
from django.views import View
from django.views.generic import ListView, TemplateView
from django.shortcuts import get_object_or_404
from garden.models import Garden
from io import BytesIO
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.db.models import Count
import urllib.request
import matplotlib
import json
matplotlib.use("Agg")          # non-interactive backend — required, since Django has no display/screen
import matplotlib.pyplot as plt

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
        from django.db.models import Count

        # ...inside get_context_data():

        # Relationship-spanning query:
        # filter Plants by an attribute of their related Garden entries
        # (Plant --> garden_instances --> progress), same shape as
        # "students filtered by section name" in the assignment example
        stage = self.request.GET.get('stage')
        context['stage'] = stage
        if stage:
            context['plants_list'] = context['plants_list'].filter(garden_instances__progress=stage)
        context['stages'] = Garden.objects.values_list('progress', flat=True).distinct()

        # Aggregations:
        # 1) a total count
        context['total_plants'] = Plant.objects.count()

        # 2) a grouped summary (annotate + count)
        context['plants_per_category'] = (
            Plant.objects
            .values('category')
            .annotate(n_plants=Count('plant_id'))
            .order_by('category')
        )
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

def plant_category_chart(request):
    data = (
        Plant.objects
        .values('category')
        .annotate(n_plants=Count('plant_id'))
        .order_by('category')
    )
    labels = [row['category'] for row in data]
    counts = [row['n_plants'] for row in data]

    fig, ax = plt.subplots(figsize=(6, 3), dpi=150)
    ax.bar(labels, counts, color="#4CAF50")     # matches your green palette from style.css
    ax.set_title("Plants per Category")
    ax.set_xlabel("Category")
    ax.set_ylabel("Number of Plants")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)          # frees the figure from memory — this is the "Memory Awareness" requirement
    buf.seek(0)
    return HttpResponse(buf.getvalue(), content_type="image/png")


class PlantsAPIView(View):
    def get(self, request):
        q = (request.GET.get('q') or '').strip()
        qs = Plant.objects.all()
        if q:
            qs = qs.filter(plant_name__icontains=q)

        data = list(qs.values('plant_name','scientific_name','category','usage_type').order_by('plant_name'))
        status_message = "ok"
        return HttpResponse( json.dumps({"status_message":status_message,"count": len(data), "plants_list": data}), content_type="application/json")

def plant_api(request):
    q=(request.GET.get('q')or '').strip()
    plant_list = Plant.objects.all().values('plant_id','plant_name', 'category','usage_type')
    if q:
        plant_list = plant_list.filter(plant_name__icontains=q).values('plant_id','plant_name', 'category','usage_type')

    data=list(plant_list.order_by('plant_id'))
    return JsonResponse({"count":len(data), "result":data})


def api_summary(request):

    summary_data = (
        Plant.objects
        .values('category')
        .annotate(value=Count('plant_id'))
        .order_by('category')
    )

    formatted_data = [
        {
            "category": item['category'] or "Uncategorized",
            "value": item['value']
        }
        for item in summary_data
    ]

    return JsonResponse(formatted_data, safe=False)

def vegalitechart(request):
    api_url = request.build_absolute_uri(reverse("api_summary"))
    with urllib.request.urlopen(api_url) as resp:
        payload = json.load(resp)

    base_encoding = {
        "x": {
            "field": "category",
            "type": "nominal",
            "title": "Category",
            "sort": None,
            "axis": {"labelAngle": -30},
        },
        "y": {
            "field": "value",
            "type": "quantitative",
            "title": "Count",
            "axis": {"tickMinStep": 1},
        },
        "tooltip": [
            {"field": "category", "type": "nominal", "title": "Category"},
            {"field": "value", "type": "quantitative", "title": "Count"},
        ],
    }

    bar_spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Plants by category (bar)",
        "width": "container",
        "height": 300,
        "data": {"values": payload},
        "mark": {"type": "bar", "cornerRadiusEnd": 3},
        "encoding": base_encoding,
    }

    line_spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Plants by category (line)",
        "width": "container",
        "height": 300,
        "data": {"values": payload},
        "mark": {"type": "line", "point": True},
        "encoding": base_encoding,
    }

    return render(request, "plant/plant_charts.html", {
        "bar_spec": bar_spec,
        "line_spec": line_spec,
    })