"""
Report models for generating client deliverables.
This is a placeholder for future report generation features.
"""

from django.db import models
from core.models import CrawlJob


class Report(models.Model):
    """
    Represents a generated report for a client.
    Future implementation will include PDF/HTML report generation.
    """
    REPORT_TYPE_CHOICES = [
        ('summary', 'Executive Summary'),
        ('detailed', 'Detailed Analysis Report'),
        ('comparison', 'Comparison Report'),
        ('custom', 'Custom Report'),
    ]

    job = models.ForeignKey(CrawlJob, on_delete=models.CASCADE, related_name='reports')
    report_type = models.CharField(max_length=50, choices=REPORT_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    content = models.JSONField(default=dict, help_text="Report content and sections")
    file_path = models.CharField(max_length=512, blank=True, help_text="Path to generated PDF/HTML")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} (Job #{self.job.id})"
