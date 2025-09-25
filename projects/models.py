#projects\models.py
from django.db import models
from tinymce.models import HTMLField
from django.db.models import Avg
from django.utils import timezone
from datetime import timedelta
from django.utils.translation import gettext_lazy as _

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Name"))
    slug = models.SlugField(unique=True, blank=True, null=True, verbose_name=_("Slug"))

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")

    def __str__(self):
        return self.name

class AvailableProject(models.Model):
    DIFFICULTY_CHOICES = [
        ("beginner", _("Beginner")),
        ("intermediate", _("Intermediate")),
        ("advanced", _("Advanced")),
    ]

    name = models.CharField(max_length=100, verbose_name=_("Project Name"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    image = models.ImageField(upload_to="projects/", blank=True, null=True, verbose_name=_("Image"))
    categories = models.ManyToManyField("Category", related_name="projects", blank=True, verbose_name=_("Categories"))

    # New fields
    difficulty_level = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default="beginner",
        verbose_name=_("Difficulty Level")
    )
    install_time_minutes = models.PositiveIntegerField(
        default=5,
        verbose_name=_("Estimated Install Time (minutes)")
    )
    disk_size_mb = models.PositiveIntegerField(
        default=500,
        verbose_name=_("Required Disk Size (MB)")
    )

    minimum_operating_requirements = models.ForeignKey(
        "plans.Plan",
        verbose_name=_("Minimum Operating Requirements"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    is_open_source = models.BooleanField(default=False)
    source_code_url = models.URLField(max_length=200, blank=True, null=True) 
    install_steps = HTMLField(blank=True, verbose_name=_("Installation Steps"))
    installs = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Number of Installs")
    )
    downloads = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Number of source code downloads")
    )
    
    about = HTMLField(blank=True, verbose_name=_("About Project"))
    pub_date = models.DateTimeField(auto_now_add=True, null=True, verbose_name=_("Publication Date"))
    
    def __str__(self):
        return self.name

    # -------------------------
    # دالة لحساب متوسط التقييم
    # -------------------------
    @property
    def average_rating_float(self):
        """إرجاع متوسط التقييم كعدد عشري بدقة منزل عشرية واحدة"""
        avg = self.reviews.aggregate(average=Avg("rating"))["average"]
        return round(avg or 0, 1)

    @property
    def rating_stars(self):
        """
        إرجاع قائمة النجوم: 'full', 'half', 'empty'
        بحيث يتم حساب النصف نجمة بدقة
        """
        avg = self.average_rating_float
        full_stars = int(avg)  # عدد النجوم الكاملة
        decimal_part = avg - full_stars  # الجزء العشري

        stars = []

        # إضافة النجوم الكاملة
        for _ in range(full_stars):
            stars.append('full')

        # إضافة نصف نجمة إذا كان الجزء العشري بين 0.25 و 0.75
        if 0.25 <= decimal_part < 0.75:
            stars.append('half')
        # إذا كان الجزء العشري أكبر أو يساوي 0.75 نضيف نجمة كاملة إضافية
        elif decimal_part >= 0.75:
            stars.append('full')

        # إكمال الباقي بالنجوم الفارغة
        while len(stars) < 5:
            stars.append('empty')

        return stars

    def get_sorted_containers(self):
        CONTAINER_PRIORITY = {
            'db': 1,
            'backend': 2,
            'backfront': 2,
            'frontend': 3,
            'redis': 4,
            'worker': 5,
            'proxy': 6,
        }
        containers = list(self.containers.all())
        containers.sort(key=lambda c: CONTAINER_PRIORITY.get(c.type, 99))
        return containers
    
    @property
    def is_new(self):
        """إرجاع True إذا لم يمر على تاريخ النشر أكثر من 7 أيام"""
        if not self.pub_date:
            return False
        return timezone.now() - self.pub_date <= timedelta(days=7)

    @property
    def get_installs_and_downloads(self):
        return self.installs + self.downloads        


class ProjectContainer(models.Model):
    # -------------------------
    # أنواع الحاويات
    # -------------------------
    CONTAINER_TYPES = [
        ('backfront', 'Backend & Frontend'),
        ('backend', 'Backend'),
        ('frontend', 'Frontend'),
        ('redis', 'Redis'),
        ('db', 'Database'),
        ('worker', 'Worker / Celery'),
        ('proxy', 'Reverse Proxy'),
    ]

    # -------------------------
    # التقنيات (Frameworks / Libraries)
    # -------------------------
    TECHNOLOGY_CHOICES = [
        ('django', 'Django'),
        ('fastapi', 'FastAPI'),
        ('flask', 'Flask'),
        ('node', 'Node.js'),
        ('express', 'Express.js'),
        ('laravel', 'Laravel'),
        ('spring', 'Spring Boot'),
        ('dotnet', '.NET'),
        ('php', 'PHP (Raw)'),
        ('react', 'React'),
        ('vue', 'Vue.js'),
        ('angular', 'Angular'),
        ('svelte', 'Svelte'),
    ]

    # -------------------------
    # اللغات الأساسية
    # -------------------------
    LANGUAGE_CHOICES = [
        ('python', 'Python'),
        ('javascript', 'JavaScript'),
        ('typescript', 'TypeScript'),
        ('php', 'PHP'),
        ('java', 'Java'),
        ('csharp', 'C#'),
        ('go', 'Go'),
        ('ruby', 'Ruby'),
        ('postgresql', 'PostgreSQL'),
    ]


    # -------------------------
    # الحقول الأساسية
    # -------------------------
    project = models.ForeignKey(
        "AvailableProject", 
        on_delete=models.CASCADE, 
        related_name="containers",
        help_text="المشروع الذي ينتمي له هذا الكونتينر"
    )
    type = models.CharField(max_length=20, choices=CONTAINER_TYPES)
    technology = models.CharField(max_length=50, choices=TECHNOLOGY_CHOICES, blank=True, null=True)
    language = models.CharField(max_length=50, choices=LANGUAGE_CHOICES, blank=True, null=True)

    docker_image_name = models.CharField(
        max_length=200,
        help_text="اسم صورة Docker مثل: postgres:14 أو nginx:latest"
    )

    have_main_domain = models.BooleanField(default=False)

    env_vars = models.JSONField(
        default=dict,
        blank=True,
        help_text="""
        يمكنك استخدام placeholders ديناميكية داخل القيم:
        - الكونتينر الحالي: {container.container_name}, {container.domain}, {container.env.VAR_NAME}
        - كونتينرات أخرى حسب النوع أو الاسم: {container.db.env.POSTGRES_USER}, {container.frontend.domain}
        - Deployment والـ Plan: {container.deployment.id}, {container.deployment.plan.ram}, {container.deployment.plan.cpu}
        - متغيرات عامة: {frontend_domain}, {backfront_domain}
        مثال:
        {
            "DJANGO_ALLOWED_HOSTS": "{container.frontend.domain},127.0.0.1,localhost",
            "DATABASE_URL": "postgres://{container.db.env.POSTGRES_USER}:{container.db.env.POSTGRES_PASSWORD}@{container.db.container_name}:5432/{container.db.env.POSTGRES_DB}"
        }
        """
    )

    default_port = models.PositiveIntegerField(
        blank=True, null=True,
        help_text="المنفذ الافتراضي داخل الكونتينر"
    )

    ports = models.JSONField(
        default=list, blank=True,
        help_text="قائمة المنافذ لربط {host:container} مثل [{'8000':'80'}]"
    )

    volume = models.JSONField(
        default=list, blank=True,
        help_text="قائمة المجلدات المربوطة {host:container}"
    )

    networks = models.JSONField(
        default=list, blank=True,
        help_text="الشبكات التي سينضم إليها الكونتينر"
    )

    working_dir = models.CharField(
        max_length=255, blank=True, null=True,
        help_text="الدليل الافتراضي الذي يبدأ فيه الكونتينر"
    )

    entrypoint = models.TextField(
        blank=True, null=True,
        help_text="استبدال الـ Entrypoint الافتراضي للصورة"
    )

    command = models.TextField(
        blank=True, null=True,
        help_text="الأمر الذي يُنفذ عند تشغيل الكونتينر"
    )

    labels = models.JSONField(
        default=dict, blank=True,
        help_text="Labels key:value metadata"
    )

    privileged = models.BooleanField(
        default=False,
        help_text="تشغيل الكونتينر بوضع Privileged (صلاحيات كاملة)"
    )

    restart_policy = models.CharField(
        max_length=20,
        choices=[('no', 'No'), ('always', 'Always'), ('on-failure', 'On Failure'), ('unless-stopped', 'Unless Stopped')],
        default="unless-stopped",
        help_text="سياسة إعادة التشغيل للكونتينر"
    )

    script_run_after_install = models.TextField(
        help_text="سكريبت يتم تنفيذه بعد تثبيت الكونتينر. يمكن أن يحتوي {container.id}",
        blank=True
    )

    # -------------------------
    # طرق env_vars
    # -------------------------
    def get_env_vars(self):
        return self.env_vars or {}

    def get_env_vars_list(self):
        return list(self.get_env_vars().items())

    def get_env_var(self, key, default=None):
        return self.get_env_vars().get(key, default)





class Action(models.Model):
    label = models.CharField(_("Label"), max_length=100)
    container = models.ManyToManyField("ProjectContainer", related_name="actions")
    command = models.TextField(_("Command"), help_text=_("The function name or command to execute via Docker"))

    class Meta:
        ordering = ["label"]

    def __str__(self):
        projects = ', '.join([str(p) for p in self.container.all()])
        return f"{projects} | {self.label}"


class ActionParameter(models.Model):
    DATA_TYPES = [
        ("string", _("String")),
        ("boolean", _("Boolean")),
        ("int", _("Integer"))
    ]

    action = models.ForeignKey(Action, on_delete=models.CASCADE, related_name="parameters")
    label = models.CharField(_("Label"), max_length=100, blank=True, null=True)
    name = models.CharField(_("Internal Name"), max_length=50, help_text=_("Internal name for code usage"))
    data_type = models.CharField(_("Data Type"), max_length=20, choices=DATA_TYPES)
    required = models.BooleanField(_("Required"), default=True)
    default = models.CharField(_("Default Value"), max_length=100, blank=True, null=True, help_text=_("{deployment.id}"))

    def display_label(self):
        return self.label or self.name

    def __str__(self):
        return f"{self.action} | {self.display_label()}"

class EnvVarsTitle(models.Model):
    title = models.CharField(_("Title"), max_length=100)
    project_container = models.ForeignKey(
        "ProjectContainer", 
        on_delete=models.CASCADE, 
        null=True, 
        related_name='project_title_envs'
    )

    def __str__(self):
        return f"{self.title} - {self.project_container}"


class EnvVar(models.Model):
    DATA_TYPES = [
        ("string", _("String")), 
        ("boolean", _("Boolean")), 
        ("int", _("Integer"))
    ]
    
    title = models.ForeignKey(
        EnvVarsTitle, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='project_envs'
    )
    label = models.CharField(_("Label"), max_length=100)
    key = models.CharField(_("Key"), max_length=100)
    data_type = models.CharField(_("Data Type"), max_length=20, choices=DATA_TYPES, null=True)
    is_secret = models.BooleanField(_("Is Secret"), default=False)
    required = models.BooleanField(_("Required"), default=False)
    default_value = models.CharField(_("Default Value"), max_length=100, help_text=_("{container.deployment.id}"), blank=True)
    sort_index = models.IntegerField(_("Sort Index"), default=0)

    class Meta:
        unique_together = ("title", "key")
        ordering = ["-sort_index"]

    def __str__(self):
        return f"{self.title} | {self.key}"



class ProjectReview(models.Model):
    project = models.ForeignKey(AvailableProject, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(default=5)  # من 1 الى 5
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("project", "user")



class ProjectDBConfig(models.Model):
    project = models.OneToOneField(AvailableProject, on_delete=models.CASCADE, related_name="db_config")
    
    db_name = models.CharField(max_length=255, help_text="POSTGRES_DB")
    db_user = models.CharField(max_length=255, blank=True, null=True, help_text="POSTGRES_USER")
    db_password = models.CharField(max_length=255, blank=True, null=True, help_text="POSTGRES_PASS")
    db_port = models.PositiveIntegerField(blank=True, null=True, help_text="POSTGRES_PORT")
    
    def __str__(self):
        return f"{self.project} DB Config"

    def is_valid(self):
        """تتحقق إذا كانت البيانات كافية للنسخ الاحتياطي"""
        return bool(self.db_name and self.db_user)

