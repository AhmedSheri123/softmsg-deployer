# projects/models.py
from django.db import models

class AvailableProject(models.Model):
    name = models.CharField(max_length=100)
    docker_image_name = models.CharField(max_length=100, null=True)
    has_frontend = models.BooleanField(default=False)
    frontend_docker_image_name = models.CharField(max_length=100, blank=True, null=True)
    has_redis = models.BooleanField(default=False)
    redis_docker_image_name = models.CharField(max_length=100, blank=True, null=True, default='redis:7')
    redis_host_env_var_name = models.CharField(max_length=100, blank=True, null=True, default="REDIS_HOST")
    redis_port_env_var_name = models.CharField(max_length=100, blank=True, null=True, default="REDIS_PORT")
    description = models.TextField()
    image = models.ImageField(upload_to="projects/", blank=True, null=True)

    def __str__(self):
        return self.name


class ActionModel(models.Model):
    label = models.CharField(max_length=100)
    project = models.ManyToManyField(AvailableProject, related_name="actions")

    # الأمر الفعلي لتنفيذه (مثل اسم الدالة أو سكربت shell)
    command = models.TextField(
        help_text="اسم الدالة أو الأمر لتنفيذه عبر Docker (مثلاً: change_admin_password)"
    )


    class Meta:
        ordering = ["label"]
        
    def __str__(self):
        projects = ', '.join([p.name for p in self.project.all()])  # استخدم حقل نصي مثل name
        return f'{projects}|{self.label}'


class ActionParameterModel(models.Model):
    action = models.ForeignKey(ActionModel, on_delete=models.CASCADE, related_name="parameters")
    label = models.CharField(max_length=100, blank=True, null=True, help_text="الاسم المعروض للمستخدم")
    name = models.CharField(max_length=50, help_text="الاسم الداخلي (للاستخدام في الكود/الـcommand)")
    data_type = models.CharField(
        max_length=20,
        choices=[("string", "string"), ("boolean", "boolean"), ("int", "integer")]
    )
    required = models.BooleanField(default=True)
    default = models.CharField(max_length=100, blank=True, null=True)

    def display_label(self):
        return self.label or self.name  # fallback لو ما تعبت label
    
    def __str__(self):
        return f'action={self.action}|{self.display_label()}|'




class EnvVarModel(models.Model):
    project = models.ForeignKey(AvailableProject, on_delete=models.CASCADE, null=True)
    label = models.CharField(max_length=100)
    key = models.CharField(max_length=100)
    is_secret = models.BooleanField(default=False, help_text="اخفاء")
    required = models.BooleanField(default=False)
    class Meta:
        unique_together = ("project", "key")
        ordering = ["key"]

    def __str__(self):
        return f"|{self.label}|{self.key}|"
