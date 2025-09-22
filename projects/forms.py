from django import forms
from django_select2.forms import Select2MultipleWidget
from .models import ProjectContainer, Category, AvailableProject
from django.utils.translation import gettext_lazy as _ 

def get_project_language_tech_list():
    r = ProjectContainer.LANGUAGE_CHOICES + ProjectContainer.TECHNOLOGY_CHOICES + ProjectContainer.CONTAINER_TYPES
    return r

class ProjectFilterForm(forms.Form):
    technologys = forms.MultipleChoiceField(
        choices=get_project_language_tech_list(),
        required=False,
        label=_("Technologies"),
        widget=Select2MultipleWidget(
            attrs={
                'class': 'form-select',
                'data-placeholder': _("Select technologies..."),
                'style': 'width: 100%;'
            }
        )
    )

    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        required=False,
        label=_("Categories"),
        widget=Select2MultipleWidget(
            attrs={
                'class': 'form-select',
                'data-placeholder': _("Select categories..."),
                'style': 'width: 100%;'
            }
        )
    )