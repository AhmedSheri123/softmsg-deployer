from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils.translation import activate, get_language
from django.conf import settings
from .models import DocsServicesModel, DocsServiceSectionsModel, SectionContentsModel

class MultiLangContentSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        """إرجاع كل عنصر مع اللغات المختلفة كـ tuples (object, language)"""
        items = []
        for obj in SectionContentsModel.objects.filter(is_enabled=True, is_default_selected=False):
            for lang_code, _ in settings.LANGUAGES:
                desc_attr = f'desc_{lang_code}'
                if getattr(obj, desc_attr, None):
                    items.append((obj, lang_code))
        return items

    def location(self, item):
        
        """إرجاع الرابط بناءً على اللغة"""
        obj, lang_code = item
        return f"/{lang_code}/resources/{obj.section.service.pk}?content_id={obj.pk}"

    def lastmod(self, item):
        """تحديد آخر تعديل للعنصر"""
        obj, _ = item
        return obj.creation_date