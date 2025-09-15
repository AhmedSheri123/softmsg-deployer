from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Deployment, DeploymentEnvVar
from projects.models import EnvVarModel

@receiver(post_save, sender=Deployment)
def create_deployment_env_vars(sender, instance, created, **kwargs):
    """
    عند إنشاء Deployment جديد، ننشئ متغيرات البيئة الخاصة بالمشروع.
    يُفترض أن جميع الحقول المهمة مثل domain و container_name جاهزة.
    """
    if created:
        project = instance.project
        for env_var in EnvVarModel.objects.filter(project=project):
            # نحاول استخدام default_value مع format
            value = ""
            if env_var.default_value:
                try:
                    value = env_var.default_value.format(self=instance)
                except Exception:
                    value = env_var.default_value  # fallback لو حصل خطأ
            # إنشاء أو تحديث DeploymentEnvVar
            DeploymentEnvVar.objects.update_or_create(
                deployment=instance,
                var_name=env_var,
                defaults={"value": value}
            )
