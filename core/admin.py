"""
Admin configuration for core models.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Client, CrawlJob


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_email', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'contact_email']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']


@admin.register(CrawlJob)
class CrawlJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'target_url_short', 'status_badge', 'pages_crawled', 'created_at', 'duration']
    list_filter = ['status', 'created_at', 'client']
    search_fields = ['target_url', 'client__name']
    readonly_fields = ['created_at', 'started_at', 'completed_at', 'celery_task_id', 'stats_display', 'duration']

    fieldsets = (
        ('Basic Information', {
            'fields': ('client', 'target_url', 'status', 'error_message')
        }),
        ('Configuration', {
            'fields': ('config',),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('stats_display',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'started_at', 'completed_at', 'duration')
        }),
        ('Technical', {
            'fields': ('celery_task_id',),
            'classes': ('collapse',)
        }),
    )

    def target_url_short(self, obj):
        """Display a shortened version of the target URL."""
        if len(obj.target_url) > 50:
            return obj.target_url[:47] + '...'
        return obj.target_url
    target_url_short.short_description = 'Target URL'

    def status_badge(self, obj):
        """Display status as a colored badge."""
        colors = {
            'pending': 'gray',
            'running': 'blue',
            'paused': 'orange',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'black',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def pages_crawled(self, obj):
        """Display the number of pages crawled."""
        return obj.stats.get('pages_crawled', 0)
    pages_crawled.short_description = 'Pages Crawled'

    def duration(self, obj):
        """Display the crawl duration in a human-readable format."""
        duration_seconds = obj.get_duration()
        if not duration_seconds:
            return '-'

        hours = int(duration_seconds // 3600)
        minutes = int((duration_seconds % 3600) // 60)
        seconds = int(duration_seconds % 60)

        if hours > 0:
            return f'{hours}h {minutes}m {seconds}s'
        elif minutes > 0:
            return f'{minutes}m {seconds}s'
        else:
            return f'{seconds}s'
    duration.short_description = 'Duration'

    def stats_display(self, obj):
        """Display formatted statistics."""
        if not obj.stats:
            return 'No statistics yet'

        import json
        return format_html('<pre>{}</pre>', json.dumps(obj.stats, indent=2))
    stats_display.short_description = 'Statistics'
