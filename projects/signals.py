# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import EnvVarModel
from deployments.models import Deployment, DeploymentEnvVar

@receiver(post_save, sender=EnvVarModel)
def add_env_var_to_deployments(sender, instance, created, **kwargs):
    """
    لما نضيف EnvVarModel جديد لمشروع,
    يتم إنشاؤه (أو ربطه) في جميع Deployments الخاصة بهذا المشروع.
    """
    if created:  # فقط عند الإضافة لأول مرة
        project = instance.project
        for deployment in Deployment.objects.filter(project=project):
            DeploymentEnvVar.objects.get_or_create(
                deployment=deployment,
                var_name=instance,
                defaults={"value": ""}  # ممكن تعطي default
            )
