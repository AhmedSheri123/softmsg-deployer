# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import DeploymentContainer, DeploymentContainerEnvVar
from projects.models import EnvVar

@receiver(post_save, sender=DeploymentContainer)
def create_deployment_env_vars(sender, instance, created, **kwargs):
    """
    لما يتنشئ Deployment جديد، ننشئ/نربط له متغيرات البيئة الخاصة بالمشروع.
    """
    if created:  # فقط عند الإنشاء
        project = instance.project_container
        for env_var in EnvVar.objects.filter(project_container=instance.project_container):
            DeploymentContainerEnvVar.objects.get_or_create(
                container=instance,
                var=env_var,
                defaults={"value": ""}  # ممكن تحط default من مكان آخر
            )
