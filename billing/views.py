from django.shortcuts import render, redirect, get_object_or_404, HttpResponseRedirect
from .models import ServicePaymentOrderModel
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from projects.models import AvailableProject
from plans.models import Plan
from plans.views import ApplySubscription, ApplyUpgradePlan
from django.urls import reverse
from django.conf import settings
from paypal.standard.forms import PayPalPaymentsForm
from .payment import addInvoice
from deployments.models import Deployment
# Create your views here.

def ServicePayment(request, orderID):
    order = ServicePaymentOrderModel.objects.get(orderID=orderID)
    plan = order.plan
    price = order.price

    if price <= 0:
        if order.order_type == '1':
            return ApplySubscription(request, order.id)
        elif order.order_type == '2':
            return ApplyUpgradePlan(request, order.id)
        elif order.order_type == '3':
            return ApplyUpgradePlan(request, order.id)

    user = request.user
    userprofile = user.userprofile
    index_url = request.build_absolute_uri('/')
    index_url = index_url.rsplit('/', 1)[0]              
    cancelUrl= index_url + reverse('CancellingOrder', kwargs={'orderID': orderID})
    PayPalCallBackUrl= index_url + reverse('PaypalCheckPaymentProcess', kwargs={'secret': order.order_secret})
    # PayPal Payment
    paypal_dict = {
        "business": settings.PAYPAL_RECIVVER_EMAIL,
        "amount": price,
        "item_name": order.project.name,
        "invoice": orderID,
        "currency_code": 'USD',
        "notify_url": request.build_absolute_uri(reverse('paypal-ipn')),
        "return": PayPalCallBackUrl,
        "cancel_return": cancelUrl,
        "custom": "premium_plan",  # Custom command to correlate to some function later (optional)
    }
    paypal_form = PayPalPaymentsForm(initial=paypal_dict)

    if request.method == 'POST':

        
        clientName = user.first_name + ' ' + user.last_name
        total_price_amount = price
        email = user.email
        phone = userprofile.phone_number
        callBackUrl= index_url + reverse('checkPaymentProcess', kwargs={'orderID': orderID})

        p_res = addInvoice(orderID, total_price_amount, email, phone, clientName, order.project.name, order.project.description, callBackUrl, cancelUrl, 'USD')
        if p_res.get('success'):
            order.transactionNo = p_res.get('transactionNo')
            order.save()
            return HttpResponseRedirect(p_res.get('url'))

    return render(request, 'dashboard/services/payment/pay.html', {'plan':plan, 'price':price, 'paypal_form':paypal_form})


def UpgradeOrRenewServiceSubscription(request, orderID):
    order = ServicePaymentOrderModel.objects.get(orderID=orderID)
    user_service = UserServiceModel.objects.get(id=order.user_service.id)
    return

def checkPaymentProcess(request, orderID):
    order = ServicePaymentOrderModel.objects.get(orderID=orderID)
    r = getInvoice(order.transactionNo)
    if r.get('success'):
        if r.get('orderStatus') == 'Paid':
            return EnableServiceSubscription(request, order.id)
    return redirect('index')

def PaypalCheckPaymentProcess(request, secret):
    orders = ServicePaymentOrderModel.objects.filter(order_secret=secret)
    if orders.exists():
        order = orders.first()
        if order.order_type == '1':
            return ApplySubscription(request, order.id)
        elif order.order_type == '2' or order.order_type == '3':
            return ApplyUpgradePlan(request, order.id)
    return redirect('index')

@login_required
def create_order(request, project_id):
    if request.method == "POST":
        order_type = request.POST.get("type")
        plan_id = request.POST.get("plan_id")
        duration = request.POST.get("duration_type")  # monthly / yearly
        deployment_id = request.POST.get("deployment_id")

        project = get_object_or_404(AvailableProject, id=project_id)
        plan = get_object_or_404(Plan, id=plan_id)

        # السعر يعتمد على نوع الاشتراك
        if duration == "monthly":
            price = plan.monthly_price
        else:
            price = plan.yearly_price

        # إنشاء طلب دفع جديد
        order = ServicePaymentOrderModel.objects.create(
            user=request.user,
            plan=plan,
            duration=duration,
            price=price,
            project=project,
            progress='1',  # Pending
            creation_date=timezone.now(),
            order_type=order_type
        )
        #Upgrade Plan
        if order_type == '3' or order_type == '2':
            deployment = get_object_or_404(Deployment, id=deployment_id)
            order.deployment = deployment
        order.save()

    return redirect('ServicePayment', order.orderID)


def MyOrders(request):
    orders = ServicePaymentOrderModel.objects.filter(user=request.user).order_by('-id')
    return render(request, 'dashboard/orders/MyOrders.html', {'orders':orders})

def DeleteOrder(request, orderID):
    order = ServicePaymentOrderModel.objects.get(orderID=orderID)
    order.delete()
    return redirect('MyOrders')

def CancellingOrder(request, orderID):
    order = ServicePaymentOrderModel.objects.get(orderID=orderID)
    order.progress = '4'
    order.save()
    return redirect('ServicePlans', order.user_service.id)