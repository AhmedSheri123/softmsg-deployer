from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.urls import reverse
from .forms import (AddUserServiceModelForm, PatientManagementHospital, SchoolManagementProfile, HRManagementProfile)
from .models import (ServicesModel, UserServiceModel)
from django.contrib import messages
from django.conf import settings
import json, requests
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import render
from decimal import Decimal
from .tools import data_base, deploy
from .projects_setting import hr_setting
import os
from billing.models import ServicePaymentOrderModel
from deployments.models import Deployment
# Create your views here.
PAYPAL_RECIVVER_EMAIL = settings.PAYPAL_RECIVVER_EMAIL



def Home(request):
    user = request.user
    user_services = Deployment.objects.filter(user=user)
    orders = ServicePaymentOrderModel.objects.filter(user=user)
    active_user_services = user_services.filter(status=2)
    copmlited_orders = orders.filter(progress='3')
    uncopmlited_orders = orders.exclude(progress='3')
    
    context = {
        'active_user_services': active_user_services.count(),
        'copmlited_orders': copmlited_orders.count(),
        'uncopmlited_orders': uncopmlited_orders.count(),
        'orders':orders
    }
    return render(request, 'dashboard/home.html', context)

def MyServices(request):
    user_services = UserServiceModel.objects.filter(user=request.user).order_by('-id')
    return render(request, 'dashboard/services/MyServices.html', {'user_services':user_services})




def ResetPasswordService(request, id):
    if request.method == 'POST':
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        if password == password2:
            data = {
                'password':password
            }
            res_data = {}
            user_services = UserServiceModel.objects.get(id=id)
            service_user_id = user_services.service_user_id
            selected_service = user_services.service.service


            if service_user_id:
                if selected_service == '1':
                    res = requests.post(f'{PatientManagementURL}/en/accounts/ResetPasswordAPI/{service_user_id}', data=data)
                elif selected_service == '2':
                    res = requests.post(f'{SchoolManagementURL}/en/ResetPasswordAPI/{service_user_id}', data=data)
                elif selected_service == '3':
                    response_data, exit_code = hr_docker.change_user_password(user_services.subdomain, service_user_id, password)
                    if exit_code == 0:
                        res_data['status'] = True
                    else:
                        res_data['status'] = False

                if not res_data:
                    if res.status_code == 200:
                        res_data = res.json()
                    else:messages.error(request, 'error on trying connect to server please call support')

                if res_data.get('status'):
                    messages.success(request, 'Password has been changed successfully')
                else:
                    messages.error(request, 'Password not changed got some errors, please call support')
            else:messages.error(request, 'error on changing password please call support')
        else:messages.error(request, 'new password field and repeat new password field not same')
    return redirect('ViewService', id)


def check_is_deployed(request, user_service_id):
    user_service = UserServiceModel.objects.get(id=user_service_id)
    # r = hr_docker.check_migrations(user_service.subdomain)
    url = f'http://77.37.122.10:{user_service.system_port}/'
    r = False
    try:
        res = requests.get(url, timeout=4)
        if res.status_code == 200 or res.status_code == 301 or res.status_code == 302:
            r = True
    except:
        pass
    return JsonResponse({'success':r}, safe=False)

def buliding_waiting_page(request, user_service_id):
    check_is_deployed_url = reverse('check_is_deployed', kwargs={'user_service_id':user_service_id})
    success_page = reverse('AddHRManagementSettings', kwargs={'id':user_service_id})
    return render(request, 'dashboard/bulding/buliding_waiting_page.html', {'check_is_deployed_url':check_is_deployed_url, 'success_page':success_page})

def DeploySystem(request, user_service):
    if user_service.system_progress == '3':
        return redirect('buliding_waiting_page', user_service.id)

    project_name = 'horilla'
    domain = 'softmsg.com'
    subdomain = user_service.subdomain if user_service.subdomain else user_service.get_unique_subdomain(user_service.project_name)
    port = user_service.system_port if user_service.system_port else user_service.get_avarible_port
    user_service.subdomain = subdomain
    user_service.system_port = port
    static_folder_name = 'staticfiles'

    #create database for project
    # creating_database = data_base.create_database(db_name=subdomain, user=DEFAULT_HR_DB_USER, password=DEFAULT_HR_DB_PASS, host='77.37.122.10', port='5434')
    print('adding service')
    hr_docker.add_hr_service(subdomain, port)
    print('runing container')
    hr_docker.compose_up(subdomain)
    # hr_docker.run_container(subdomain, port)
    print('success')
    
    if os.name == "posix":
        #create nginx for app
        deploying = deploy.create_nginx_config(static_folder_name, subdomain, port, domain)
        deploy.restart_services()
    # if creating_database:
    user_service.system_progress = '3'
    user_service.save()
    return redirect('buliding_waiting_page', user_service.id)
    # else:
    #     user_service.system_progress = '4'
    #     user_service.save()
    #     messages.error(request, 'حدث خطاء اثناء بناء النظام')
    #     return redirect('MyServices')
    
    
    

def UserServiceCreationProgress(request, id):
    user_service = UserServiceModel.objects.get(id=id)
    progress = user_service.progress
    if progress == '1': return redirect('AddService')
    elif progress == '2': return redirect('ServicePlans', id)
    elif progress == '3':
        if user_service.service.service == '1':
            return redirect('AddPatientManagementSettings', id)
        elif user_service.service.service == '2':
            return redirect('AddSchoolManagementSettings', id)
        elif user_service.service.service == '3':
            return DeployHRSystem(request, user_service)
    elif progress == '4':
        return redirect('ViewService', id)
    return redirect('MyServices')

def AddService(request):
    service_info_url = reverse('GetServiceInfo')
    form = AddUserServiceModelForm()
    if request.method == 'POST':
        form = AddUserServiceModelForm(data=request.POST)
        if form.is_valid():
            user_service = form.save(commit=False)
            user_service.user = request.user
            user_service.progress = '2'
            user_service.save()

            return redirect('UserServiceCreationProgress', user_service.id)
    return render(request, 'dashboard/services/AddService.html', {'form':form, 'service_info_url':service_info_url})


def ServicePlans(request, id):
    user_service = UserServiceModel.objects.get(id=id)

    return render(request, 'dashboard/services/ServicePlans.html', {'user_service':user_service})




def ViewService(request, id):
    
    return




