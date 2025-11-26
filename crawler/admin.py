# crawler/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q
from .models import CrawlJob, CrawledPage, PageRelationship

@admin.register(CrawledPage)
class CrawledPageAdmin(admin.ModelAdmin):
    list_display = ['title_display', 'doc_type', 'depth', 'word_count', 
                    'readability_score', 'has_examples', 'response_time']
    
    list_filter = ['doc_type', 'depth', 'has_examples', 'has_table_of_contents',
                   'render_method', 'is_duplicate']
    
    search_fields = ['url', 'title', 'main_content']
    
    readonly_fields = ['content_hash', 'crawled_at', 'quality_indicators']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('job', 'url', 'depth', 'status_code', 'title', 'doc_type')
        }),
        ('Content', {
            'fields': ('main_content', 'meta_description', 'content_hash'),
            'classes': ('collapse',)
        }),
        ('Structured Data', {
            'fields': ('headers', 'internal_links', 'external_links', 
                      'code_blocks', 'sections', 'api_endpoints'),
            'classes': ('collapse',)
        }),
        ('Quality Metrics', {
            'fields': ('word_count', 'readability_score', 'estimated_reading_time',
                      'code_to_text_ratio', 'quality_indicators')
        }),
        ('Features', {
            'fields': ('has_table_of_contents', 'has_search', 'has_examples',
                      'has_videos', 'has_copy_buttons')
        }),
        ('Performance', {
            'fields': ('response_time', 'page_size', 'render_method', 
                      'javascript_render_time')
        }),
        ('Metadata', {
            'fields': ('crawled_at', 'version_info', 'last_modified', 'author'),
            'classes': ('collapse',)
        })
    )
    
    def title_display(self, obj):
        """Show truncated title with hover for full text"""
        return format_html(
            '<span title="{}">{}</span>',
            obj.title,
            obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
        )
    title_display.short_description = 'Title'
    
    def quality_indicators(self, obj):
        """Show quality indicators as badges"""
        indicators = []
        
        if obj.readability_score and obj.readability_score > 60:
            indicators.append('<span class="badge badge-success">Readable</span>')
        elif obj.readability_score and obj.readability_score < 30:
            indicators.append('<span class="badge badge-warning">Complex</span>')
        
        if obj.has_examples:
            indicators.append('<span class="badge badge-info">Has Examples</span>')
        
        if obj.word_count < 100:
            indicators.append('<span class="badge badge-warning">Stub</span>')
        
        if obj.code_blocks and len(obj.code_blocks.get('blocks', [])) > 3:
            indicators.append('<span class="badge badge-info">Code Rich</span>')
        
        return format_html(' '.join(indicators))
    quality_indicators.short_description = 'Quality Indicators'
    
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }