#deployments\models.py

from django.db import models
from django.contrib.auth.models import User
from projects.models import AvailableProject, EnvVar

SERVICE_PROGRESS = [
    (1, 'Create Project'),
    (2, 'Billing'),
    (3, 'Deploying'),
    (4, 'Completed'),
    (5, 'Failed'),
]

SERVICE_STATUS = [
    (1, 'Stopped'),
    (2, 'Running'),
    (3, 'Undefined'),
]


class Deployment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey(AvailableProject, on_delete=models.CASCADE)

    
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    version = models.CharField(max_length=50, default="1.0")

    progress = models.IntegerField(choices=SERVICE_PROGRESS, null=True)
    status = models.IntegerField(choices=SERVICE_STATUS, null=True)
    is_active = models.BooleanField(default=True)

    used_ram = models.PositiveIntegerField(blank=True, null=True, help_text="RAM used in MB")
    used_storage = models.PositiveIntegerField(blank=True, null=True, help_text="Storage used in GB")
    used_cpu = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True, help_text="CPU cores used")
    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.project.name}"



    @property
    def subscription(self):
        """ترجع الاشتراك المرتبط بهذا الـ Deployment أو None"""
        from plans.models import Subscription
        try:
            return Subscription.objects.get(deployment=self)
        except Subscription.DoesNotExist:
            return None
    @property
    def plan(self):
        return self.subscription.plan
    
    def subscription_status(self):
        """ترجع True إذا الاشتراك نشط وجاري"""
        sub = self.subscription
        if sub:
            return sub.has_sub()
        return False

    @property    
    def domain(self):
        pc = self.project.containers.all()
        if pc.filter(type='backfront').exists():
            return self.containers.get(project_container__type='backfront').domain
        elif pc.filter(type='frontend').exists():
            return self.containers.get(project_container__type='frontend').domain
        else:return 'N/A'
    @property
    def backend_domain(self):
        pc = self.project.containers.all()
        if pc.filter(type='backend').exists():
            return self.containers.get(project_container__type='backend').domain
        else:return 'N/A'

class DeploymentContainer(models.Model):
    STATUS_CHOICES = [(1,'Pending'),(2,'Running'),(3,'Error')]

    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE, related_name="containers")
    project_container = models.ForeignKey('projects.ProjectContainer', on_delete=models.CASCADE, null=True)
    container_name = models.CharField(max_length=255)
    domain = models.CharField(max_length=255, blank=True, null=True)
    env_vars = models.JSONField(default=dict, blank=True)
    port = models.PositiveIntegerField(blank=True, null=True)
    status = models.IntegerField(choices=STATUS_CHOICES, default=1)

    def __str__(self):
        return f"{self.deployment} | {self.container_name}"

    def get_env_var(self):
        """
        ترجع قاموس {key: value} لجميع متغيرات البيئة الخاصة بهذا الـ Deployment
        """
        env_vars = {}
        for env in DeploymentContainerEnvVar.objects.filter(container=self):
            if env.var and env.var.key:
                env_vars[env.var.key] = env.value
        return env_vars


    def update_default_env_vars(self):
        """
        تقوم بتعبئة جميع DeploymentEnvVar الفارغة بالقيم الافتراضية
        من var.default_value مع دعم تعابير format مثل {self.id} أو {self.domain}.
        """
        env_vars = DeploymentContainerEnvVar.objects.filter(container=self)
        for env in env_vars:
            if (not env.value or env.value.strip() == "") and env.var and env.var.default_value:
                try:
                    # استخدام format لدعم {self} داخل default_value
                    env.value = env.var.default_value.format(container=self)
                except Exception:
                    env.value = env.var.default_value  # fallback لو حصل خطأ
                env.save()


class DeploymentContainerVolume(models.Model):
    container = models.ForeignKey(DeploymentContainer, on_delete=models.CASCADE, related_name="volumes")
    path = models.CharField(max_length=255, help_text="Path on container/server")
    description = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.container} | {self.path}"


class DeploymentContainerEnvVar(models.Model):
    container = models.ForeignKey(DeploymentContainer, on_delete=models.CASCADE, null=True, related_name="envs")
    var = models.ForeignKey('projects.EnvVar', on_delete=models.CASCADE, null=True)
    value = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.deployment} | {self.var.key} | {self.value}"
