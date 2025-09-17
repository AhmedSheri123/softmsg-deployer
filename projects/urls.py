from django.urls import path
from . import views

urlpatterns = [
    path('project-list', views.project_list, name='project_list'),
    path(
        "run/<int:container_id>/<int:action_id>/",
        views.run_action,
        name="run_action"
    ),
]
