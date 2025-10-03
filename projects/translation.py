from modeltranslation.translator import register, TranslationOptions
from .models import Action, ActionParameter, EnvVarsTitle, EnvVar, AvailableProject

@register(AvailableProject)
class AvailableProjectTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'install_steps', 'about')

@register(Action)
class ActionTranslationOptions(TranslationOptions):
    fields = ('label',)

@register(ActionParameter)
class ActionParameterTranslationOptions(TranslationOptions):
    fields = ('label',)


@register(EnvVarsTitle)
class EnvVarsTitleTranslationOptions(TranslationOptions):
    fields = ('title',)

@register(EnvVar)
class EnvVarTranslationOptions(TranslationOptions):
    fields = ('label',)