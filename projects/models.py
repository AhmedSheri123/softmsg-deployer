from django.db import models

class AvailableProject(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="projects/", blank=True, null=True)

    def __str__(self):
        return self.name


class ProjectContainer(models.Model):
    CONTAINER_TYPES = [
        ('backfront', 'Backend&Frontend'),
        ('backend', 'Backend'),
        ('frontend', 'Frontend'),
        ('redis', 'Redis'),
    ]
    
    TECHNOLOGY_CHOICES = [
        ('django', 'Django'),
        ('node', 'Node.js'),
        ('laravel', 'Laravel'),
        ('php', 'PHP'),
        ('react', 'React'),
        ('vue', 'Vue.js'),
    ]

    

    project = models.ForeignKey(AvailableProject, on_delete=models.CASCADE, related_name="containers")
    type = models.CharField(max_length=20, choices=CONTAINER_TYPES)
    technology = models.CharField(max_length=50, choices=TECHNOLOGY_CHOICES, blank=True, null=True)
    docker_image_name = models.CharField(max_length=200)
    env_vars = models.JSONField(default=dict, blank=True, help_text="{deployment}, {this_container_domain}, {frontend_domain}, {backfront_domain}, {db_name}, {db_user}, {db_pass}, {db_container_name}")
    default_port = models.PositiveIntegerField(blank=True, null=True)
    volume = models.JSONField(default=list, blank=True, help_text="List of volume paths")
    script_run_after_install = models.TextField(help_text="{container.id}", blank=True)

    def __str__(self):
        return f"{self.project.name} - {self.type}"


class Action(models.Model):
    label = models.CharField(max_length=100)
    container = models.ManyToManyField(ProjectContainer, related_name="actions")
    command = models.TextField(help_text="اسم الدالة أو الأمر لتنفيذه عبر Docker")

    class Meta:
        ordering = ["label"]

    def __str__(self):
        projects = ', '.join([str(p) for p in self.container.all()])
        return f"{projects} | {self.label}"


class ActionParameter(models.Model):
    DATA_TYPES = [("string", "String"), ("boolean", "Boolean"), ("int", "Integer")]

    action = models.ForeignKey(Action, on_delete=models.CASCADE, related_name="parameters")
    label = models.CharField(max_length=100, blank=True, null=True)
    name = models.CharField(max_length=50, help_text="الاسم الداخلي للاستخدام بالكود")
    data_type = models.CharField(max_length=20, choices=DATA_TYPES)
    required = models.BooleanField(default=True)
    default = models.CharField(max_length=100, blank=True, null=True, help_text="{deployment.id}")

    def display_label(self):
        return self.label or self.name

    def __str__(self):
        return f"{self.action} | {self.display_label()}"

class EnvVarsTitle(models.Model):
    title = models.CharField(max_length=100)
    project_container = models.ForeignKey(ProjectContainer, on_delete=models.CASCADE, null=True, related_name='project_title_envs')

    def __str__(self):
        return f"{self.title}-{self.project_container}"
    
class EnvVar(models.Model):
    DATA_TYPES = [("string", "String"), ("boolean", "Boolean"), ("int", "Integer")]
    
    title = models.ForeignKey(EnvVarsTitle, on_delete=models.SET_NULL, null=True, blank=True, related_name='project_envs')
    label = models.CharField(max_length=100)
    key = models.CharField(max_length=100)
    data_type = models.CharField(max_length=20, choices=DATA_TYPES, null=True)
    is_secret = models.BooleanField(default=False)
    required = models.BooleanField(default=False)
    default_value = models.CharField(max_length=100, help_text="{container.deployment.id}", blank=True)
    sort_index = models.IntegerField(default=0)

    class Meta:
        unique_together = ("title", "key")
        ordering = ["-sort_index"]

    def __str__(self):
        return f"{self.title} | {self.key}"
