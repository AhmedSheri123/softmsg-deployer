from modeltranslation.translator import register, TranslationOptions
from .models import DocsServiceSectionsModel, DocsServicesModel, SectionContentsModel

@register(DocsServiceSectionsModel)
class ServiceSectionsTranslationOptions(TranslationOptions):
    fields = ('name',)  # الحقول التي تحتاج إلى ترجمة

@register(DocsServicesModel)
class DocsTranslationOptions(TranslationOptions):
    fields = ('name',)  # الحقول التي تحتاج إلى ترجمة


@register(SectionContentsModel)
class ContentsTranslationOptions(TranslationOptions):
    fields = ('name', 'desc', 'content')  # الحقول التي تحتاج إلى ترجمة
