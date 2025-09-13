# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Deployment, DeploymentEnvVar
from projects.models import EnvVarModel

@receiver(post_save, sender=Deployment)
def create_deployment_env_vars(sender, instance, created, **kwargs):
    """
    لما يتنشئ Deployment جديد، ننشئ/نربط له متغيرات البيئة الخاصة بالمشروع.
    """
    if created:  # فقط عند الإنشاء
        project = instance.project
        for env_var in EnvVarModel.objects.filter(project=project):
            DeploymentEnvVar.objects.get_or_create(
                deployment=instance,
                var_name=env_var,
                defaults={"value": ""}  # ممكن تحط default من مكان آخر
            )
