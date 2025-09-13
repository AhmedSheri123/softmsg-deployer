from django.db import models
from django.utils.translation import gettext as _

# Create your models here.

class ContactModel(models.Model):
    full_name = models.CharField(max_length=100, verbose_name=_("Full Name"))
    email = models.EmailField(verbose_name=("Email address"))
    phone_number = models.CharField(max_length=100, verbose_name=("Phone Number"))
    project_title = models.CharField(max_length=100, verbose_name=("Project Title"))
    project_description = models.TextField(verbose_name=("Project Description"))
    similar_websites = models.TextField(verbose_name=("Examples of similar websites"), blank=True)
    expected_budget = models.TextField(max_length=100, verbose_name=("Expected budget"), blank=True)

    creation_date = models.DateTimeField(auto_now_add=False, null=True, blank=True)

    def __str__(self):
        return str(self.full_name)
    

class SubscribeToUsModel(models.Model):
    email = models.EmailField(verbose_name=("Email address"), unique=True)
    def __str__(self):
        return str(self.email)