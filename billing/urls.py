from django.urls import path
from . import views

urlpatterns = [
    path('create-order/<int:project_id>', views.create_order, name='create_order'),
    path('ServicePayment/<str:orderID>', views.ServicePayment, name='ServicePayment'),
    path('checkPaymentProcess/<str:orderID>', views.checkPaymentProcess, name='checkPaymentProcess'),
    path('PaypalCheckPaymentProcess/<str:secret>', views.PaypalCheckPaymentProcess, name='PaypalCheckPaymentProcess'),
    path('UpgradeOrRenewServiceSubscription/<str:orderID>', views.UpgradeOrRenewServiceSubscription, name='UpgradeOrRenewServiceSubscription'),
    path('MyOrders', views.MyOrders, name='MyOrders'),
    path('DeleteOrder/<str:orderID>', views.DeleteOrder, name='DeleteOrder'),
    path('CancellingOrder/<str:orderID>', views.CancellingOrder, name='CancellingOrder'),
]