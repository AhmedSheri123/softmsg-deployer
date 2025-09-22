from modeltranslation.translator import register, TranslationOptions
from .models import DocsServiceSectionsModel, DocsServicesModel, SectionContentsModel

@register(DocsServiceSectionsModel)
class ServiceSectionsTranslationOptions(TranslationOptions):
    """
    Translation options for service sections.
    """
    fields = ('name',)  # Fields that need translation

@register(DocsServicesModel)
class DocsServicesTranslationOptions(TranslationOptions):
    """
    Translation options for services.
    """
    fields = ('name',)  # Fields that need translation

@register(SectionContentsModel)
class SectionContentsTranslationOptions(TranslationOptions):
    """
    Translation options for section contents.
    """
    fields = ('name', 'desc', 'content')  # Fields that need translation
