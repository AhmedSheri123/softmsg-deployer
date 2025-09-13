from django.urls import path
from . import views

urlpatterns = [
    path('<int:service_id>', views.view_service_resources, name='view_service_resources'),
]
