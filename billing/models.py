from django.db import models
import random, string
from django.utils.translation import gettext_lazy as _ 

def payOrderCodeGen(N=4):
    res = ''.join(random.choices(string.digits, k=N))
    order = ServicePaymentOrderModel.objects.filter(orderID=res)
    if order.exists():
        res = payOrderCodeGen(N+1)
    return 'o' + str(res)

def payOrderSecretCodeGen():
    N = 99
    res = ''.join(random.choices((string.digits + string.ascii_letters), k=N))
    return str(res)

order_progress_choices = [
    ('1', _('Pending')),
    ('2', _('Paid')),
    ('3', _('Completed')),
    ('4', _('Cancelled'))
]

class ServicePaymentOrderModel(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, null=True)
    plan = models.ForeignKey('plans.Plan', on_delete=models.CASCADE)
    project = models.ForeignKey('projects.AvailableProject', on_delete=models.CASCADE, null=True)
    duration = models.CharField(max_length=10, choices=[('monthly','Monthly'),('yearly','Yearly')], null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    orderID = models.CharField(max_length=250, default=payOrderCodeGen, unique=True, verbose_name=_("Order ID"))
    order_secret = models.CharField(max_length=254, default=payOrderSecretCodeGen, unique=True, verbose_name=_("Order Secret Code"))
    transactionNo = models.CharField(max_length=250, null=True, blank=True, verbose_name=_("Transaction Number"))
    progress = models.CharField(max_length=254, default='1', choices=order_progress_choices, verbose_name=_("Order Progress"))
    creation_date = models.DateTimeField(auto_now_add=True, verbose_name=_("Creation Date"), null=True)

    class Meta:
        verbose_name = _("Service Payment Order")
        verbose_name_plural = _("Service Payment Orders")
        ordering = ['-creation_date']   # الأحدث أولاً

    def __str__(self):
        return f'Order {self.orderID} - {self.get_progress_display()}'
