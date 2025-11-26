"""
Core models for the docanalyzer project.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField
import json


class Client(models.Model):
    """
    Represents a client company that is receiving documentation analysis services.
    """
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)
    contact_email = models.EmailField()
    webhook_url = models.URLField(blank=True, null=True, help_text="URL to receive crawl progress notifications")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class CrawlJob(models.Model):
    """
    Represents a crawl job for a specific documentation site.
    Orchestrates the entire crawl process from start to finish.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='crawl_jobs')
    target_url = models.URLField(help_text="The starting URL for the crawl")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Configuration stored as JSON
    config = models.JSONField(
        default=dict,
        help_text="Crawl configuration: depth_limit, allowed_domains, url_patterns, etc."
    )

    max_depth = models.IntegerField(default=10, help_text="The maximum depth to crawl")
    max_pages = models.IntegerField(default=50000, help_text="The maximum number of pages to crawl")
    rate_limit = models.FloatField(default=1.0, help_text="The rate limit in requests per second")
    include_patterns = ArrayField(models.CharField(max_length=200) , default=list, blank=True, help_text="List of patterns to include in the crawl")
    exclude_patterns = ArrayField(models.CharField(max_length=200) , default=list, blank=True, help_text="List of patterns to exclude from the crawl")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Enhanced Statistics stored as JSON
    stats = models.JSONField(
        default=dict,
        help_text="Crawl statistics: pages_crawled, errors, urls_discovered, etc."
    )
    pages_crawled = models.IntegerField(default=0, help_text="The number of pages crawled")
    pages_failed = models.IntegerField(default=0, help_text="The number of pages that failed to crawl")
    unique_content_pages = models.IntegerField(default=0, help_text="The number of unique content pages crawled")
    duplicate_pages = models.IntegerField(default=0, help_text="The number of duplicate pages crawled")

    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    # Analysis flags
    is_analyzed = models.BooleanField(default=False, help_text="Whether the crawl has been analyzed")
    analysis_started_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Error tracking
    error_message = models.TextField(blank=True, null=True)

    # Celery task ID for tracking
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['client', 'status']),
        ]

    def __str__(self):
        return f"{self.client.name} - {self.target_url} ({self.status})"

    def get_depth_limit(self):
        """Get the configured depth limit or return default."""
        return self.config.get('depth_limit', 5)

    def get_allowed_domains(self):
        """Get the list of allowed domains."""
        return self.config.get('allowed_domains', [])

    def update_stats(self, **kwargs):
        """Update crawl statistics."""
        if not self.stats:
            self.stats = {}
        self.stats.update(kwargs)
        self.save(update_fields=['stats'])

    def increment_stat(self, key, amount=1):
        """Increment a statistic counter."""
        if not self.stats:
            self.stats = {}
        self.stats[key] = self.stats.get(key, 0) + amount
        self.save(update_fields=['stats'])

    def mark_started(self):
        """Mark the job as started."""
        self.status = 'running'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])

    def mark_completed(self):
        """Mark the job as completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])

    def mark_failed(self, error_message):
        """Mark the job as failed with an error message."""
        self.status = 'failed'
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'error_message', 'completed_at'])

    def get_duration(self):
        """Get the duration of the crawl in seconds."""
        if not self.started_at:
            return None
        end_time = self.completed_at or timezone.now()
        return (end_time - self.started_at).total_seconds()

    def get_pages_per_second(self):
        """Calculate the average pages crawled per second."""
        duration = self.get_duration()
        if not duration or duration == 0:
            return 0
        pages_crawled = self.stats.get('pages_crawled', 0)
        return pages_crawled / duration

    @property
    def progress_percentage(self):
        """Calculate progress percentage based on discovered vs crawled URLs."""
        discovered = self.stats.get('urls_discovered', 0)
        crawled = self.stats.get('pages_crawled', 0)
        if discovered == 0:
            return 0
        return min(100, int((crawled / discovered) * 100))

