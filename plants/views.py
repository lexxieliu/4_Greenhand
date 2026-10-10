from django.shortcuts import render
from .models import Plant
from django.views import View
from django.views.generic import ListView
from django.shortcuts import get_object_or_404
from garden.models import Garden
from io import BytesIO
from django.conf import settings
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from django.urls import reverse
from django.db.models import Count, Q
import requests
import matplotlib
import json
import csv
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
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
@login_required
def vegalitechart(request):
    bar_spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Plants per category",
        "width": "container",
        "height": 300,
        "data": {"url": reverse("api_summary")},
        "mark": {"type": "bar", "cornerRadiusEnd": 3},
        "encoding": {
            "x": {"field": "category", "type": "nominal", "title": "Category",
                  "axis": {"labelAngle": -30}},
            "y": {"field": "value", "type": "quantitative", "title": "Plants",
                  "axis": {"tickMinStep": 1}},
            "tooltip": [
                {"field": "category", "type": "nominal"},
                {"field": "value", "type": "quantitative", "title": "Plants"},
            ],
        },
    }
    line_spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Garden entries over time (cumulative)",
        "width": "container",
        "height": 300,
        "data": {"url": reverse("api_garden_timeline")},
        "mark": {"type": "line", "point": True},
        "encoding": {
            "x": {"field": "added_at", "type": "temporal", "title": "Added to a garden"},
            "y": {"field": "total", "type": "quantitative", "title": "Total entries",
                  "axis": {"tickMinStep": 1}},
            "tooltip": [
                {"field": "added_at", "type": "temporal"},
                {"field": "progress", "type": "nominal"},
                {"field": "total", "type": "quantitative"},
            ],
        },
    }
    return render(request, "plant/plant_charts.html", {
        "bar_spec": bar_spec,
        "line_spec": line_spec,
    })


def export_csv(request):
    """Generates and streams a downloadable CSV file containing all Plant records."""
    # Format timestamp for filename: YYYY-MM-DD_HH-MM
    timestamp = timezone.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"plants_{timestamp}.csv"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    # First row: Column headers
    writer.writerow(["Plant ID", "Name", "Scientific Name", "Category", "Usage Type"])

    # Data rows from DB (ordered by name)
    plants = Plant.objects.values_list("plant_id", "plant_name", "scientific_name", "category", "usage_type").order_by("plant_name")
    for plant in plants:
        writer.writerow(plant)
    return response


def export_json(request):
    """Returns a downloadable formatted JSON file with metadata and model records."""
    timestamp_str = timezone.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"plants_{timestamp_str}.json"

    plants = list(Plant.objects.values("plant_id", "plant_name", "scientific_name", "category", "usage_type").order_by("plant_id"))

    # Required structured metadata + record list
    payload = {
        "generated_at": timezone.now().isoformat(),
        "record_count": len(plants),
        "plants": plants,
    }

    response = JsonResponse(payload, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
@login_required
def reports_view(request):
    """Renders the HTML reports page with grouped summaries and totals."""
    # Summary 1: Plants per Category
    category_summary = (
        Plant.objects.values("category")
        .annotate(total=Count("plant_id"))
        .order_by("-total")
    )

    usage_type_summary = (
        Plant.objects.values("usage_type").annotate(total=Count("usage_type")).order_by("-total")
    )


    # Overall Total
    total_plants = Plant.objects.count()

    context = {
        "category_summary": category_summary,
        "usage_type_summary": usage_type_summary,
        "total_plants": total_plants,
    }
    return render(request, "reports.html", context)

def external_plant_api(request):
    """Fetch plant entries from Wikipedia API, combine with local DB Plant data,

    and expose as an aggregated API endpoint or HTML search view.
    """
    query = request.GET.get("q", "").strip()

    if not query:
        if request.GET.get("format") == "json":
            return JsonResponse(
                {
                    "error": "Query parameter 'q' is required. Example: /api/external-plant/?q=tomato"
                },
                status=400,
            )
        return render(
            request,
            "external_search.html",
            {"query": "", "result": None, "error": None},
        )

    # 1. Local DB Query (using exact fields from your Plant model)
    local_plants_qs = Plant.objects.filter(
        Q(plant_name__icontains=query)
        | Q(scientific_name__icontains=query)
        | Q(category__icontains=query)
    )

    local_plants = [
        {
            "plant_id": p.plant_id,
            "plant_name": p.plant_name,
            "scientific_name": getattr(p, "scientific_name", "N/A"),
            "category": getattr(p, "category", "N/A"),
            "usage_type": getattr(p, "usage_type", "N/A"),
        }
        for p in local_plants_qs
    ]

    # 2. Call external keyless API (Wikipedia Opensearch API)
    external_data = []
    api_status = "success"
    error_message = None

    try:
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "opensearch",
            "search": query,
            "limit": 3,
            "namespace": 0,
            "format": "json",
        }
        headers = {"User-Agent": "DjangoPlantApp/1.0 (educational use)"}

        # Strict Assignment Requirements: params=..., timeout=5, .raise_for_status()
        response = requests.get(
            url, params=params, headers=headers, timeout=5
        )
        response.raise_for_status()

        wiki_json = response.json()
        if len(wiki_json) >= 4:
            titles = wiki_json[1]
            descriptions = wiki_json[2]
            links = wiki_json[3]

            for i in range(len(titles)):
                external_data.append(
                    {
                        "title": titles[i],
                        "snippet": (
                            descriptions[i]
                            if descriptions[i]
                            else "Wikipedia entry available."
                        ),
                        "url": links[i],
                    }
                )

    except requests.exceptions.Timeout:
        api_status = "timeout_error"
        error_message = "The external Wikipedia API request timed out."
    except requests.exceptions.RequestException as e:
        api_status = "request_error"
        error_message = f"Failed to fetch external data: {str(e)}"

    # 3. Analytics & Triangulation (Combining Local + External Data)
    has_local = len(local_plants) > 0
    has_external = len(external_data) > 0

    combined_result = {
        "query": query,
        "api_status": api_status,
        "analytics": {
            "local_matches_count": len(local_plants),
            "external_matches_count": len(external_data),
            "data_coverage": (
                "Complete (Both Local DB & External API)"
                if (has_local and has_external)
                else (
                    "Local Only"
                    if has_local
                    else ("External Only" if has_external else "No Coverage")
                )
            ),
        },
        "local_plants": local_plants,
        "external_wikipedia_results": external_data,
        "error_message": error_message,
    }

    # Return clean JSON API if requested, otherwise render HTML template
    if (
        request.GET.get("format") == "json"
        or request.headers.get("x-requested-with") == "XMLHttpRequest"
    ):
        return JsonResponse(combined_result)

    return render(
        request,
        "external_search.html",
        {"query": query, "result": combined_result, "error": error_message},
    )

def api_garden_timeline(request):
    """Cumulative count of Garden entries over time (chart-ready JSON)."""
    entries = Garden.objects.order_by('added_at').values('added_at', 'progress')
    data = [
        {"added_at": e['added_at'].isoformat(), "progress": e['progress'], "total": i}
        for i, e in enumerate(entries, start=1)
    ]
    return JsonResponse(data, safe=False)

def vega_chart_image(request, name):
    """Serve the saved Vega-Lite chart screenshots at /vega-lite/chart1.png and chart2.png."""
    if name not in ("chart1", "chart2"):
        raise Http404
    path = settings.BASE_DIR / "static" / "vega-lite" / f"{name}.png"
    if not path.exists():
        raise Http404
    return FileResponse(open(path, "rb"), content_type="image/png")

def signup_view(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})