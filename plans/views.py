from django.shortcuts import render, get_object_or_404, redirect
from .models import Plan, Subscription
from projects.models import AvailableProject
from deployments.models import Deployment, DeploymentContainer, DeploymentContainerEnvVar
from deployments.views import run_docker
from django.contrib.auth.decorators import login_required
from billing.models import ServicePaymentOrderModel
from django.contrib import messages
# Create your views here.
@login_required
def plans_list(request, project_id):
    project = AvailableProject.objects.get(id=project_id)
    plans = Plan.objects.filter(project=project)

    return render(request, 'dashboard/plans/ServicePlans.html', {'plans':plans, "project":project, "type":"1"})


@login_required
def ApplySubscription(request, order_id):
    order = get_object_or_404(ServicePaymentOrderModel, id=order_id)
    plan = order.plan
    duration = order.duration
    project = order.project

    # تحديث حالة الطلب
    order.progress = '3'
    order.save()

    # إنشاء Deployment
    deployment = Deployment.objects.create(
        user=request.user,
        project=project,
        progress=3,  # Deploying
        status=1,   # Stopped كبداية
    )
    

    # إنشاء Subscription مرتبط بالـ Deployment
    Subscription.objects.create(
        deployment=deployment,
        plan=plan,
        duration=duration,
    )
    main_domain = ".softmsg.com"
    # إنشاء DeploymentContainers من ProjectContainers
    for pc in project.containers.all():
        dc = DeploymentContainer.objects.create(
            deployment=deployment,
            project_container=pc,
            env_vars=pc.env_vars,
            port=pc.default_port,
            status=1,  # Pending
        )

        container_name = f"{request.user.username}-{dc.id}".lower()
        dc.container_name = container_name

        # تحديد الدومين الخاص بالباك اند
        if pc.type == "backend":
            container_domain = f"api.{container_name}{main_domain}"
        elif pc.type == "frontend":
            container_domain = f'{container_name}{main_domain}'
        elif pc.type == "backfront":
            container_domain = f'{container_name}{main_domain}'
        else:
            container_domain = None  # redis أو غيره ما يحتاج دومين

        dc.domain = container_domain
        dc.save()

    # تشغيل الـ Docker containers
    success = run_docker(deployment)
    if success:
        deployment.project.installs +=1
        deployment.project.save()
        
        containers = deployment.containers.all()
        for container in containers:
            container.update_default_env_vars()
        messages.success(request, 'تم شراء الخدمة بنجاح')
    return redirect('my_deployments')

def ApplyUpgradePlan(request, order_id):
    order = get_object_or_404(ServicePaymentOrderModel, id=order_id)
    deployment = order.deployment
    plan = order.plan
    duration = order.duration
    print(duration)
    old_sub = Subscription.objects.get(deployment=deployment)
    old_sub.delete()
    new_sub = Subscription.objects.create(
        deployment=deployment,
        plan=plan,
        duration=duration,
    )

    # تحديث حالة الطلب
    order.progress = '3'
    order.save()

    messages.success(request, 'تم تجديد الخطة بنجاح')
    return redirect('my_deployments')
    

def UpgradePlan(request, deployment_id):
    deployment = get_object_or_404(Deployment, id=deployment_id)
    project = deployment.project
    plans = Plan.objects.filter(project=project)
    return render(request, 'dashboard/plans/ServicePlans.html', {'plans':plans, "project":project, "type":'3', "deployment":deployment})