from allauth.account.signals import user_signed_up
from django.dispatch import receiver
from .models import UserProfile  # استبدل بالمسار الصحيح

@receiver(user_signed_up)
def create_user_profile(request, user, **kwargs):
    profile, created = UserProfile.objects.get_or_create(user=user)
    # تعبئة بيانات إضافية من Google
    sociallogin = kwargs.get('sociallogin')
    if sociallogin:
        extra_data = sociallogin.account.extra_data
        print(extra_data)
        profile.phone_number = extra_data.get('phone_number', '')
        profile.company_name = extra_data.get('company', '')
        profile.save()