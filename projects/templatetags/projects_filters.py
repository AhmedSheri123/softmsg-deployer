from django import template
from projects.models import AvailableProject
from deployments.models import Deployment
from collections import defaultdict

register = template.Library()

@register.filter
def clean_default(value:str, deployment):
    """
    مثال: إذا كانت القيمة None أو تحتوي على نص غير مرغوب فيه يتم تنظيفها
    يمكنك تعديل هذا حسب احتياجك
    """
    if not value:
        return ''
    value = value.format(deployment=deployment)
    # مثال آخر: إزالة {} أو علامات خاصة
    return str(value)

@register.simple_tag
def active_deployments(project):
    deployment = Deployment.objects.filter(project=project, status=2)
    return deployment

@register.simple_tag
def deployments(project):
    deployment = Deployment.objects.filter(project=project)
    return deployment

@register.simple_tag
def get_list_project_language_tech_tree(project):
    containers = project.containers.all()
    tree = []

    for c in containers:
        if c.language and c.technology and c.type:
            tree = [c.language, c.technology, c.get_type_display()]
    unique_list = list(dict.fromkeys(tree))
    return unique_list


@register.simple_tag
def get_project_language_tech_tree(project):


    containers = project.containers.all()
    tree = defaultdict(lambda: defaultdict(list))

    for c in containers:
        if c.language and c.type:
            tech = c.technology or "-"  # إذا كانت technology فارغة
            tree[c.language][tech].append(c.get_type_display())

    # ترتيب النص
    lines = []
    for lang, techs in tree.items():
        lines.append(lang)
        for tech, types in techs.items():
            lines.append(f" └─ {tech}")
            for i, t in enumerate(types):
                if i < len(types) - 1:
                    lines.append(f"     ├─ {t}")
                else:
                    lines.append(f"     └─ {t}")
    return "\n".join(lines)

@register.simple_tag
def get_deployment_compose_env(deployment_id, service_name, var_name):
    print(deployment_id, service_name, var_name)
    try:
        deployment = Deployment.objects.get(id=deployment_id)
    except Deployment.DoesNotExist:
        return 'N/A'

    compose = deployment.render_deployment_compose()
    services = compose.get("services", {})
    service = services.get(service_name)
    if not service:
        return 'N/A'

    env = service.get('environment', {})
    var_value = 'N/A'

    # إذا environment dict
    if isinstance(env, dict):
        var_value = env.get(var_name, 'N/A')
    # إذا environment قائمة من السلاسل
    elif isinstance(env, list):
        for item in env:
            if isinstance(item, str) and item.startswith(f"{var_name}="):
                var_value = item.split("=", 1)[1]
                break

    return var_value
