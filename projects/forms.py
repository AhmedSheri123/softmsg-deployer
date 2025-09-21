from django import forms
from django_select2.forms import Select2MultipleWidget
from .models import ProjectContainer, Category, AvailableProject

def get_project_language_tech_list():
    r = ProjectContainer.LANGUAGE_CHOICES + ProjectContainer.TECHNOLOGY_CHOICES + ProjectContainer.CONTAINER_TYPES
    return r

class ProjectFilterForm(forms.Form):

    technologys = forms.MultipleChoiceField(
        choices=get_project_language_tech_list(),
        required=False,
        widget=Select2MultipleWidget(
            attrs={
                'class': 'form-select',  # ينسق مع Bootstrap
                'data-placeholder': 'اختر التقنيات...',
                'style': 'width: 100%;'
            }
        )
    )

    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        required=False,
        widget=Select2MultipleWidget(
            attrs={
                'class': 'form-select',
                'data-placeholder': 'اختر التصنيفات...',
                'style': 'width: 100%;'
            }
        )
    )