from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('Services/PatientManagement', views.PatientManagement, name='PatientManagement'),
    path('Services/SchoolManagement', views.SchoolManagement, name='SchoolManagement'),
    path('Services/HRManagement', views.HRManagement, name='HRManagement'),
    path('SubscribeToUs', views.SubscribeToUs, name='SubscribeToUs'),
    path('Contact', views.Contact, name='Contact'),
    path('change_language/', views.change_language, name='change_language'),

]
