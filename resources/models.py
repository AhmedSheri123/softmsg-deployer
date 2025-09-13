from django.db import models
from tinymce.models import HTMLField
# Create your models here.

class DocsServicesModel(models.Model):
    name = models.CharField("Service Name", max_length=254)
    desc = models.TextField("Service Description")
    is_enabled = models.BooleanField(default=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    ordering = models.CharField(max_length=254, default='0')

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['ordering']

class DocsServiceSectionsModel(models.Model):
    name = models.CharField("Section Name", max_length=254)
    desc = models.TextField("Section Description")
    service = models.ForeignKey(DocsServicesModel, on_delete=models.CASCADE)
    is_enabled = models.BooleanField(default=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    ordering = models.CharField(max_length=254, default='0')

    def __str__(self):
        return f'{self.name} - {self.service.name}'

class SectionContentsModel(models.Model):
    section = models.ForeignKey(DocsServiceSectionsModel, on_delete=models.CASCADE)
    name = models.CharField("Content Name", max_length=254)
    desc = models.TextField("Content Description")
    content = HTMLField()
    is_enabled = models.BooleanField(default=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    ordering = models.CharField(max_length=254, default='0')
    is_default_selected = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.section.name} - {self.name} - {self.section.service.name}'
    
    @property
    def get_title(self):
        return f'{self.name} - {self.section.service.name}'

    class Meta:
        ordering = ['ordering']