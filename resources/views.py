from django.shortcuts import render, get_object_or_404
from .models import DocsServicesModel, DocsServiceSectionsModel, SectionContentsModel

def view_service_resources(request, project_id):
    # الحصول على content_id من GET
    content_id = request.GET.get('content_id')

    # جلب الخدمة المرتبطة بالمشروع
    service = get_object_or_404(DocsServicesModel, project__id=project_id)

    # جلب الأقسام المرتبطة بالخدمة
    sections = service.sections.all()  # استخدم related_name إذا عينته
    sections = sections.order_by('ordering')

    # جلب المحتويات المرتبطة بالخدمة
    contents = SectionContentsModel.objects.filter(section__service=service).order_by('ordering')

    # اختيار المحتوى الافتراضي إذا لم يتم تحديد content_id
    if not content_id:
        default_content = contents.filter(is_default_selected=True).first()
        if default_content:
            content = default_content
        else:
            content = contents.first()
    else:
        # التأكد من أن المحتوى موجود وينتمي للخدمة
        content = contents.filter(id=content_id).first()
        if not content:
            # fallback للمحتوى الأول إذا كان content_id غير صالح
            content = contents.first()

    return render(
        request,
        'resources/viwer.html',
        {
            'content': content,
            'sections': sections,
            'service': service
        }
    )
