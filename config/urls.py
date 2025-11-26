"""
URL configuration for docanalyzer project.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls')),
    path('api/crawler/', include('crawler.urls')),
]

# Customize admin site
admin.site.site_header = 'DocAnalyzer Administration'
admin.site.site_title = 'DocAnalyzer Admin'
admin.site.index_title = 'Welcome to DocAnalyzer Administration'
