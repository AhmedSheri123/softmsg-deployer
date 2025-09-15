from django.shortcuts import render, get_object_or_404, redirect
from .models import Plan, Subscription
from projects.models import AvailableProject
from deployments.models import Deployment
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
    order = ServicePaymentOrderModel.objects.get(id=order_id)
    plan = order.plan
    duration = order.duration
    project = order.project
    order.progress = '3'
    order.save()
    # إنشاء Deployment
    deployment = Deployment.objects.create(
        user=request.user,
        project=project,
    )

    deployment.domain = f"{request.user.username}-{deployment.id}.softmsg.com"
    deployment.save()
    deployment.update_default_env_vars()
    # إنشاء Subscription مرتبط بالـ Deployment
    Subscription.objects.create(
        deployment=deployment,
        plan=plan,
        duration=duration,
    )
    # تشغيل الـ Docker container
    success = run_docker(deployment)


    return redirect('my_deployments')
