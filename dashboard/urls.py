from django.urls import path
from . import views

urlpatterns = [
    path('', views.Home, name='DashboardHome'),
    path('MyServices', views.MyServices, name='MyServices'),
    path('AddService', views.AddService, name='AddService'),

    path('UserServiceCreationProgress/<int:id>', views.UserServiceCreationProgress, name='UserServiceCreationProgress'),
    path('ResetPasswordService/<int:id>', views.ResetPasswordService, name='ResetPasswordService'),
    
    path('ServicePlans/<int:id>', views.ServicePlans, name='ServicePlans'),
    path('ViewService/<int:id>', views.ViewService, name='ViewService'),
    
    path('buliding_waiting_page/<int:user_service_id>', views.buliding_waiting_page, name='buliding_waiting_page'),
    path('check_is_deployed/<int:user_service_id>', views.check_is_deployed, name='check_is_deployed'),
]
