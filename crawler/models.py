"""
Crawler models for storing crawled page data.
"""

from django.db import models
from core.models import CrawlJob
import hashlib

# Import configuration model


class CrawledPage(models.Model):
    """Enhanced with documentation-specific fields"""
    
    # Document type classification
    DOC_TYPE_CHOICES = [
        ('api_reference', 'API Reference'),
        ('tutorial', 'Tutorial'),
        ('guide', 'Guide'),
        ('quickstart', 'Quick Start'),
        ('concept', 'Conceptual'),
        ('example', 'Example/Demo'),
        ('changelog', 'Changelog'),
        ('faq', 'FAQ'),
        ('troubleshooting', 'Troubleshooting'),
        ('configuration', 'Configuration'),
        ('migration', 'Migration Guide'),
        ('best_practices', 'Best Practices'),
        ('landing', 'Landing Page'),
        ('navigation', 'Navigation Page'),
        ('unknown', 'Unknown'),
    ]
    
    # Basic fields (what you have)
    client = models.ForeignKey('core.Client', on_delete=models.CASCADE, related_name='pages')
    job = models.ForeignKey(CrawlJob, on_delete=models.CASCADE, related_name='pages')
    url = models.URLField(max_length=2000, db_index=True)
    depth = models.IntegerField()
    status_code = models.IntegerField()
    title = models.TextField(blank=True)
    meta_description = models.TextField(blank=True)
    content_hash = models.CharField(max_length=64, db_index=True)
    
    # Enhanced content storage
    main_content = models.TextField(help_text="Cleaned text content")
    raw_html = models.TextField(blank=True, null=True, help_text="Original HTML for reprocessing")
    screenshot_path = models.CharField(max_length=500, blank=True, null=True, help_text="Path to page screenshot")
    
    # Documentation classification
    doc_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES, default='unknown')
    doc_category = models.CharField(max_length=100, blank=True)  # User-defined categories
    
    # Version and freshness
    version_info = models.CharField(max_length=50, blank=True, help_text="v2.3, latest, etc.")
    last_modified = models.DateTimeField(null=True, blank=True)
    
    # ========================================
    # E-E-A-T (Experience, Expertise, Authoritativeness, Trust)
    # ========================================
    author = models.CharField(max_length=200, blank=True, help_text="Article author")
    author_bio = models.TextField(blank=True, help_text="Author credentials/bio if available")
    published_date = models.CharField(max_length=100, blank=True, help_text="Original publication date")
    last_updated_text = models.CharField(max_length=100, blank=True, help_text="Last updated date as text")
    reviewed_by = models.CharField(max_length=200, blank=True, help_text="Technical reviewer")
    
    # References and citations
    external_references = models.JSONField(default=list, help_text="Citations to authoritative sources")
    reference_count = models.IntegerField(default=0)
    has_references = models.BooleanField(default=False)
    
    # Navigation context
    breadcrumb = models.JSONField(default=list, help_text='["Home", "API", "Auth"]')
    sidebar_position = models.IntegerField(null=True, blank=True)
    navigation_title = models.CharField(max_length=200, blank=True)
    
    # Structured content
    headers = models.JSONField(default=dict)
    internal_links = models.JSONField(default=list)  # Full link details, not just count
    external_links = models.JSONField(default=list)
    code_blocks = models.JSONField(default=list)
    tables = models.JSONField(default=list)
    images = models.JSONField(default=list)
    
    # Content sections
    sections = models.JSONField(default=list, help_text="Semantic sections with headings")
    table_of_contents = models.JSONField(default=list)
    
    # Embeddings (OpenAI text-embedding-3-small)
    section_embeddings = models.JSONField(
        default=list,
        help_text="Per-section embeddings (model: text-embedding-3-small)",
    )
    page_embedding = models.JSONField(
        default=list,
        help_text="Full-page embedding (model: text-embedding-3-small)",
    )
    learning_objective_embeddings = models.JSONField(
        default=list,
        help_text="[{objective, bloom_level, difficulty, embedding}] - embeddings for each learning objective"
    )
    
    # ========================================
    # AI-Enhanced Content Analysis
    # ========================================
    ai_topics = models.JSONField(
        default=list,
        help_text="[{name, relevance, category, parent_topic, child_topics, related_topics}] - hierarchical topics"
    )
    ai_learning_objectives = models.JSONField(
        default=list,
        help_text="[{objective, bloom_level, bloom_verb, difficulty, estimated_time_minutes, measurable}] - structured LOs"
    )
    ai_prerequisite_chain = models.JSONField(
        default=list,
        help_text="[{concept, type, importance, description}] - linked prerequisites"
    )
    ai_summary = models.TextField(
        blank=True,
        default="",
        help_text="AI-generated 1-2 sentence summary for clustering"
    )
    ai_audience_level = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="AI-classified audience level: beginner, intermediate, advanced"
    )
    ai_key_concepts = models.JSONField(
        default=list,
        help_text="[{term, definition, is_new}] - key concepts introduced or used"
    )
    ai_doc_type = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text="AI-classified doc type using Diátaxis framework"
    )
    ai_quality_indicators = models.JSONField(
        default=dict,
        help_text="{completeness_score, needs_code_examples, needs_visuals, suggested_improvements}"
    )
    ai_related_topics = models.JSONField(
        default=list,
        help_text="List of related topic strings for cross-linking"
    )
    ai_analysis_metadata = models.JSONField(
        default=dict,
        help_text="{model, timestamp, processing_time_seconds, content_length}"
    )
    
    # Special content detection
    api_endpoints = models.JSONField(default=list)
    parameters = models.JSONField(default=list)
    warnings = models.JSONField(default=list)  # Warning/danger callouts
    tips = models.JSONField(default=list)  # Tip/info callouts
    questions = models.JSONField(default=list)  # Questions found in content
    
    # ========================================
    # Self-Contained Context (RAG Optimization)
    # ========================================
    prerequisites = models.JSONField(default=list, help_text="Prerequisites and requirements")
    learning_objectives = models.JSONField(default=list, help_text="What user will learn")
    next_steps = models.JSONField(default=list, help_text="Next steps after this page")
    
    has_prerequisites = models.BooleanField(default=False)
    has_learning_objectives = models.BooleanField(default=False)
    has_next_steps = models.BooleanField(default=False)
    
    # Q&A pairs for AI training
    qa_pairs = models.JSONField(default=list, help_text="Question-answer pairs extracted")
    qa_count = models.IntegerField(default=0)
    
    # SEO and discovery
    og_tags = models.JSONField(default=dict)  # Open Graph tags
    schema_markup = models.JSONField(default=dict)  # JSON-LD
    canonical_url = models.URLField(max_length=2000, blank=True)
    meta_keywords = models.TextField(blank=True)
    
    # ========================================
    # Technical SEO
    # ========================================
    hreflang_tags = models.JSONField(default=dict, help_text="Multi-language hreflang tags")
    structured_data_types = models.JSONField(default=list, help_text="Types of schema.org markup present")
    has_breadcrumb_schema = models.BooleanField(default=False)
    has_article_schema = models.BooleanField(default=False)
    has_howto_schema = models.BooleanField(default=False)
    has_faq_schema = models.BooleanField(default=False)
    
    # Navigation context
    navigation_depth = models.IntegerField(default=0, help_text="Clicks from homepage")
    is_orphan_page = models.BooleanField(default=False, help_text="No internal links pointing to it")
    incoming_internal_links_count = models.IntegerField(default=0, help_text="Number of internal links to this page")
    
    # Quality metrics
    word_count = models.IntegerField(default=0)
    readability_score = models.FloatField(null=True, blank=True)  # Flesch-Kincaid
    code_to_text_ratio = models.FloatField(null=True, blank=True)
    estimated_reading_time = models.IntegerField(default=0)  # minutes
    
    # ========================================
    # Content Quality Signals
    # ========================================
    has_tldr = models.BooleanField(default=False, help_text="Has TL;DR or summary section")
    paragraph_count = models.IntegerField(default=0)
    list_count = models.IntegerField(default=0, help_text="Number of ul/ol lists")
    average_paragraph_length = models.IntegerField(default=0, help_text="Average words per paragraph")
    
    # Temporal language patterns
    has_step_by_step = models.BooleanField(default=False, help_text="Contains step-by-step instructions")
    imperative_sentence_count = models.IntegerField(default=0, help_text="Command sentences (Click, Run, etc.)")
    
    # Feature detection
    has_table_of_contents = models.BooleanField(default=False)
    has_search = models.BooleanField(default=False)
    has_examples = models.BooleanField(default=False)
    has_interactive_elements = models.BooleanField(default=False)
    has_videos = models.BooleanField(default=False)
    has_copy_buttons = models.BooleanField(default=False)  # For code blocks
    
    # ========================================
    # Interactive Features
    # ========================================
    has_code_playground = models.BooleanField(default=False, help_text="Has embedded code playground")
    has_api_explorer = models.BooleanField(default=False, help_text="Has interactive API explorer")
    has_feedback_mechanism = models.BooleanField(default=False, help_text="Has user feedback buttons")
    has_version_switcher = models.BooleanField(default=False, help_text="Has version switcher UI")
    has_community_comments = models.BooleanField(default=False, help_text="Has comment system")
    
    # Performance
    response_time = models.FloatField(default=0.0)  # seconds
    page_size = models.IntegerField(default=0)  # bytes
    render_method = models.CharField(max_length=20, choices=[
        ('static', 'Static HTML'),
        ('javascript', 'JavaScript Rendered')
    ], default='static')
    javascript_render_time = models.FloatField(null=True, blank=True)
    
    # ========================================
    # Performance & Resources
    # ========================================
    script_count = models.IntegerField(default=0, help_text="Number of script tags")
    stylesheet_count = models.IntegerField(default=0, help_text="Number of stylesheet links")
    third_party_scripts = models.JSONField(default=list, help_text="Third-party script domains")
    
    # ========================================
    # Version & Compatibility
    # ========================================
    version_compatibility = models.JSONField(default=dict, help_text="Version requirements and compatibility")
    product_versions = models.JSONField(default=list, help_text="Product versions mentioned")
    language_versions = models.JSONField(default=list, help_text="Programming language version requirements")
    deprecation_warnings = models.JSONField(default=list, help_text="Deprecation notices")
    has_deprecation_warning = models.BooleanField(default=False)
    
    # ========================================
    # Accessibility & UX Quality
    # ========================================
    aria_labels_count = models.IntegerField(default=0, help_text="Number of ARIA labels")
    alt_text_quality_score = models.FloatField(default=0.0, help_text="Percentage of images with meaningful alt text")
    heading_structure_valid = models.BooleanField(default=True, help_text="Valid h1-h6 hierarchy")
    has_skip_links = models.BooleanField(default=False, help_text="Has skip navigation links")
    mobile_viewport_meta = models.BooleanField(default=False, help_text="Has mobile viewport meta tag")
    
    # ========================================
    # Content Comprehensiveness
    # ========================================
    sections_count = models.IntegerField(default=0, help_text="Number of major sections")
    has_diagrams = models.BooleanField(default=False, help_text="Contains diagrams or architecture images")
    has_troubleshooting = models.BooleanField(default=False, help_text="Has troubleshooting section")
    example_to_explanation_ratio = models.FloatField(default=0.0, help_text="Code examples vs text ratio")
    content_type_diversity = models.IntegerField(default=0, help_text="Number of different content types (0-5)")
    
    # Deduplication
    is_duplicate = models.BooleanField(default=False)
    duplicate_of = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Timestamps
    crawled_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['client', 'url']  # Changed from ['job', 'url'] to prevent duplicates across crawls
        ordering = ['depth', 'url']
        indexes = [
            models.Index(fields=['client', 'crawled_at']),  # New index for client-level queries
            models.Index(fields=['job', 'doc_type']),
            models.Index(fields=['job', 'depth']),
            models.Index(fields=['content_hash']),
            models.Index(fields=['job', 'is_duplicate']),
            # AI-era SEO indexes
            models.Index(fields=['job', 'has_references']),
            models.Index(fields=['job', 'qa_count']),
            models.Index(fields=['job', 'has_prerequisites']),
            models.Index(fields=['job', 'content_type_diversity']),
            models.Index(fields=['job', 'is_orphan_page']),
            models.Index(fields=['job', 'has_deprecation_warning']),
            models.Index(fields=['job', 'sections_count']),
        ]
    
    def calculate_content_hash(self):
        """Generate hash of main content for deduplication"""
        return hashlib.sha256(self.main_content.encode()).hexdigest()
    
    def __str__(self):
        return f"{self.title or self.url} (Depth: {self.depth})"

class PageRelationship(models.Model):
    """Track relationships between pages for link graph analysis"""
    RELATIONSHIP_TYPES = [
        ('parent', 'Parent Page'),
        ('child', 'Child Page'),
        ('sibling', 'Sibling Page'),
        ('related', 'Related Page'),
        ('next', 'Next Page'),
        ('previous', 'Previous Page'),
    ]
    
    from_page = models.ForeignKey(CrawledPage, on_delete=models.CASCADE, related_name='outgoing_relationships')
    to_page = models.ForeignKey(CrawledPage, on_delete=models.CASCADE, related_name='incoming_relationships')
    relationship_type = models.CharField(max_length=20, choices=RELATIONSHIP_TYPES)
    anchor_text = models.TextField(blank=True)
    context = models.TextField(blank=True, help_text="Surrounding text near the link")
    
    class Meta:
        unique_together = ['from_page', 'to_page', 'relationship_type']


class CrawlError(models.Model):
    """
    Records errors encountered during crawling.
    """
    ERROR_TYPE_CHOICES = [
        ('timeout', 'Timeout'),
        ('http_error', 'HTTP Error'),
        ('connection_error', 'Connection Error'),
        ('parse_error', 'Parse Error'),
        ('javascript_error', 'JavaScript Error'),
        ('other', 'Other'),
    ]

    job = models.ForeignKey(CrawlJob, on_delete=models.CASCADE, related_name='errors')
    url = models.URLField(max_length=2048)
    error_type = models.CharField(max_length=50, choices=ERROR_TYPE_CHOICES)
    error_message = models.TextField()
    status_code = models.IntegerField(null=True, blank=True)
    depth = models.IntegerField(default=0)
    retry_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['job', '-created_at']),
            models.Index(fields=['job', 'error_type']),
        ]

    def __str__(self):
        return f"{self.error_type}: {self.url}"
