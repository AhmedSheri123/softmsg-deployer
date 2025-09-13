from django.contrib import admin
from .models import Deployment, DeploymentEnvVar
# Register your models here.
admin.site.register(Deployment)
admin.site.register(DeploymentEnvVar)