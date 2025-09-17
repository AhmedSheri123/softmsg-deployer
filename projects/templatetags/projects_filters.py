from django import template

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
