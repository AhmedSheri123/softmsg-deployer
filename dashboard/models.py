from django.db import models
from django.contrib.auth.models import User
import random, string, datetime
from django.utils.translation import gettext_lazy as _ 
# Create your models here.

def payOrderCodeGen(N = 4):
    res = ''.join(random.choices(string.digits, k=N))
    order = ServicePaymentOrderModel.objects.filter(orderID=res)
    if order.exists():
        res = payOrderCodeGen(N+1)
    return 'o' + str(res)

def payOrderSecretCodeGen():
    N = 99
    res = ''.join(random.choices((string.digits+string.ascii_letters), k=N))
    return str(res)

services_choices = [
    ('1', _('Patient Management')),
    ('2', _('School Management')),
    ('3', _('HR Management')),
]

plan_scope_choices = [
    ('1', _('Monthly')),
    ('2', _('Yearly'))
]

order_progress_choices = [
    ('1', _('Pending')),
    ('2', _('Paid')),
    ('3', _('Complited')),
    ('4', _('Cancelled'))
]

user_service_progress_choices = [
    ('1', _('Create Project')),
    ('2', _('Choose Plan')),
    ('3', _('Project Settings')),
    ('4', _('Complited'),
)]

system_progress_choices = [
    ('1', _('Pending')),
    ('2', _('Building')),
    ('3', _('Complited')),
    ('4', _('Failed'),
)]

class ServicesModel(models.Model):
    title = models.CharField(max_length=254, verbose_name=_("Service Title"))
    sub_title = models.TextField(verbose_name=_("Subtitle"))
    service = models.CharField(max_length=254, choices=services_choices, verbose_name=_("Service"))

    creation_datetime = models.DateTimeField(auto_now_add=True, verbose_name=_("Creation Date"))

    class Meta:
        verbose_name = _("Service Model")
        verbose_name_plural = _("Service Models")

    def __str__(self):
        return str(self.get_service_display())


class UserServiceModel(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, verbose_name=_("User"))
    project_name = models.CharField(max_length=254, null=True, verbose_name=_("Project Name"))
    service = models.ForeignKey(ServicesModel, on_delete=models.CASCADE, null=True, verbose_name=_("Service"))
    progress = models.CharField(max_length=254, choices=user_service_progress_choices, null=True, verbose_name=_("Progress"))

    service_subscription_id = models.CharField(max_length=254, null=True, verbose_name=_("Service Subscription ID"))
    service_user_id = models.CharField(max_length=254, null=True, verbose_name=_("Service User ID"))
    service_subscription_date = models.CharField(max_length=254, null=True, verbose_name=_("Service Subscription Date"))
    plan_scope = models.CharField(max_length=254, choices=plan_scope_choices, null=True, verbose_name=_("Plan Scope"))
    
    system_port = models.CharField(max_length=254, null=True, blank=True, verbose_name=_("system_port"), unique=True)
    subdomain = models.CharField(max_length=254, null=True, blank=True, verbose_name=_("Subdomain"))
    system_progress = models.CharField(max_length=254, default='1', choices=system_progress_choices, null=True, verbose_name=_("System Progress"))

    creation_datetime = models.DateTimeField(auto_now_add=True, verbose_name=_("Creation Date"))

    class Meta:
        verbose_name = _("User Service Model")
        verbose_name_plural = _("User Service Models")

    def __str__(self):
        return str(self.project_name)

    @property
    def get_avarible_port(self):
        """
        دالة لتوليد منفذ فريد غير مستخدم.
        """
        # البحث عن المنافذ المحجوزة
        reserved_ports = UserServiceModel.objects.exclude(system_port__isnull=True).values_list('system_port', flat=True)

        # البحث عن منفذ متاح
        for port in range(9000, 65535):
            port = str(port)
            if port not in reserved_ports:
                # إذا كان المنفذ غير محجوز، يتم إرجاعه
                return port

        # في حال لم يوجد منفذ متاح
        return None

    def get_unique_subdomain(self, subdomain):
        """
        دالة للتحقق مما إذا كان الـ subdomain موجودًا بالفعل في قاعدة البيانات.
        إذا كان موجودًا، سيتم إرجاع قيمة فريدة بتعديل الاسم.
        """
        subdomain = 'ppp' + subdomain.replace(" ", "")
        original_subdomain = subdomain
        counter = 1

        # التحقق من وجود الـ subdomain في قاعدة البيانات
        while UserServiceModel.objects.filter(subdomain=subdomain).exists():
            subdomain = f"{original_subdomain}{counter}"  # إضافة رقم لتمييز الـ subdomain
            counter += 1

        return subdomain

    @property
    def remaining_subscription(self):
        subscription_date = self.service_subscription_date
        if subscription_date:
            subscription_days = 30 if self.plan_scope else 365
            subscription_end_date = (datetime.timedelta(days=subscription_days) + subscription_date) - subscription_date


