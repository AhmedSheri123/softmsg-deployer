from django.urls import path
from . import views

urlpatterns = [
    path("<int:project_id>/details/api/", views.project_details_ajax, name="project_details_ajax"),
    path("<int:project_id>/details/", views.project_details, name="project_details"),

    path('marketplace', views.project_list, name='project_list'),
    
    path(
        "run/<int:container_id>/<int:action_id>/",
        views.run_action,
        name="run_action"
    ),
    path("project/<int:project_id>/review/", views.add_review, name="add_review"),
    path("get-project-source-code/<int:project_id>/url/", views.get_project_source_code, name="get_project_source_code"),
    path('project-autocomplete/', views.project_autocomplete, name='project-autocomplete'),
]
