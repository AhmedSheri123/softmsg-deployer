# from django.contrib import admin
# from .models import DocsServiceSectionsModel, DocsServicesModel, SectionContentsModel

# # Register your models here.
# admin.site.register(DocsServiceSectionsModel)
# admin.site.register(DocsServicesModel)
# admin.site.register(SectionContentsModel)


from django.contrib import admin
from modeltranslation.admin import TranslationAdmin
from .models import DocsServiceSectionsModel, DocsServicesModel, SectionContentsModel
from modeltranslation.admin import TabbedTranslationAdmin

@admin.register(DocsServicesModel)
class DocsServicesAdmin(TabbedTranslationAdmin):
    list_display = ('name', 'project', 'is_enabled')
    search_fields = ('name',)

@admin.register(DocsServiceSectionsModel)
class ServiceSectionsAdmin(TabbedTranslationAdmin):
    list_display = ('name', 'service', 'is_enabled')
    search_fields = ('name',)

@admin.register(SectionContentsModel)
class SectionContentsAdmin(TabbedTranslationAdmin):
    list_display = ('name', 'section', 'is_enabled')
    search_fields = ('name',)