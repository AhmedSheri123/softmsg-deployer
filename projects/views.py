# actions/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from .models import ActionModel, ActionParameterModel
from deployments.models import Deployment
from projects.models import AvailableProject
import docker

def project_list(request):
    projects = AvailableProject.objects.all()

    return render(request, "dashboard/projects/project_list.html", {
        "projects": projects,
    })




def run_action(request, deployment_id, action_id):
    deployment = get_object_or_404(Deployment, id=deployment_id)
    action = get_object_or_404(ActionModel, id=action_id)

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
            container = client.containers.get(deployment.container_name)

            exec_log = container.exec_run(command)
            output = exec_log.output.decode("utf-8") if exec_log.output else ""
            
            return JsonResponse({
                "success": True,
                "message": f"{action.label} executed successfully!",
                "output": output
            })
        
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})
    
    return render(request, "dashboard/projects/actions/run_action_modal.html", {
        "deployment": deployment,
        "action": action,
    })
