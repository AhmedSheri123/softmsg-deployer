from django import template
from django.template.defaultfilters import stringfilter
from accounts.models import NotificationsModel
from django.contrib.auth.models import User

register = template.Library()

@register.simple_tag
@stringfilter
def get_notifications(user_id):
    notifications = NotificationsModel.objects.filter(receiver__id__in=[user_id]).order_by('-id')
    return notifications

@register.simple_tag
@stringfilter
def get_user_profile_img(user_id):
    user = User.objects.get(id=user_id)
    try:
        userprofile = user.userprofile
        img = userprofile.img_base64
    except: img = ''
    return img

@register.simple_tag
@stringfilter
def has_not_readed_noti(user_id):
    user = User.objects.get(id=user_id)
    notis = NotificationsModel.objects.filter(receiver__in=[user]).exclude(reaed_users__in=[user])
    return notis.exists()