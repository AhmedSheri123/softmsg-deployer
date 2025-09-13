from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ContactFormModel, SubscribeToUsModelForm
from django.utils.translation import gettext as _
from django.utils import translation

# Create your views here.

def index(request):
    form = ContactFormModel()
    return render(request, 'pages/index.html', {'form':form})

def PrivacyPolicy(request):
    return render(request, 'pages/PrivacyPolicy.html')

def PatientManagement(request):
    return render(request, 'pages/services/PatientManagement.html')

def SchoolManagement(request):
    return render(request, 'pages/services/SchoolManagement.html')

def HRManagement(request):
    return render(request, 'pages/services/HRManagement.html')

def SubscribeToUs(request):
    form = SubscribeToUsModelForm(data=request.GET)
    if form.is_valid():
        form.save()
        messages.success(request, _('Your has been subscribed successfully.'))
    return redirect('index')


def Contact(request):
    if request.method == 'POST':
        form = ContactFormModel(data=request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _('Your message has been sent successfully. You will be replied after reviewing the details.'))
            return redirect('index')
        
def change_language(request):
    if request.method == 'POST':
            user_language = translation.get_language()
            language = request.POST['language']
            translation.activate(language)  # تفعيل اللغة المختارة
            # request.session[translation.LANGUAGE_SESSION_KEY] = language  # تخزين اللغة في الجلسة
            referer = request.META.get('HTTP_REFERER', '/').replace(f'/{user_language}/', f'/{language}/')
            print(user_language, language, referer)
            return redirect(referer)
    else:
        return redirect('index')