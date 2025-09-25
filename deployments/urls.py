from django.urls import path
from . import views

urlpatterns = [
    path('rebuild-project/<int:deployment_id>', views.rebuild_project, name='rebuild_project'),
    path('my-deployments/', views.my_deployments, name='my_deployments'),
    path('deployment-detail/<int:deployment_id>', views.deployment_detail, name='deployment_detail'),
    path('change-project-domain/<int:deployment_id>', views.change_project_domain, name='change_project_domain'),
    path('reset-project-domain/<int:deployment_id>', views.reset_project_domain, name='reset_project_domain'),
    path('delete-deployment/<int:deployment_id>', views.delete_deployment, name='delete_deployment'),
    path('deployments/<int:deployment_id>/usage/', views.deployment_usage_api, name='deployment_usage_api'),


    path("deployment/<int:deployment_id>/hard-restart/", views.hard_restart_deployment, name="hard_restart_deployment"),
    path("deployment/<int:deployment_id>/restart/", views.restart_deployment, name="restart_deployment"),
    path("deployment/<int:deployment_id>/stopstart/", views.stopstart_deployment, name="stopstart_deployment"),
    path("deployment/<int:deployment_id>/logs/", views.deployment_logs, name="deployment_logs"),

    path('deployments/<int:deployment_id>/env-vars/update/', views.update_all_env_vars, name='update_all_env_vars'),
    path('env-settings/<int:deployment_id>/', views.env_settings, name='env_settings'),

    #backups
    path("deployment/<int:deployment_id>/backups/", views.deployment_backups, name="deployment_backups"),
    path("deployment/<int:deployment_id>/backups/create/", views.create_backup, name="deployment_backup_create"),
    path("backups/<int:backup_id>/restore/", views.restore_backup, name="deployment_backup_restore"),
    path("deployments/backups/<int:backup_id>/delete/", views.delete_backup, name="deployment_backup_delete"),
    path("deployments/backups/<int:backup_id>/download/", views.download_backup, name="deployment_backup_download"),
    path("deployments/<int:deployment_id>/backups/upload/", views.upload_backup, name="deployment_backup_upload"),



]
