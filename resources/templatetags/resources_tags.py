from django import template
from django.template.defaultfilters import stringfilter
from resources.models import SectionContentsModel, DocsServicesModel
from django.contrib.auth.models import User
from django.utils.translation import activate, get_language

register = template.Library()

@register.simple_tag
@stringfilter
def get_contents_by_section(section_id):
    contents = SectionContentsModel.objects.filter(section__id=section_id)
    for content in contents:
        lang = get_language()
        if not getattr(content, f'name_{lang}', None):
            contents = contents.exclude(id=content.id)
    return contents


@register.simple_tag
@stringfilter
def get_doc_services(section_id):
    doc_services = DocsServicesModel.objects.filter()
    for doc_service in doc_services:
        lang = get_language()
        if not getattr(doc_service, f'name_{lang}', None):
            doc_services = doc_services.exclude(id=doc_service.id)
    return doc_services