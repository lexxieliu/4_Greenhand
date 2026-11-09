from django.urls import path

from . import views

app_name = 'garden'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('my-garden/', views.my_garden, name='my_garden'),
    # JSON endpoints for the My Garden page and the dashboard (PRD 6.5, as plain function-based views)
    path('plants/', views.add_plant, name='add_plant'),
    path('plants/<int:user_plant_id>/timeline/', views.add_timeline_entry, name='add_timeline_entry'),
    path('plants/<int:user_plant_id>/care-logs/', views.log_care, name='log_care'),
    path('plants/<int:user_plant_id>/problems/', views.log_problem, name='log_problem'),
    path('plants/<int:user_plant_id>/harvests/', views.log_harvest, name='log_harvest'),
    path('plants/<int:user_plant_id>/status/', views.change_status, name='change_status'),
    path('plants/<int:user_plant_id>/reminders/', views.add_reminder, name='add_reminder'),
    path('problems/<int:problem_id>/status/', views.set_problem_status, name='set_problem_status'),
    path('reminders/<int:reminder_id>/', views.set_reminder_flag, name='set_reminder_flag'),
    path('reminders/<int:reminder_id>/done/', views.complete_reminder, name='complete_reminder'),
]
