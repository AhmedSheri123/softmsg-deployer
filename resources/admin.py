# from django.contrib import admin
# from .models import DocsServiceSectionsModel, DocsServicesModel, SectionContentsModel

# # Register your models here.
# admin.site.register(DocsServiceSectionsModel)
# admin.site.register(DocsServicesModel)
# admin.site.register(SectionContentsModel)


from django.contrib import admin
from modeltranslation.admin import TranslationAdmin
from .models import DocsServiceSectionsModel, DocsServicesModel, SectionContentsModel

@admin.register(DocsServiceSectionsModel)
class SectionsAdmin(TranslationAdmin):
    pass

@admin.register(DocsServicesModel)
class DocsAdmin(TranslationAdmin):
    pass

@admin.register(SectionContentsModel)
class ContentsAdmin(TranslationAdmin):
    pass
