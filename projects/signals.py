# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import EnvVar
from deployments.models import DeploymentContainer, DeploymentContainerEnvVar

@receiver(post_save, sender=EnvVar)
def add_env_var_to_deployments(sender, instance, created, **kwargs):
    """
    لما نضيف EnvVarModel جديد لمشروع,
    يتم إنشاؤه (أو ربطه) في جميع Deployments الخاصة بهذا المشروع.
    """
    if created:  # فقط عند الإضافة لأول مرة
        project_container = instance.title.project_container
        for dc in DeploymentContainer.objects.filter(project_container=project_container):
            DeploymentContainerEnvVar.objects.get_or_create(
                container=dc,
                var=instance,
                defaults={"value": ""}  # ممكن تعطي default
            )
