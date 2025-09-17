from django.contrib import admin
from .models import Deployment, DeploymentContainerEnvVar
# Register your models here.
admin.site.register(Deployment)
admin.site.register(DeploymentContainerEnvVar)