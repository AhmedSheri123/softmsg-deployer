from django.contrib import admin
from .models import AvailableProject, ActionModel, ActionParameterModel, EnvVarModel
# Register your models here.
admin.site.register(AvailableProject)
admin.site.register(ActionModel)
admin.site.register(ActionParameterModel)
admin.site.register(EnvVarModel)