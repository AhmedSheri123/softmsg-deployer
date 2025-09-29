from django.shortcuts import render, get_object_or_404, redirect
from .models import Plan, Subscription
from projects.models import AvailableProject
from deployments.models import Deployment, DeploymentContainer, DeploymentContainerEnvVar
from deployments.views import run_docker
from django.contrib.auth.decorators import login_required
from billing.models import ServicePaymentOrderModel
from django.contrib import messages
from django.db import transaction
import logging
from django.utils.text import slugify
from django.utils.translation import gettext as _

# Create your views here.
@login_required
def plans_list(request, project_id):
    project = AvailableProject.objects.get(id=project_id)
    plans = Plan.objects.filter(project=project)

    return render(request, 'dashboard/plans/ServicePlans.html', {'plans':plans, "project":project, "type":"1"})




logger = logging.getLogger(__name__)

@login_required
def ApplySubscription(request, order_id):
    order = get_object_or_404(ServicePaymentOrderModel, id=order_id)
    plan = order.plan
    duration = order.duration
    project = order.project
    main_domain = ".softmsg.com"

    try:
        with transaction.atomic():
            # تحديث حالة الطلب
            order.progress = '3'  # Deploying
            order.save()
            logger.info(f"Order {order.id} set to Deploying")

            # إنشاء Deployment
            deployment = Deployment.objects.create(
                user=request.user,
                project=project,
                progress=3,  # Deploying
                status=1,   # Stopped كبداية
            )
            logger.info(f"Deployment {deployment.id} created for project {project.name}")

            # إنشاء Subscription مرتبط بالـ Deployment
            Subscription.objects.create(
                deployment=deployment,
                plan=plan,
                duration=duration,
            )
            logger.info(f"Subscription created for deployment {deployment.id}")

            # إنشاء DeploymentContainers من ProjectContainers
            compose = deployment.docker_compose()
            services = compose.get("services", {})

            for name, config in services.items():
                container_name = f"{name}-{deployment.id}"
                dc = DeploymentContainer.objects.create(
                    deployment=deployment,
                    status=1,  # Pending
                    container_name=container_name,
                    pc_name=name,
                    domain=f"{container_name}{main_domain}"
                )


                logger.info(f"DeploymentContainer {dc.container_name} created with domain {dc.domain}")

            # تحديث env vars الافتراضية لكل container
            for container in deployment.containers.all():
                container.update_default_env_vars()
            logger.info(f"Default env vars updated for deployment {deployment.id}")

            deployment.create_xfs_volume(plan.storage)
            # تشغيل الـ Docker containers
            success = run_docker(deployment)
            if success:
                deployment.project.installs += 1
                deployment.project.save()
                install_time_minutes = deployment.project.install_time_minutes
                messages.success(request, _(f"The service has been successfully purchased. Please wait {install_time_minutes} minutes for the installation to complete."))
                logger.info(f"Docker containers for deployment {deployment.id} started successfully")
            else:
                deployment.progress = 5  # Failed
                deployment.save()
                messages.error(request, _("Failed to start the app"))
                logger.error(f"app for deployment {deployment.id} failed to start")

    except Exception as e:
        logger.exception(f"Error applying subscription for order {order_id}: {e}")
        messages.error(request, _("An error occurred while activating the service. Please try again later."))

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

    messages.success(request, _("The plan has been successfully renewed."))
    return redirect('my_deployments')
    

def UpgradePlan(request, deployment_id):
    deployment = get_object_or_404(Deployment, id=deployment_id)
    project = deployment.project
    plans = Plan.objects.filter(project=project)
    return render(request, 'dashboard/plans/ServicePlans.html', {'plans':plans, "project":project, "type":'3', "deployment":deployment})