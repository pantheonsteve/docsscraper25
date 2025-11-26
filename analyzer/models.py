"""
Analyzer models for storing analysis results.
This is a placeholder for future LLM-based analysis features.
"""

from django.db import models
from core.models import CrawlJob


class Analysis(models.Model):
    """
    Represents an analysis run on crawled data.
    Future implementation will include LLM-based insights.
    """
    ANALYSIS_TYPE_CHOICES = [
        ('structure', 'Documentation Structure Analysis'),
        ('content_gaps', 'Content Gap Detection'),
        ('api_completeness', 'API Reference Completeness'),
        ('tutorial_quality', 'Tutorial Quality Assessment'),
        ('custom', 'Custom Analysis'),
    ]

    job = models.ForeignKey(CrawlJob, on_delete=models.CASCADE, related_name='analyses')
    analysis_type = models.CharField(max_length=50, choices=ANALYSIS_TYPE_CHOICES)
    results = models.JSONField(default=dict, help_text="Analysis results and insights")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Analyses'

    def __str__(self):
        return f"{self.get_analysis_type_display()} for Job #{self.job.id}"
