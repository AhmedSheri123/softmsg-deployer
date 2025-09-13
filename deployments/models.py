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
    port = models.CharField(max_length=255, blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    container_name = models.CharField(max_length=255, blank=True, null=True)
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
        return f"{self.user.username} - {self.project.name} ({self.plan.name})"
    

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
    

class DeploymentEnvVar(models.Model):
    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE, null=True)
    var_name = models.ForeignKey('projects.EnvVarModel', on_delete=models.CASCADE, null=True)
    value = models.CharField(max_length=255, blank=True, null=True)