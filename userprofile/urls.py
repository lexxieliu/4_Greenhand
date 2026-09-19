from django.urls import path
from . import views

urlpatterns = [
    # FBV & Base CBV
    path('manual/', views.profile_manual_view, name='profile-manual'),
    path('render/', views.profile_render_view, name='profile-render'),
    path('cbv-base/', views.ProfileBaseView.as_view(), name='profile-cbv-base'),

    # Generic CBV path
    path('<int:pk>/detail/', views.ProfileGenericDetailView.as_view(), name='profile-cbv-generic-detail'),
    path('<int:pk>/edit/', views.ProfileGenericUpdateView.as_view(), name='profile-cbv-generic-update'),
]