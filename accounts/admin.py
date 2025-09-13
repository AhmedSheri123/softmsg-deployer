from django.contrib import admin
from .models import NotificationsModel, UserProfile
# Register your models here.
admin.site.register(NotificationsModel)
admin.site.register(UserProfile)