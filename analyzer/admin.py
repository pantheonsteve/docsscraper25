"""
Admin configuration for analyzer models.
"""

from django.contrib import admin
from .models import Analysis


@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    list_display = ['id', 'job', 'analysis_type', 'created_at', 'completed_at']
    list_filter = ['analysis_type', 'created_at']
    readonly_fields = ['created_at', 'completed_at']
