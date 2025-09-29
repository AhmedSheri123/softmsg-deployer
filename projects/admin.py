from django.contrib import admin
from .models import AvailableProject, ProjectContainer, Action, ActionParameter, EnvVar, EnvVarsTitle, ProjectReview, Category, ProjectDBConfig
from django_json_widget.widgets import JSONEditorWidget
from django.db import models
from modeltranslation.admin import TabbedTranslationAdmin

# -------------------------
# Action & EnvVar
# -------------------------
admin.site.register(ProjectDBConfig)
admin.site.register(Category)
admin.site.register(ProjectReview)

# فقط المودل المترجم نستخدم TabbedTranslationAdmin
@admin.register(EnvVarsTitle)
class EnvVarsTitleAdmin(TabbedTranslationAdmin):
    pass

# هذه المودلز غير مترجمة، نستخدم ModelAdmin عادي
@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ('label',)
    search_fields = ('label', 'command')

@admin.register(ActionParameter)
class ActionParameterAdmin(admin.ModelAdmin):
    list_display = ('action', 'display_label', 'name', 'data_type', 'required', 'default')
    search_fields = ('name', 'label')

@admin.register(EnvVar)
class EnvVarAdmin(admin.ModelAdmin):
    list_display = ('title', 'key', 'label', 'is_secret', 'required', 'default_value')
    search_fields = ('key', 'label')



# -------------------------
# ProjectContainer
# -------------------------
@admin.register(ProjectContainer)
class ProjectContainerAdmin(admin.ModelAdmin):
    list_display = ('project', 'type')
    search_fields = ('project',)
    


# -------------------------
# AvailableProject
# -------------------------
@admin.register(AvailableProject)
class AvailableProjectAdmin(TabbedTranslationAdmin):
    list_display = ('name', 'has_frontend', 'has_redis')
    search_fields = ('name',)


    def has_frontend(self, obj):
        return obj.containers.filter(type='frontend').exists()
    has_frontend.boolean = True

    def has_redis(self, obj):
        return obj.containers.filter(type='redis').exists()
    has_redis.boolean = True

    # -------------------------
    # (اختياري) تقسيم الحقول عند إضافة/تعديل المشروع
    # -------------------------
    fieldsets = (
        ("Basic Info", {
            "fields": ('name', 'description', 'image', 'is_open_source', 'source_code_url', 'install_steps', 'difficulty_level', 'install_time_minutes', 'disk_size_mb', 'minimum_operating_requirements', 'about', 'docker_compose_template', 'which_service_has_main_domain')
        }),
    )
