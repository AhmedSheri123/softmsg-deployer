"""
URL configuration for softmsg project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.views.generic.base import TemplateView
from pages import views
from django.contrib.sitemaps.views import sitemap
from resources.sitemaps import MultiLangContentSitemap
from projects.sitemaps import StaticViewSitemap, ProjectSitemap
sitemaps = {
    "contents": MultiLangContentSitemap,
    'projects': ProjectSitemap,
    'static': StaticViewSitemap,
}




urlpatterns = [
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
    path('PrivacyPolicy', views.PrivacyPolicy, name='PrivacyPolicy'),
    path('l-accounts/', include('allauth.urls')),  # روابط allauth
    
] + i18n_patterns(
    path('', include('pages.urls')),
    path('resources/', include('resources.urls')),
    path('accounts/', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('projects/', include('projects.urls')),
    path('deployments/', include('deployments.urls')),
    path('plans/', include('plans.urls')),
    path('billing/', include('billing.urls')),
    path('paypal/', include("paypal.standard.ipn.urls")),
    path('tinymce/', include("tinymce.urls")),
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    
)


urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)