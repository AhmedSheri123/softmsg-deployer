# sitemaps.py
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import AvailableProject
from django.conf import settings

class StaticViewSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return ['project_list']  # أسماء مسارات ثابتة

    def location(self, item):
        return reverse(item)

class ProjectSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        items = []
        for obj in AvailableProject.objects.all():
            for lang_code, _ in settings.LANGUAGES:
                items.append((obj, lang_code))
        return items

    def location(self, item):
        obj, lang_code = item
        return f"/{lang_code}/projects/{obj.id}/details/"