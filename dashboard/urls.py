"""
URL configuration for dashboard.
"""

from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('job/<int:job_id>/', views.job_detail, name='job_detail'),
    path('job/<int:job_id>/stats/', views.job_stats_api, name='job_stats_api'),
    path('job/<int:job_id>/logs/', views.job_logs, name='job_logs'),
    path('job/<int:job_id>/cancel/', views.cancel_job, name='cancel_job'),
    path('job/<int:job_id>/delete/', views.delete_job, name='delete_job'),
    path('job/<int:job_id>/restart/', views.restart_job, name='restart_job'),
    path('job/<int:job_id>/generate-embeddings/', views.generate_job_embeddings, name='generate_job_embeddings'),
    path('job/<int:job_id>/analyze-content/', views.analyze_job_content, name='analyze_job_content'),
    path('crawl/new/', views.new_crawl, name='new_crawl'),
    path('client/<int:client_id>/', views.client_detail, name='client_detail'),
    path('client/<int:client_id>/pages/', views.client_pages, name='client_pages'),
    path('client/<int:client_id>/taxonomy/', views.client_taxonomy, name='client_taxonomy'),
    path('page/<int:page_id>/', views.page_detail, name='page_detail'),
    path('page/<int:page_id>/raw-html/', views.page_raw_html, name='page_raw_html'),
    path('page/<int:page_id>/screenshot/', views.page_screenshot, name='page_screenshot'),
    path('page/<int:page_id>/capture-screenshot/', views.capture_page_screenshot, name='capture_page_screenshot'),
    path('page/<int:page_id>/generate-embeddings/', views.generate_page_embeddings, name='generate_page_embeddings'),
    path('page/<int:page_id>/json/', views.page_json, name='page_json'),
    path('management/commands/', views.management_reference, name='management_reference'),
]
