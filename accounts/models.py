from django.db import models
from django.contrib.auth.models import User
from .libs import when_published

# Create your models here.

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    company_name = models.CharField(max_length=254)
    phone_number = models.CharField(max_length=254)
    img_base64 = models.TextField(null=True)

    @property
    def get_full_name(self):
        return f'{self.user.first_name} {self.user.last_name}'
    
    def __str__(self):
        return f'{self.user.id} - {self.user.username} - {self.get_full_name}' 

class NotificationsModel(models.Model):
    sender = models.ForeignKey(User, related_name='noti_sender', on_delete=models.CASCADE)
    receiver = models.ManyToManyField(User, related_name='noti_receiver')
    reaed_users = models.ManyToManyField(User, related_name='reaed_users')
    msg = models.TextField()

    creation_date = models.DateTimeField(null=True, verbose_name="تاريخ الانشاء")

    def whenpublished(self):
        return when_published(self.creation_date)
    
