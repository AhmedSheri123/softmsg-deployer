# deployments/models.py
from django.db import models
from django.contrib.auth.models import User
from projects.models import AvailableProject
from plans.models import Plan
from django.utils.translation import gettext_lazy as _ 

service_progress_choices = [
    (1, _('Create Project')),
    (2, _('Billing')),
    (3, _('Deploying')),
    (4, _('Completed')),
    (5, _('Failed')),
]

service_status_choices = [
    (1, _('Stopped')),
    (2, _('Running')),
    (3, _('Undefined')),
]



class Deployment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey(AvailableProject, on_delete=models.CASCADE)

    domain = models.CharField(max_length=255, blank=True, null=True)
    frontend_domain = models.CharField(max_length=255, blank=True, null=True)   # frontend 
    port = models.CharField(max_length=255, blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    container_name = models.CharField(max_length=255, blank=True, null=True)
    frontend_container_name = models.CharField(max_length=100, blank=True, null=True)
    redis_container_name = models.CharField(max_length=100, blank=True, null=True)

    volume_media = models.CharField(max_length=255, blank=True, null=True)
    version = models.CharField(max_length=50, default="1.0")
    

    
    progress = models.IntegerField(choices=service_progress_choices, null=True, verbose_name=_("Progress"))
    status = models.IntegerField(choices=service_status_choices, null=True, verbose_name=_("Status"))
    is_active = models.BooleanField(default=True)
    
    used_ram = models.IntegerField(null=True, blank=True, help_text=_("RAM used in MB"))
    used_storage = models.IntegerField(null=True, blank=True, help_text=_("Storage used in GB"))
    used_cpu = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, help_text=_("CPU cores used"))
    
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.project.name} ({self.plan.name if self.plan else 'No Plan'})"

    

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

    def get_env_var(self):
        """
        ترجع قاموس {key: value} لجميع متغيرات البيئة الخاصة بهذا الـ Deployment
        """
        env_vars = {}
        for env in DeploymentEnvVar.objects.filter(deployment=self):
            if env.var_name and env.var_name.key:
                env_vars[env.var_name.key] = env.value
        return env_vars


    def update_default_env_vars(self):
        """
        تقوم بتعبئة جميع DeploymentEnvVar الفارغة بالقيم الافتراضية
        من var_name.default_value مع دعم تعابير format مثل {self.id} أو {self.domain}.
        """
        env_vars = DeploymentEnvVar.objects.filter(deployment=self)
        for env in env_vars:
            if (not env.value or env.value.strip() == "") and env.var_name and env.var_name.default_value:
                try:
                    # استخدام format لدعم {self} داخل default_value
                    env.value = env.var_name.default_value.format(self=self)
                except Exception:
                    env.value = env.var_name.default_value  # fallback لو حصل خطأ
                env.save()

class DeploymentEnvVar(models.Model):
    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE, null=True)
    var_name = models.ForeignKey('projects.EnvVarModel', on_delete=models.CASCADE, null=True)
    value = models.CharField(max_length=255, blank=True, null=True)
