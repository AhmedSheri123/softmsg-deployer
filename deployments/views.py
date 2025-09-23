from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required
from .utils import run_docker, delete_docker, restart_docker, get_container_usage, start_docker, stop_docker, rebuild_docker, hard_restart, get_storage_usage
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
import docker, json
from .models import DeploymentContainerEnvVar, Deployment
from projects.models import EnvVarsTitle


@login_required
def rebuild_project(request, deployment_id):
    # إنشاء Deployment في قاعدة البيانات
    deployment = Deployment.objects.get(
        id=deployment_id,
    )

    # استدعاء السكربت لإنشاء Docker container
    success = rebuild_docker(deployment)
    if not success:
        messages.error(request, "Failed to deploy the project.")
    else:messages.success(request, "Project deployed successfully!")
    return redirect('my_deployments')



@login_required
def my_deployments(request):
    deployments = Deployment.objects.filter(user=request.user)
    return render(request, "dashboard/deployments/my_deployments.html", {"deployments": deployments})

@login_required
def deployment_detail(request, deployment_id):
    deployment = get_object_or_404(Deployment, id=deployment_id, user=request.user)
    plan_features = deployment.plan.features.all() if hasattr(deployment.plan, 'features') else []



    # تحديد الألوان
    def color_for(percent):
        if percent <= 50:
            return "bg-success"
        if percent <= 80:
            return "bg-warning text-dark"
        return "bg-danger"

    resources = [
        {
            "name": "RAM",
            "used": 0,
            "limit": 0,
            "unit": "MB",
            "percent": 0,
            "color": color_for(0),
            "icon": '<i class="fa-solid fa-memory"></i>'
        },
        {
            "name": "CPU",
            "used": 0,
            "limit": 0,
            "unit": "%",
            "percent": 0,
            "color": color_for(0),
            "icon": '<i class="fa-solid fa-microchip"></i>'
        },
        {
            "name": "Storage",
            "used": 0,
            "limit": 0,
            "unit": "MB",
            "percent": 0,
            "color": color_for(0),
            "icon": '<i class="fa-solid fa-hard-drive"></i>'
        },
    ]


    context = {
        "deployment": deployment,
        "plans_data": plan_features,
        "resources": resources
    }
    return render(request, "dashboard/deployments/deployment_detail.html", context)



@login_required
def deployment_usage_api(request, deployment_id):
    deployment = get_object_or_404(Deployment, id=deployment_id, user=request.user)
    plan = getattr(deployment, "plan", None)

    total_mem_used = 0
    total_mem_limit = 0
    total_cpu_percent = 0
    total_cpu_limit_percent = 0
    total_storage_used = 0

    containers = deployment.containers.all()
    if not containers.exists():
        return JsonResponse({"error": "No containers found"}, status=400)
    total_storage_used = get_storage_usage(deployment).get("used_storage", 0)
    for dc in containers:
        usage = get_container_usage(dc.container_name, deployment=deployment)
        if "error" in usage:
            continue

        total_mem_used += usage.get("used_ram", 0)
        total_mem_limit += usage.get("memory_limit", 0)
        

        # -------- CPU --------
        cpu_limit_cores = float(getattr(plan, "cpu", 1))  # تحويل Decimal إلى float
        cpu_limit_percent = cpu_limit_cores * 100
        total_cpu_percent += (usage.get("cpu_percent", 0) / 100) * cpu_limit_percent
        total_cpu_limit_percent += cpu_limit_percent

    # تحويل Bytes إلى MB
    mem_used_mb = round(total_mem_used / (1024 * 1024), 2)
    mem_limit_mb = round(total_mem_limit / (1024 * 1024), 2)
    storage_used_mb = round(total_storage_used / (1024 * 1024), 2)

    cpu_percent_final = round((total_cpu_percent / total_cpu_limit_percent) * 100, 1) if total_cpu_limit_percent else 0

    data = {
        "RAM": {"used": mem_used_mb, "limit": mem_limit_mb, "unit": "MB"},
        "CPU": {"used": cpu_percent_final, "limit": 100, "unit": "%"},
        "Storage": {"used": storage_used_mb, "limit": getattr(plan, "storage", 0), "unit": "MB"}
    }

    return JsonResponse(data)



def delete_deployment(request, deployment_id):
    deployment = Deployment.objects.get(id=deployment_id)
    if deployment:
        delete_docker(deployment)
    deployment.delete()
    return redirect('my_deployments')



@csrf_exempt
def restart_deployment(request, deployment_id):
    deployment = get_object_or_404(Deployment, id=deployment_id, user=request.user)
    try:
        restart_docker(deployment)
        return JsonResponse({"success": True, "message": "Device restarted"})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})

@csrf_exempt
def hard_restart_deployment(request, deployment_id):
    deployment = get_object_or_404(Deployment, id=deployment_id, user=request.user)
    try:
        hard_restart(deployment)
        return JsonResponse({"success": True, "message": "Device restarted"})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})

@csrf_exempt
def stopstart_deployment(request, deployment_id):
    deployment = get_object_or_404(Deployment, id=deployment_id, user=request.user)
    try:
        if deployment.status == 2:
            stop_docker(deployment)
        else:
            start_docker(deployment)
        return JsonResponse({"success": True, "message": f"Device {deployment.get_status_display()}"})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})

def deployment_logs(request, deployment_id):
    client = docker.from_env()
    deployment = get_object_or_404(Deployment, id=deployment_id, user=request.user)
    logs_data = []

    containers = deployment.containers.all()
    for dc in containers:
        try:
            container = client.containers.get(dc.container_name)
            logs_data.append({
                "container_name": dc.container_name,
                "logs": container.logs(tail=100).decode(errors="ignore")
            })
        except Exception as e:
            logs_data.append({
                "container_name": dc.container_name,
                "error": str(e)
            })

    return JsonResponse(logs_data, safe=False)



def env_settings(request, deployment_id):
    deployment = get_object_or_404(Deployment, id=deployment_id, user=request.user)
    vars_titles = EnvVarsTitle.objects.filter()
    # جلب جميع env vars المرتبطة بالـ Deployment
    env_vars = DeploymentContainerEnvVar.objects.filter(
        container__deployment=deployment
    ).select_related('var', 'container')

    context = {
        'deployment': deployment,
        'env_vars': env_vars,
        'vars_titles': vars_titles,
    }
    return render(request, 'dashboard/deployments/env_var/env_settings.html', context)


def update_all_env_vars(request, deployment_id):
    if request.method == 'POST':
        deployment = get_object_or_404(Deployment, id=deployment_id, user=request.user)
        try:
            data = json.loads(request.body)

            # جلب جميع الـ env vars التابعة للـ deployment مرة واحدة
            env_vars = DeploymentContainerEnvVar.objects.filter(
                container__deployment=deployment
            )

            env_dict = {str(ev.id): ev for ev in env_vars}

            for env_id, value in data.items():
                env_var = env_dict.get(str(env_id))
                if env_var:
                    # التعامل مع نوع البيانات
                    if env_var.var.data_type == "boolean":
                        env_var.value = bool(value)
                    elif env_var.var.data_type == "int":
                        try:
                            env_var.value = int(value)
                        except ValueError:
                            env_var.value = 0  # قيمة افتراضية عند خطأ
                    else:
                        env_var.value = str(value)

                    env_var.save()

            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def change_project_domain(request, deployment_id):
    """
    View لتغيير الدومين لمشروع (Deployment).
    يفترض أن المشروع لديه container من نوع frontend أو backfront.
    """
    deployment = get_object_or_404(Deployment, id=deployment_id, user=request.user)

    # إيجاد الكونتينر المسؤول عن الدومين (frontend أو backfront)
    container = deployment.containers.filter(project_container__have_main_domain=True).first()
    if not container:
        messages.error(request, "No container found for this deployment.")
        return redirect('deployment_detail', deployment_id)

    if request.method == "POST":
        new_domain = request.POST.get("new_domain", "").strip()
        if not new_domain:
            messages.error(request, "Domain cannot be empty.")
            return redirect('deployment_detail', deployment_id)

        # هنا يمكن إضافة أي تحقق إضافي للدومين (format / DNS / regex)
        container.domain = new_domain
        container.save()
        hard_restart(deployment)
        messages.success(request, f"Project domain updated to {new_domain}.")
        return redirect('deployment_detail', deployment_id)



@login_required
def reset_project_domain(request, deployment_id):
    """
    View لتغيير الدومين لمشروع (Deployment).
    يفترض أن المشروع لديه container من نوع frontend أو backfront.
    """
    deployment = get_object_or_404(Deployment, id=deployment_id, user=request.user)

    # إيجاد الكونتينر المسؤول عن الدومين (frontend أو backfront)
    container = deployment.containers.filter(project_container__have_main_domain=True).first()
    if not container:
        messages.error(request, "No container found for this deployment.")
        return redirect('deployment_detail', deployment_id)
    main_domain = ".softmsg.com"
    new_domain = f"{container.container_name}{main_domain}"
    if not new_domain:
        messages.error(request, "Domain cannot be empty.")
        return redirect('deployment_detail', deployment_id)

    # هنا يمكن إضافة أي تحقق إضافي للدومين (format / DNS / regex)
    container.domain = new_domain
    container.save()
    hard_restart(deployment)
    
    messages.success(request, f"Project domain updated to {new_domain}.")
    return redirect('deployment_detail', deployment_id)
