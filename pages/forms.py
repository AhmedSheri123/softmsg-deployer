from django import forms
from .models import ContactModel, SubscribeToUsModel
from django.utils.translation import gettext_lazy as _


class ContactFormModel(forms.ModelForm):
    class Meta:
        model = ContactModel
        fields = ['full_name', 'email', 'phone_number', 'project_description', 'similar_websites']

        widgets = {
            'full_name': forms.TextInput(attrs={'class':'form-control', 'placeholder':_('write your name...')}),
            'email': forms.EmailInput(attrs={'class':'form-control', 'placeholder':_('name@example.com')}),
            'phone_number': forms.TextInput(attrs={'class':'form-control', 'placeholder':_('e.g., +1 234 567 890')}),
            # 'project_title': forms.TextInput(attrs={'class':'form-control', 'placeholder':_('Enter your project title here')}),
            'project_description': forms.Textarea(attrs={'class':'form-control', 'rows':'5', 'placeholder':_('How can our team help you?')}),
            'similar_websites': forms.Textarea(attrs={'class':'form-control', 'rows':'3', 'placeholder':_('https://example.com')}),
            # 'expected_budget': forms.TextInput(attrs={'class':'form-control', 'placeholder':_('Enter the estimated budget amount')}),
        }


class SubscribeToUsModelForm(forms.ModelForm):
    class Meta:
        model = SubscribeToUsModel
        fields = ['email']

        widgets = {
            'email': forms.EmailInput(attrs={'class':'form-control', 'placeholder':_('name@example.com')}),
        }