"""
URL configuration for crawler API endpoints.
"""

from django.urls import path
from . import views

app_name = 'crawler'

urlpatterns = [
    path('status/<int:job_id>/', views.crawl_status, name='crawl_status'),
    path('start/', views.start_crawl, name='start_crawl'),
]
