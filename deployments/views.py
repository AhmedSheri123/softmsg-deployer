from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required
from .utils import run_docker, delete_docker_compose, restart_docker, get_container_usage, start_docker, stop_docker, rebuild_docker, hard_restart, get_storage_usage
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, FileResponse, Http404
import docker, json
from .models import DeploymentContainerEnvVar, Deployment, DeploymentBackup
from projects.models import EnvVarsTitle
from django.utils.translation import gettext as _
import logging, os
from django.utils import timezone

logger = logging.getLogger(__name__)

@login_required
def rebuild_project(request, deployment_id):
    # إنشاء Deployment في قاعدة البيانات
    deployment = Deployment.objects.get(
        id=deployment_id,
    )
    deployment.uuid_cache = {}
    deployment.save()

    compose_yaml = deployment.render_docker_resolved_compose_template()
    deployment.compose_template = compose_yaml
    deployment.save()

    # استدعاء السكربت لإنشاء Docker container
    success = rebuild_docker(deployment)
    if not success:
        messages.error(request, _("Failed to deploy the project."))
    else:messages.success(request, _("Project deployed successfully!"))
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
        delete_docker_compose(deployment)
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

    compose_yaml = deployment.render_docker_resolved_compose_template()
    deployment.compose_template = compose_yaml
    deployment.save()

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
    container = deployment.containers.filter(service_name=deployment.project.which_service_has_main_domain).first()
    if not container:
        messages.error(request, _("No container found for this deployment."))
        return redirect('deployment_detail', deployment_id)

    if request.method == "POST":
        new_domain = request.POST.get("new_domain", "").strip()
        if not new_domain:
            messages.error(request, _("Domain cannot be empty."))
            return redirect('deployment_detail', deployment_id)

        # هنا يمكن إضافة أي تحقق إضافي للدومين (format / DNS / regex)
        container.domain = new_domain
        container.save()
        hard_restart(deployment)
        messages.success(request, _(f"Project domain updated to {new_domain}."))
        return redirect('deployment_detail', deployment_id)



@login_required
def reset_project_domain(request, deployment_id):
    """
    View لتغيير الدومين لمشروع (Deployment).
    يفترض أن المشروع لديه container من نوع frontend أو backfront.
    """
    deployment = get_object_or_404(Deployment, id=deployment_id, user=request.user)

    # إيجاد الكونتينر المسؤول عن الدومين (frontend أو backfront)
    container = deployment.containers.filter(service_name=deployment.project.which_service_has_main_domain).first()
    if not container:
        messages.error(request, _("No container found for this deployment."))
        return redirect('deployment_detail', deployment_id)
    main_domain = ".softmsg.com"
    new_domain = f"{container.container_name}{main_domain}"
    if not new_domain:
        messages.error(request, _("Domain cannot be empty."))
        return redirect('deployment_detail', deployment_id)

    # هنا يمكن إضافة أي تحقق إضافي للدومين (format / DNS / regex)
    container.domain = new_domain
    container.save()
    hard_restart(deployment)
    
    messages.success(request, _(f"Project domain updated to {new_domain}."))
    return redirect('deployment_detail', deployment_id)




# -------------------------------
# قائمة النسخ الاحتياطية
# -------------------------------
def deployment_backups(request, deployment_id):
    """
    عرض جميع النسخ الاحتياطية الخاصة بنشر معين
    """
    deployment = get_object_or_404(Deployment, id=deployment_id)
    backups = deployment.backups.all()
    return render(request, "dashboard/deployments/backup/backup_list.html", {
        "deployment": deployment,
        "backups": backups
    })


# -------------------------------
# إنشاء نسخة احتياطية جديدة
# -------------------------------
def create_backup(request, deployment_id):
    """
    إنشاء نسخة احتياطية للملفات، قاعدة البيانات أو النسخة الكاملة حسب اختيار المستخدم
    """
    deployment = get_object_or_404(Deployment, id=deployment_id)

    if request.method == "POST":
        backup_type = request.POST.get("backup_type", "full")

        # تحقق من DB config إذا كان النسخ يتضمن قاعدة البيانات
        if backup_type in ["db", "full"]:
            db_config = getattr(deployment.project, "db_config", None)
            if not db_config or not db_config.is_valid():
                msg = _("Cannot create database backup: no valid DB config found for this project.")
                messages.error(request, msg)
                logger.error(msg)
                # إذا كان db-only، نوقف العملية مباشرة
                if backup_type == "db":
                    return redirect("deployment_backups", deployment_id=deployment.id)
                # إذا كان full، نستمر ولكن فقط الملفات
                backup_type = "files"
                logger.warning(f"DB config missing: creating files-only backup for deployment {deployment.id}")

        backup = DeploymentBackup.objects.create(
            deployment=deployment,
            backup_type=backup_type
        )

        try:
            backup_file = backup.create_backup()
            summary_msg = backup.backup_summary or _(f"Backup ({backup_type}) created successfully.")
            messages.success(request, summary_msg)
            logger.info(f"Backup created successfully: {backup_file}")
        except Exception as e:
            messages.error(request, _(f"Failed to create backup: {e}"))
            logger.error(f"Failed to create backup for deployment {deployment.id}: {e}", exc_info=True)

    return redirect("deployment_backups", deployment_id=deployment.id)


# -------------------------------
# استعادة نسخة احتياطية
# -------------------------------
def restore_backup(request, backup_id):
    """
    استعادة نسخة احتياطية محددة
    """
    backup = get_object_or_404(DeploymentBackup, id=backup_id)

    if request.method == "POST":
        try:
            backup.restore_backup()
            messages.success(request, _("Backup restored successfully."))
            logger.info(f"Backup restored successfully: {backup.file_path}")
        except Exception as e:
            messages.error(request, _(f"Failed to restore backup: {e}"))
            logger.error(f"Failed to restore backup {backup.id}: {e}", exc_info=True)

    return redirect("deployment_backups", deployment_id=backup.deployment.id)


def delete_backup(request, backup_id):
    backup = get_object_or_404(DeploymentBackup, id=backup_id)

    if request.method == "POST":
        deployment_id = backup.deployment.id
        try:
            # احذف الملف من النظام إذا موجود
            if backup.file_path and os.path.exists(backup.file_path):
                os.remove(backup.file_path)
                logger.info(f"Backup file deleted: {backup.file_path}")

            backup.delete()
            messages.success(request, _("Backup deleted successfully."))
            logger.info(f"Backup record deleted: {backup_id}")
        except Exception as e:
            messages.error(request, _(f"Failed to delete backup: {e}"))
            logger.error(f"Failed to delete backup {backup_id}: {e}", exc_info=True)

        return redirect("deployment_backups", deployment_id=deployment_id)

    return redirect("deployment_backups", deployment_id=backup.deployment.id)


@login_required
def download_backup(request, backup_id):
    backup = get_object_or_404(DeploymentBackup, id=backup_id)

    if not backup.file_path or not os.path.exists(backup.file_path):
        raise Http404("Backup file not found.")

    filename = os.path.basename(backup.file_path)
    response = FileResponse(open(backup.file_path, "rb"), as_attachment=True, filename=filename)
    return response


@login_required
def upload_backup(request, deployment_id):
    deployment = get_object_or_404(Deployment, id=deployment_id)

    if request.method == "POST":
        backup_file = request.FILES.get("backup_file")
        backup_type = request.POST.get("backup_type", "full")

        if not backup_file:
            messages.error(request, _("No file selected."))
            return redirect("deployment_backups", deployment_id=deployment.id)

        filename = f"{deployment.id}_{backup_type}_{timezone.now().strftime('%Y%m%d%H%M%S')}_{backup_file.name}"
        save_path = os.path.join("/var/lib/containers/backups", filename)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        with open(save_path, "wb+") as destination:
            for chunk in backup_file.chunks():
                destination.write(chunk)

        DeploymentBackup.objects.create(
            deployment=deployment,
            backup_type=backup_type,
            file_path=save_path,
            status="completed",
            size_mb=int(os.path.getsize(save_path)/(1024*1024))
        )

        messages.success(request, _("Backup uploaded successfully."))
        logger.info(f"Backup uploaded: {save_path}")

    return redirect("deployment_backups", deployment_id=deployment.id)
