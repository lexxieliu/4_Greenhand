from django.urls import path

from . import views

app_name = "tutor"

urlpatterns = [
    path("", views.ask, name="ask"),
    path("api/ask/", views.api_ask, name="api_ask"),
    path("messages/<int:message_id>/feedback/", views.feedback, name="feedback"),
    path("messages/<int:message_id>/log-problem/", views.log_problem, name="log_problem"),
    path("diagnose/", views.diagnose, name="diagnose"),
    path("diagnose/<int:diagnosis_id>/", views.diagnosis_detail, name="diagnosis_detail"),
    path("diagnose/<int:diagnosis_id>/save/", views.save_diagnosis, name="save_diagnosis"),
]
