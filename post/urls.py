from django.urls import path
from . import views

urlpatterns = [
    path('manual/', views.post_manual_view, name='post-manual'),
    path('render/', views.post_render_view, name='post-render'),
    path('cbv-base/', views.PostBaseView.as_view(), name='post-cbv-base'),
    path('cbv-generic/', views.PostGenericListView.as_view(), name='post-cbv-generic'),
]