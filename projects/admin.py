from django.contrib import admin
from .models import AvailableProject, ActionModel, ActionParameterModel, EnvVarModel
# Register your models here.
admin.site.register(ActionModel)
admin.site.register(ActionParameterModel)
admin.site.register(EnvVarModel)



@admin.register(AvailableProject)
class AvailableProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'docker_image_name', 'has_frontend', 'has_redis')
    search_fields = ('name', 'docker_image_name')
    
    fieldsets = (
        ("Basic Info", {
            "fields": ('name', 'docker_image_name', 'description', 'image')
        }),
        ("Database Env Vars", {
            "fields": (
                'db_engine_env_var_name',
                'db_name_env_var_name',
                'db_user_env_var_name',
                'db_password_env_var_name',
                'db_host_env_var_name',
                'db_port_env_var_name',
            ),
            "classes": ('collapse',),  # يمكن طي القسم لتقليل الفوضى
        }),
        ("Frontend Settings", {
            "fields": ('has_frontend', 'frontend_docker_image_name'),
            "classes": ('collapse',),
        }),
        ("Redis Settings", {
            "fields": ('has_redis', 'redis_docker_image_name', 'redis_host_env_var_name', 'redis_port_env_var_name'),
            "classes": ('collapse',),
        }),

        ("Other", {
            "fields": ('script_run_after_install',)
        }),


    )
