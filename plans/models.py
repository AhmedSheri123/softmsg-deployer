# plans/models.py
from django.db import models
from django.utils import timezone
from datetime import timedelta, date

SubscriptionsTheemChoices = (
    ('primary', 'primary'),
    ('secondary', 'secondary'),
    ('success', 'success'),
    ('danger', 'danger'),
    ('warning', 'warning'),
    ('info', 'info'),
    ('light', 'light'),
    ('dark', 'dark'),
)

plan_type_choices = [
    ('premium', 'Premium'),
    ('pro', 'PRO'),
    ('basic', 'Basic'),
]

database_type_choices = [
    ('sqlite', 'SQLite'),
    ('postgresql', 'PostgreSQL'),
]

class Plan(models.Model):
    project = models.ForeignKey('projects.AvailableProject', on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=100)  # Basic, Pro, Enterprise
    Theem = models.CharField(max_length=255, choices=SubscriptionsTheemChoices, null=True, verbose_name='الثيم')
    plan_type = models.CharField(max_length=255, choices=plan_type_choices, null=True, verbose_name='نو الاشتراك')
    ram = models.IntegerField(help_text="RAM بالـ MB")
    storage = models.IntegerField(help_text="Storage بالـ mb")
    cpu = models.DecimalField(max_digits=3, decimal_places=1, help_text="عدد الأنوية أو النسبة")
    database = models.CharField(max_length=255, choices=database_type_choices, null=True, verbose_name='قاعدة البيانات')
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    yearly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    def __str__(self):
        return f"{self.name} - {self.ram}MB / {self.storage}mb / {self.cpu} CPU"


class Subscription(models.Model):
    deployment = models.OneToOneField('deployments.Deployment', on_delete=models.CASCADE)
    plan = models.ForeignKey('Plan', on_delete=models.CASCADE)
    duration = models.CharField(max_length=10, choices=[('monthly','Monthly'),('yearly','Yearly')])
    price = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        # تعيين start_date إذا لم يكن موجود
        start = self.start_date or timezone.now()

        # تعيين end_date بناءً على المدة
        if not self.end_date:
            if self.duration == 'monthly':
                self.end_date = start + timedelta(days=30)
            elif self.duration == 'yearly':
                self.end_date = start + timedelta(days=365)

        # تعيين السعر إذا لم يكن محدد
        if not self.price:
            if self.duration == 'monthly':
                self.price = self.plan.monthly_price
            elif self.duration == 'yearly':
                self.price = self.plan.yearly_price

        super().save(*args, **kwargs)

    def has_sub(self):
        now = timezone.now()
        return self.start_date <= now <= self.end_date and self.is_active