from django.db import models
from tinymce.models import HTMLField

class BaseModel(models.Model):
    is_enabled = models.BooleanField(default=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True
        ordering = ['ordering']

class DocsServicesModel(BaseModel):
    project = models.OneToOneField("projects.AvailableProject", on_delete=models.CASCADE, null=True, related_name="docs")
    name = models.CharField("Service Name", max_length=254)
    desc = models.TextField("Service Description")

    def __str__(self):
        return self.name

class DocsServiceSectionsModel(BaseModel):
    name = models.CharField("Section Name", max_length=254)
    desc = models.TextField("Section Description")
    service = models.ForeignKey(DocsServicesModel, on_delete=models.CASCADE, related_name="sections")

    def __str__(self):
        return f'{self.name} - {self.service.name}'

class SectionContentsModel(BaseModel):
    section = models.ForeignKey(DocsServiceSectionsModel, on_delete=models.CASCADE, related_name="contents")
    name = models.CharField("Content Name", max_length=254)
    desc = models.TextField("Content Description")
    content = HTMLField()
    is_default_selected = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.section.name} - {self.name} - {self.section.service.name}'

    @property
    def get_title(self):
        return f'{self.name} - {self.section.service.name}'
