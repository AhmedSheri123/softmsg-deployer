from django.shortcuts import redirect, get_object_or_404, render
from deployments.models import Deployment
from django.contrib.auth.decorators import login_required
from .utils import run_docker, delete_docker, restart_docker, get_container_usage, start_docker, stop_docker, rebuild_docker
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
import docker, json
from .models import DeploymentEnvVar
client = docker.from_env()

@login_required
def rebuild_project(request, deployment_id):
    # إنشاء Deployment في قاعدة البيانات
    deployment = Deployment.objects.get(
        id=deployment_id,
    )

    # استدعاء السكربت لإنشاء Docker container
    success = rebuild_docker(deployment, deployment.plan)
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
            "icon": '<i class="bi bi-memory"></i>'
        },
        {
            "name": "CPU",
            "used": 0,
            "limit": 0,
            "unit": "%",
            "percent": 0,
            "color": color_for(0),
            "icon": '<i class="bi bi-cpu"></i>'
        },
        {
            "name": "Storage",
            "used": 0,
            "limit": 0,
            "unit": "MB",
            "percent": 0,
            "color": color_for(0),
            "icon": '<i class="bi bi-device-hdd"></i>'
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

    resources_now = get_container_usage(deployment.container_name)
    if "error" in resources_now:
        return JsonResponse({"error": resources_now["error"]}, status=400)

    # نفس الحسابات اللي عملناها في detail
    mem_usage_bytes = resources_now.get("memory_usage", 0) or 0
    mem_limit_bytes = resources_now.get("memory_limit") or 1
    cpu_percent_now = resources_now.get("cpu_percent", 0) or 0
    storage_bytes = resources_now.get("storage_usage", 0) or 0

    mem_used_mb = round(mem_usage_bytes / (1024 * 1024), 2)
    mem_limit_mb = round(mem_limit_bytes / (1024 * 1024), 2)
    storage_used_mb = round(storage_bytes / (1024 * 1024), 2)

    # هنا بس نرجع JSON جاهز
    data = {
        "RAM": {"used": mem_used_mb, "limit": mem_limit_mb, "unit": "MB"},
        "CPU": {"used": round(cpu_percent_now, 1), "limit": 100, "unit": "%"},
        "Storage": {"used": storage_used_mb, "limit": deployment.plan.storage*1000, "unit": "MB"}  # مثال: حد 1GB
    }
    return JsonResponse(data)


def delete_deployment(request, deployment_id):
    deployment = Deployment.objects.get(id=deployment_id)
    if deployment.container_name:
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
def stopstart_deployment(request, deployment_id):
    deployment = get_object_or_404(Deployment, id=deployment_id, user=request.user)
    try:
        container = client.containers.get(deployment.container_name)
        if deployment.status == 2:
            stop_docker(deployment)
        else:
            start_docker(deployment)
        return JsonResponse({"success": True, "message": f"Device {deployment.get_status_display()}"})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})

def deployment_logs(request, deployment_id):
    deployment = get_object_or_404(Deployment, id=deployment_id, user=request.user)
    try:
        container = client.containers.get(deployment.container_name)
        logs = container.logs(tail=100).decode()
        return HttpResponse(logs, content_type="text/plain")
    except Exception as e:
        return HttpResponse(str(e), content_type="text/plain")



def env_settings(request, deployment_id):
    deployment = get_object_or_404(Deployment, id=deployment_id, user=request.user)
    return render(request, 'dashboard/deployments/env_var/env_settings.html', {'deployment':deployment})

def update_all_env_vars(request, deployment_id):
    if request.method == 'POST':
        try:
            deployment = Deployment.objects.get(id=deployment_id)
            data = json.loads(request.body)
            
            for env_id, value in data.items():
                env_var = DeploymentEnvVar.objects.get(id=int(env_id), deployment=deployment)
                env_var.value = value
                env_var.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})