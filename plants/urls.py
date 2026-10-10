from django.urls import include, path
from . import views
from django.contrib.auth import views as auth_views
from .api_access import api_login_required, public_api

urlpatterns = [
    # Pages
    path('plants/', views.PlantListView.as_view(), name='plants_list'),
    path('plants/<int:primary_key>', views.PlantDetailView.as_view(), name='plants_detail'),
    path('plants/chart.png', views.plant_category_chart, name='plants-chart'),
    path('plants/vega/', views.vegalitechart, name='vega_chart'),
    path('vega-lite/<str:name>.png', views.vega_chart_image, name='vega_chart_image'),
    path('reports/', views.reports_view, name='reports'),

    # Exports (protected)
    path('export/csv/', api_login_required(views.export_csv), name='export_csv'),
    path('export/json/', api_login_required(views.export_json), name='export_json'),

    # Internal JSON APIs (protected: login required)
    path('api/plants/', api_login_required(views.PlantsAPIView.as_view()), name='plants_api'),
    path('api/plants_fbv/', api_login_required(views.plant_api), name='api_fbv'),
    path('api/garden-timeline/', api_login_required(views.api_garden_timeline), name='api_garden_timeline'),

    # External API (Wikipedia) combined with local data (protected)
    path('api/external-plant/', api_login_required(views.external_plant_api), name='external_plant_api'),

    # THE ONE PUBLIC API: no login, clean JSON from the database, CORS enabled
    path('api/summary/', public_api(views.api_summary), name='api_summary'),

    path("signup/", views.signup_view, name="signup"),
    # Django login
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),

    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path('accounts/', include('allauth.urls')),

]