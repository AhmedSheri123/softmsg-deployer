from django.urls import path
from . import views

urlpatterns = [
    path('plans/<int:project_id>', views.plans_list, name='plans_list'),
    path('apply-subscription/<int:project_id>', views.ApplySubscription, name='ApplySubscription'),
    path('upgrade-plan/<int:deployment_id>', views.UpgradePlan, name='UpgradePlan'),
]
