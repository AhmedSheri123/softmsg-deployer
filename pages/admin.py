from django.contrib import admin
from .models import ContactModel, SubscribeToUsModel

# Register your models here.
admin.site.register(ContactModel)
admin.site.register(SubscribeToUsModel)