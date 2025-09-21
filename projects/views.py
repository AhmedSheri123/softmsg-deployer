# actions/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from .models import Action
from deployments.models import DeploymentContainer
from projects.models import AvailableProject, ProjectReview
import docker
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .forms import ProjectFilterForm
from django.urls import reverse
from django.db.models import Q



def project_list(request):
    projects = AvailableProject.objects.all()

    form = ProjectFilterForm(request.GET or None)

    if form.is_valid():
        technologys = form.cleaned_data.get("technologys")
        categories = form.cleaned_data.get('categories')

        if technologys:
            projects = projects.filter(Q(containers__technology__in=technologys)|Q(containers__language__in=technologys)|Q(containers__type__in=technologys)).distinct()
        if categories:
            projects = projects.filter(categories__in=categories).distinct()

    # فلترة حسب التصنيف (التقنية مثلاً)
    category = request.GET.get("category")
    if category:
        projects = projects.filter(containers__technology=category)

    # فلترة حسب اللغة
    language = request.GET.get("language")
    if language:
        projects = projects.filter(containers__language=language)

    # فلترة حسب مستوى الصعوبة
    difficulty = request.GET.get("difficulty")
    if difficulty:
        projects = projects.filter(difficulty_level=difficulty)

    # البحث بالاسم أو الوصف
    search = request.GET.get("search")
    if search:
        projects = projects.filter(name__icontains=search) | projects.filter(description__icontains=search)

    # الترتيب
    order = request.GET.get("order")
    if order == "install":
        projects = projects.order_by("-installs")
    elif order == "rating":
        projects = sorted(projects, key=lambda p: p.average_rating_float, reverse=True)
    elif order == "latest":
        projects = projects.order_by("-id")  # أو -created_at إذا عندك

    # اختر الـ base template حسب إذا كان المستخدم في لوحة التحكم
    if request.user.is_authenticated:  # أو أي شرط تحدده للوحة التحكم
        base_template = "dashboard_base.html"
    else:
        base_template = "base.html"

    return render(request, "dashboard/projects/project_list.html", {
        "projects": projects,
        "form":form,
        "base_template":base_template,
    })



def project_details_ajax(request, project_id):
    project = get_object_or_404(AvailableProject, id=project_id)
    return render(request, "dashboard/projects/project_details_modal.html", {"project": project})

def project_details(request, project_id):
    project = get_object_or_404(AvailableProject, id=project_id)

    # اختر الـ base template حسب إذا كان المستخدم في لوحة التحكم
    if request.user.is_authenticated:  # أو أي شرط تحدده للوحة التحكم
        base_template = "dashboard_base.html"
    else:
        base_template = "base.html"
        
    return render(request, "dashboard/projects/project_details.html", {"project": project, "base_template":base_template})



def run_action(request, container_id, action_id):
    container = get_object_or_404(DeploymentContainer, id=container_id)
    action = get_object_or_404(Action, id=action_id)

    if request.method == "POST":
        params = {}

        for param in action.parameters.all():
            value = request.POST.get(param.name, param.default)

            # تحويل حسب نوع البيانات
            if param.data_type == "int":
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    return JsonResponse({"success": False, "message": f"Invalid integer for {param.label}"})
            elif param.data_type == "boolean":
                value = str(value).lower() in ["true", "1", "yes", "on"]

            params[param.name] = value

        # تجهيز الأمر مع الباراميترات
        try:
            command = action.command.format(**params)
        except KeyError as e:
            return JsonResponse({"success": False, "message": f"Missing parameter: {e}"})

        # تشغيل الأمر داخل الحاوية
        try:
            client = docker.from_env()
            container = client.containers.get(container.container_name)

            exec_log = container.exec_run(command)
            output = exec_log.output.decode("utf-8") if exec_log.output else ""
            print(command, output)
            return JsonResponse({
                "success": True,
                "message": f"{action.label} executed successfully!",
                "output": output
            })
        
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})
    
    return render(request, "dashboard/projects/actions/run_action_modal.html", {
        "container": container,
        "action": action,
    })

@csrf_exempt
def add_review(request, project_id):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "طلب غير صالح"})

    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "error": "يجب تسجيل الدخول"})

    project = get_object_or_404(AvailableProject, id=project_id)
    rating = int(request.POST.get("rating", 0))
    comment = request.POST.get("comment", "").strip()

    if rating < 1 or rating > 5:
        return JsonResponse({"success": False, "error": "التقييم يجب أن يكون بين 1 و 5"})

    if not comment:
        return JsonResponse({"success": False, "error": "التعليق فارغ"})

    # إنشاء أو تحديث مراجعة المستخدم
    review, created = ProjectReview.objects.get_or_create(
        project=project,
        user=request.user,
        defaults={"rating": rating, "comment": comment}
    )
    if not created:
        review.rating = rating
        review.comment = comment
        review.save()

    # فقط إرسال التعليق الجديد (لا تحذف السابق)
    review_data = {
        "user": review.user.username,
        "rating": review.rating,
        "comment": review.comment
    }

    return JsonResponse({"success": True, "review": review_data})


def project_autocomplete(request):
    q = request.GET.get('q', '')
    projects = AvailableProject.objects.filter(Q(name__icontains=q)|Q(description__icontains=q))[:10]

    # اجعل safe=False لإرسال قائمة JSON مباشرة
    data = [{"id": p.id, "name": p.name, "image":p.image.url, "url":reverse('project_details', kwargs={"project_id":p.id})} for p in projects]
    return JsonResponse(data, safe=False)