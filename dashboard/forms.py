from django import forms
from .models import UserServiceModel
from .fields import CountrysChoices

class AddUserServiceModelForm(forms.ModelForm):

    class Meta:
        model = UserServiceModel
        fields = ['project_name', 'service']

        widgets = {
            'project_name': forms.TextInput(attrs={'class':'form-control', 'placeholder':'New Project Name'}),
            'service': forms.Select(attrs={'class':'form-select', 'placeholder':'Choose Service'}),
        }

PatientManagementLANGUAGES = [
    ('ar', 'العربية'),
    ('en', 'English'),
    ('de', 'Deutsch'),
    ('he', 'עִברִית'),
    ('ro', 'Românește'),
    
]

SchoolManagementLANGUAGES = [
    ('ar', 'العربية'),
    ('en', 'English'),
    ('de', 'Deutsch'),
    ('he', 'עִברִית'),
    ('ro', 'Românește'),
    
]


class PatientManagementHospital(forms.Form):
    first_name = forms.CharField(max_length=254, widget=forms.TextInput({'class':'form-control'}))
    last_name = forms.CharField(max_length=254, widget=forms.TextInput({'class':'form-control'}))
    username = forms.CharField(max_length=254, widget=forms.TextInput({'class':'form-control'}))
    password = forms.CharField(label='password', max_length=254, widget=forms.PasswordInput(attrs={'class':'form-control', 'placeholder':'Password'}))
    name = forms.CharField(max_length=254, widget=forms.TextInput({'class':'form-control'}))
    number = forms.CharField(max_length=254, widget=forms.TextInput({'class':'form-control'}))
    address = forms.CharField(max_length=254, widget=forms.TextInput({'class':'form-control'}))
    lang = forms.ChoiceField(choices=PatientManagementLANGUAGES, widget=forms.Select({'class':'form-select'}))

class SchoolManagementProfile(forms.Form):
    first_name = forms.CharField(max_length=254, widget=forms.TextInput({'class':'form-control'}))
    last_name = forms.CharField(max_length=254, widget=forms.TextInput({'class':'form-control'}))
    username = forms.CharField(max_length=254, widget=forms.TextInput({'class':'form-control'}))
    password = forms.CharField(label='password', max_length=254, widget=forms.PasswordInput(attrs={'class':'form-control', 'placeholder':'Password'}))
    name = forms.CharField(max_length=254, widget=forms.TextInput({'class':'form-control'}))
    number = forms.CharField(max_length=254, widget=forms.TextInput({'class':'form-control'}))
    address = forms.CharField(max_length=254, widget=forms.TextInput({'class':'form-control'}))
    academic_year = forms.IntegerField(widget=forms.NumberInput({'class':'form-control', "min":"0", "placeholder":"2025"}))
    lang = forms.ChoiceField(choices=SchoolManagementLANGUAGES, widget=forms.Select({'class':'form-select'}))
    country = forms.ChoiceField(choices=CountrysChoices, widget=forms.Select({'class':'form-select'}))

class HRManagementProfile(forms.Form):
    first_name = forms.CharField(max_length=254, widget=forms.TextInput({'class':'form-control'}))
    last_name = forms.CharField(max_length=254, widget=forms.TextInput({'class':'form-control'}))
    username = forms.CharField(max_length=254, widget=forms.TextInput({'class':'form-control'}))
    email = forms.EmailField(widget=forms.TextInput({'class':'form-control'}))
    password = forms.CharField(label='password', max_length=254, widget=forms.PasswordInput(attrs={'class':'form-control', 'placeholder':'Password'}))
    number = forms.CharField(max_length=254, widget=forms.TextInput({'class':'form-control'}))
