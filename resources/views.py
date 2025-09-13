from django.shortcuts import render
from .models import DocsServicesModel, DocsServiceSectionsModel, SectionContentsModel
# Create your views here.

def view_service_resources(request, service_id):
    content_id = request.GET.get('content_id')

    service = DocsServicesModel.objects.get(id=service_id)
    sections = DocsServiceSectionsModel.objects.filter(service=service).order_by('ordering')
    contents = SectionContentsModel.objects.filter(section__service=service)
    if not content_id:
        content_id =  contents.filter(is_default_selected=True).first().id if contents.filter(is_default_selected=True).exists() else contents.first().id
    content = SectionContentsModel.objects.get(id=content_id)
    return render(request, 'resources/viwer.html', {'content':content, 'sections':sections, 'service':service})