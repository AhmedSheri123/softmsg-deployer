from django.shortcuts import render, get_object_or_404, redirect
from .models import Plan, Subscription
from projects.models import AvailableProject
from deployments.models import Deployment, DeploymentContainer, DeploymentContainerEnvVar
from deployments.views import run_docker
from django.contrib.auth.decorators import login_required
from billing.models import ServicePaymentOrderModel
# Create your views here.
@login_required
def plans_list(request, project_id):
    project = AvailableProject.objects.get(id=project_id)
    plans = Plan.objects.filter(project=project)

    return render(request, 'dashboard/plans/ServicePlans.html', {'plans':plans, "project":project})


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

        container_name = f"{request.user.username}_{dc.id}".lower()
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
        containers = deployment.containers.all()
        for container in containers:
            container.update_default_env_vars()
    return redirect('my_deployments')
