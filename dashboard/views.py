"""
Dashboard views for monitoring crawl jobs.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Count, Avg, Sum, Q
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils import timezone
from core.models import Client, CrawlJob
from crawler.models import CrawledPage, CrawlError
from crawler.tasks import start_crawl_task, generate_page_embeddings_task
from crawler.content_analyzer import ContentAnalyzer
from celery import current_app
import logging
from ddtrace import tracer
from django.utils.text import slugify

FORMAT = ('%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] '
          '[dd.service=%(dd.service)s dd.env=%(dd.env)s dd.version=%(dd.version)s dd.trace_id=%(dd.trace_id)s dd.span_id=%(dd.span_id)s] '
          '- %(message)s')
logging.basicConfig(format=FORMAT)
logger = logging.getLogger('dashboard')
logger.level = logging.INFO

@tracer.wrap()
def index(request):
    """
    Main dashboard view showing overview of all crawl jobs.
    """
    logger.info("Dashboard index view called")
    # Get statistics
    total_jobs = CrawlJob.objects.count()
    active_jobs = CrawlJob.objects.filter(status='running').count()
    completed_jobs = CrawlJob.objects.filter(status='completed').count()
    failed_jobs = CrawlJob.objects.filter(status='failed').count()
    total_pages = CrawledPage.objects.count()

    # Get recent jobs
    recent_jobs = CrawlJob.objects.select_related('client').order_by('-created_at')[:10]

    # Get clients with job counts
    clients = Client.objects.annotate(
        job_count=Count('crawl_jobs'),
        total_pages=Count('crawl_jobs__pages')
    ).filter(is_active=True)

    context = {
        'total_jobs': total_jobs,
        'active_jobs': active_jobs,
        'completed_jobs': completed_jobs,
        'failed_jobs': failed_jobs,
        'total_pages': total_pages,
        'recent_jobs': recent_jobs,
        'clients': clients,
    }

    return render(request, 'dashboard/index.html', context)


def management_reference(request):
    """
    Simple static reference page for all management commands, with examples.
    """
    return render(request, 'dashboard/management_reference.html')


def job_detail(request, job_id):
    """
    Detailed view of a specific crawl job.
    """
    job = get_object_or_404(CrawlJob.objects.select_related('client'), id=job_id)
    logger.info(f"Job detail view called for job {job_id}")
    logger.info(f"Job status: {job.status}")
    # Get page statistics
    pages = CrawledPage.objects.filter(job=job)
    page_count = pages.count()
    logger.info(f"Page count: {page_count}")
    duplicate_count = pages.filter(is_duplicate=True).count()
    logger.info(f"Duplicate count: {duplicate_count}")
    unique_count = page_count - duplicate_count

    # Get error statistics
    errors = CrawlError.objects.filter(job=job)
    error_count = errors.count()
    error_types = errors.values('error_type').annotate(count=Count('id'))
    logger.info(f"Error types: {error_types}")
    # Get depth distribution
    depth_distribution = pages.values('depth').annotate(count=Count('id')).order_by('depth')
    logger.info(f"Depth distribution: {depth_distribution}")
    # Get doc type distribution with percentages
    doc_type_dist_raw = pages.values('doc_type').annotate(count=Count('id')).order_by('-count')[:10]
    doc_type_distribution = []
    for item in doc_type_dist_raw:
        percentage = (item['count'] / page_count * 100) if page_count > 0 else 0
        doc_type_distribution.append({
            'doc_type': item['doc_type'],
            'count': item['count'],
            'percentage': round(percentage, 1)
        })
    logger.info(f"Doc type distribution: {doc_type_distribution}")
    # Get quality metrics
    avg_word_count = pages.aggregate(avg=Avg('word_count'))['avg'] or 0
    avg_readability = pages.filter(readability_score__isnull=False).aggregate(avg=Avg('readability_score'))['avg']
    pages_with_examples = pages.filter(has_examples=True).count()
    pages_with_code = pages.filter(code_blocks__isnull=False).exclude(code_blocks=[]).count()
    logger.info(f"Pages with examples: {pages_with_examples}")
    logger.info(f"Pages with code: {pages_with_code}")
    
    # Embeddings metrics
    pages_with_embeddings = pages.filter(page_embedding__isnull=False).exclude(page_embedding=[]).count()
    embeddings_percentage = (pages_with_embeddings / page_count * 100) if page_count > 0 else 0
    logger.info(f"Pages with embeddings: {pages_with_embeddings} ({embeddings_percentage}%)")
    
    # AI Analysis metrics (optimized to avoid loading all pages into memory)
    pages_with_ai_analysis = pages.filter(ai_topics__isnull=False).exclude(ai_topics=[]).count()
    ai_analysis_percentage = (pages_with_ai_analysis / page_count * 100) if page_count > 0 else 0
    
    # Calculate average topics per analyzed page (optimized with database aggregation)
    # Instead of loading all pages, we use only() to fetch just the fields we need
    analyzed_pages = pages.exclude(ai_topics=[]).exclude(ai_topics__isnull=True).only('ai_topics', 'ai_learning_objectives')
    
    # For reasonable performance, we'll sample if there are too many pages
    if pages_with_ai_analysis > 100:
        # Sample 100 pages to estimate averages (much faster)
        analyzed_sample = analyzed_pages[:100]
        total_topics = sum(len(page.ai_topics or []) for page in analyzed_sample)
        total_los = sum(len(page.ai_learning_objectives or []) for page in analyzed_sample)
        sample_size = len(list(analyzed_sample))
        
        avg_topics_per_page = (total_topics / sample_size) if sample_size > 0 else 0
        avg_los_per_page = (total_los / sample_size) if sample_size > 0 else 0
        
        # Bloom level distribution from sample
        bloom_levels = {}
        for page in analyzed_sample:
            for lo in (page.ai_learning_objectives or []):
                level = lo.get('bloom_level', 'unknown')
                bloom_levels[level] = bloom_levels.get(level, 0) + 1
    else:
        # For small datasets, calculate exactly
        total_topics = sum(len(page.ai_topics or []) for page in analyzed_pages)
        total_los = sum(len(page.ai_learning_objectives or []) for page in analyzed_pages)
        
        avg_topics_per_page = (total_topics / pages_with_ai_analysis) if pages_with_ai_analysis > 0 else 0
        avg_los_per_page = (total_los / pages_with_ai_analysis) if pages_with_ai_analysis > 0 else 0
        
        # Bloom level distribution
        bloom_levels = {}
        for page in analyzed_pages:
            for lo in (page.ai_learning_objectives or []):
                level = lo.get('bloom_level', 'unknown')
                bloom_levels[level] = bloom_levels.get(level, 0) + 1
    
    logger.info(f"Pages with AI analysis: {pages_with_ai_analysis} ({ai_analysis_percentage}%)")
    logger.info(f"Avg topics per page: {avg_topics_per_page:.1f}, Avg LOs per page: {avg_los_per_page:.1f}")
    
    # Get sample pages
    sample_pages = pages.select_related('job').order_by('-crawled_at')[:20]
    logger.info(f"Sample pages: {sample_pages}")
    # Calculate crawl speed
    duration = job.get_duration()
    pages_per_minute = (page_count / (duration / 60)) if duration and duration > 0 else 0
    logger.info(f"Pages per minute: {pages_per_minute}")
    context = {
        'job': job,
        'page_count': page_count,
        'unique_count': unique_count,
        'duplicate_count': duplicate_count,
        'error_count': error_count,
        'error_types': error_types,
        'depth_distribution': depth_distribution,
        'doc_type_distribution': doc_type_distribution,
        'avg_word_count': int(avg_word_count),
        'avg_readability': round(avg_readability, 1) if avg_readability else None,
        'pages_with_examples': pages_with_examples,
        'pages_with_code': pages_with_code,
        'pages_with_embeddings': pages_with_embeddings,
        'embeddings_percentage': round(embeddings_percentage, 1),
        'pages_with_ai_analysis': pages_with_ai_analysis,
        'ai_analysis_percentage': round(ai_analysis_percentage, 1),
        'avg_topics_per_page': round(avg_topics_per_page, 1),
        'avg_los_per_page': round(avg_los_per_page, 1),
        'bloom_levels': bloom_levels,
        'pages_per_minute': round(pages_per_minute, 2),
        'sample_pages': sample_pages,
        'errors': errors[:20],
    }

    return render(request, 'dashboard/job_detail.html', context)


def client_detail(request, client_id):
    """
    Detailed view of a specific client.
    """
    client = get_object_or_404(Client, id=client_id)
    logger.info(f"Client detail view called for client {client_id}")
    logger.info(f"Client: {client}")
    # Get client's jobs
    jobs = CrawlJob.objects.filter(client=client).order_by('-created_at')
    logger.info(f"Jobs: {jobs}")
    # Get statistics
    total_pages = CrawledPage.objects.filter(job__client=client).count()
    completed_jobs = jobs.filter(status='completed').count()
    failed_jobs = jobs.filter(status='failed').count()
    logger.info(f"Total pages: {total_pages}")
    logger.info(f"Completed jobs: {completed_jobs}")
    logger.info(f"Failed jobs: {failed_jobs}")
    context = {
        'client': client,
        'jobs': jobs,
        'total_pages': total_pages,
        'completed_jobs': completed_jobs,
        'failed_jobs': failed_jobs,
    }

    return render(request, 'dashboard/client_detail.html', context)


def job_stats_api(request, job_id):
    """
    API endpoint for real-time job statistics (AJAX polling).
    """
    job = get_object_or_404(CrawlJob, id=job_id)
    logger.info(f"Job stats API called for job {job_id}")
    logger.info(f"Job: {job}")
    # Get live statistics
    pages = CrawledPage.objects.filter(job=job)
    page_count = pages.count()
    logger.info(f"Page count: {page_count}")
    duplicate_count = pages.filter(is_duplicate=True).count()
    logger.info(f"Duplicate count: {duplicate_count}")
    error_count = CrawlError.objects.filter(job=job).count()
    logger.info(f"Error count: {error_count}")
    # Get recent pages (last 5)
    recent_pages = pages.order_by('-crawled_at')[:5].values(
        'url', 'title', 'depth', 'word_count', 'crawled_at'
    )
    logger.info(f"Recent pages: {recent_pages}")
    # Calculate speed
    duration = job.get_duration()
    pages_per_minute = (page_count / (duration / 60)) if duration and duration > 0 else 0
    logger.info(f"Pages per minute: {pages_per_minute}")
    data = {
        'job_id': job.id,
        'status': job.status,
        'page_count': page_count,
        'unique_count': page_count - duplicate_count,
        'duplicate_count': duplicate_count,
        'error_count': error_count,
        'pages_per_minute': round(pages_per_minute, 2),
        'progress_percentage': job.progress_percentage,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'duration': duration,
        'recent_pages': list(recent_pages),
    }
    
    return JsonResponse(data)


def page_detail(request, page_id):
    """
    Executive dashboard view for a single crawled page showing all AI-era SEO metrics.
    """
    page = get_object_or_404(CrawledPage.objects.select_related('job__client'), id=page_id)
    logger.info(f"Page detail view called for page {page_id}")
    logger.info(f"Page: {page}")
    # Calculate overall scores
    eeat_score = calculate_eeat_score(page)
    rag_readiness_score = calculate_rag_score(page)
    accessibility_score = calculate_accessibility_score(page)
    content_quality_score = calculate_content_quality_score(page)
    overall_ai_readiness = (eeat_score + rag_readiness_score + accessibility_score + content_quality_score) / 4
    
    context = {
        'page': page,
        'eeat_score': eeat_score,
        'rag_readiness_score': rag_readiness_score,
        'accessibility_score': accessibility_score,
        'content_quality_score': content_quality_score,
        'overall_ai_readiness': overall_ai_readiness,
    }
    
    return render(request, 'dashboard/page_detail.html', context)


def calculate_eeat_score(page):
    """Calculate E-E-A-T (Experience, Expertise, Authoritativeness, Trust) score out of 100."""
    score = 0

    logger.info(f"Calculating E-E-A-T score for page {page.id}")
    # Author present (25 points)
    if page.author:
        score += 25
    
    # Has references (25 points)
    if page.has_references:
        score += min(25, page.reference_count * 5)
    
    # Content freshness (25 points)
    if page.published_date or page.last_updated_text:
        score += 25
    
    # Reviewed/verified (25 points)
    if page.reviewed_by:
        score += 25
    elif page.author_bio:
        score += 15  # Author credentials mentioned
    
    return min(100, score)


def calculate_rag_score(page):
    """Calculate RAG (Retrieval Augmented Generation) readiness score out of 100."""
    score = 0
    
    # Has prerequisites (20 points)
    if page.has_prerequisites:
        score += 20
    
    # Has learning objectives (20 points)
    if page.has_learning_objectives:
        score += 20
    
    # Has Q&A pairs (30 points)
    if page.qa_count > 0:
        score += min(30, page.qa_count * 5)
    
    # Self-contained content (30 points)
    if page.has_next_steps:
        score += 10
    if page.sections_count >= 3:
        score += 10
    if page.has_examples:
        score += 10
    
    return min(100, score)


def calculate_accessibility_score(page):
    """Calculate accessibility score out of 100."""
    score = 0
    
    # Alt text quality (30 points)
    score += page.alt_text_quality_score * 30
    
    # Heading structure (20 points)
    if page.heading_structure_valid:
        score += 20
    
    # Mobile viewport (15 points)
    if page.mobile_viewport_meta:
        score += 15
    
    # ARIA labels (20 points)
    if page.aria_labels_count > 0:
        score += min(20, page.aria_labels_count * 2)
    
    # Skip links (15 points)
    if page.has_skip_links:
        score += 15
    
    return min(100, score)


def calculate_content_quality_score(page):
    """Calculate content quality score out of 100."""
    score = 0
    
    # Comprehensiveness (40 points)
    score += min(40, page.content_type_diversity * 8)
    
    # Has examples (15 points)
    if page.has_examples:
        score += 15
    
    # Has troubleshooting (15 points)
    if page.has_troubleshooting:
        score += 15
    
    # Readability (20 points)
    if page.readability_score:
        # Flesch Reading Ease: 60-70 is ideal
        if 60 <= page.readability_score <= 70:
            score += 20
        elif 50 <= page.readability_score <= 80:
            score += 15
        elif page.readability_score >= 40:
            score += 10
    
    # Interactive features (10 points)
    interactive_count = sum([
        page.has_code_playground,
        page.has_api_explorer,
        page.has_feedback_mechanism,
        page.has_version_switcher,
    ])
    score += min(10, interactive_count * 3)
    
    return min(100, score)


def client_pages(request, client_id):
    """
    View all pages crawled for a specific client with filtering and sorting.
    """
    client = get_object_or_404(Client, id=client_id)
    
    # Get all pages for this client
    pages = CrawledPage.objects.filter(job__client=client).select_related('job')
    
    # Get filter parameters
    doc_type_filter = request.GET.get('doc_type', '')
    job_filter = request.GET.get('job', '')
    depth_filter = request.GET.get('depth', '')
    has_examples = request.GET.get('has_examples', '')
    has_code = request.GET.get('has_code', '')
    has_embeddings = request.GET.get('has_embeddings', '')
    quality_filter = request.GET.get('quality', '')
    search_query = request.GET.get('q', '')
    
    # Apply filters
    if doc_type_filter:
        pages = pages.filter(doc_type=doc_type_filter)
    
    if job_filter:
        pages = pages.filter(job_id=job_filter)
    
    if depth_filter:
        pages = pages.filter(depth=int(depth_filter))
    
    if has_examples == 'true':
        pages = pages.filter(has_examples=True)
    
    if has_code == 'true':
        pages = pages.filter(code_blocks__isnull=False).exclude(code_blocks=[])
    
    if has_embeddings == 'true':
        pages = pages.filter(page_embedding__isnull=False).exclude(page_embedding=[])
    elif has_embeddings == 'false':
        pages = pages.filter(Q(page_embedding__isnull=True) | Q(page_embedding=[]))
    
    if quality_filter == 'high':
        # High quality: good readability and substantial content
        pages = pages.filter(
            Q(readability_score__gte=60) | Q(readability_score__isnull=True),
            word_count__gte=300
        )
    elif quality_filter == 'low':
        # Low quality: poor readability or thin content
        pages = pages.filter(
            Q(readability_score__lt=30) | Q(word_count__lt=100)
        )
    
    if search_query:
        logger.info(f"Search query received: '{search_query}'")
        # Search in title and URL (fast), and optionally in content
        pages = pages.filter(
            Q(title__icontains=search_query) |
            Q(url__icontains=search_query) |
            Q(main_content__icontains=search_query)
        )
        logger.info(f"Search filtered pages count: {pages.count()}")
    
    # Get sorting parameter
    sort_by = request.GET.get('sort', '-crawled_at')
    valid_sorts = [
        'title', '-title',
        'url', '-url',
        'doc_type', '-doc_type',
        'depth', '-depth',
        'word_count', '-word_count',
        'readability_score', '-readability_score',
        'crawled_at', '-crawled_at',
        'estimated_reading_time', '-estimated_reading_time',
    ]
    
    if sort_by in valid_sorts:
        pages = pages.order_by(sort_by)
    else:
        pages = pages.order_by('-crawled_at')
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(pages, 50)  # 50 pages per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get filter options (with deduplication)
    doc_types = CrawledPage.objects.filter(job__client=client).values_list('doc_type', flat=True).order_by('doc_type').distinct()
    jobs = CrawlJob.objects.filter(client=client).order_by('-created_at')
    depths = CrawledPage.objects.filter(job__client=client).values_list('depth', flat=True).order_by('depth').distinct()
    
    # Get summary statistics
    total_count = pages.count()
    avg_word_count = pages.aggregate(avg=Avg('word_count'))['avg'] or 0
    avg_readability = pages.filter(readability_score__isnull=False).aggregate(avg=Avg('readability_score'))['avg']
    
    # Calculate AI-era SEO aggregate scores
    pages_with_scores = pages.filter(word_count__gt=0)  # Only pages with content
    
    # E-E-A-T metrics
    pages_with_author = pages.exclude(author='').count()
    pages_with_dates = pages.exclude(Q(published_date='') & Q(last_updated_text='')).count()
    pages_with_references = pages.filter(has_references=True).count()
    
    # RAG metrics
    pages_with_prerequisites = pages.filter(has_prerequisites=True).count()
    pages_with_qa = pages.filter(qa_count__gt=0).count()
    avg_qa_count = pages.aggregate(avg=Avg('qa_count'))['avg'] or 0
    
    # Accessibility metrics
    avg_alt_text_quality = pages.aggregate(avg=Avg('alt_text_quality_score'))['avg'] or 0
    pages_mobile_ready = pages.filter(mobile_viewport_meta=True).count()
    pages_valid_headings = pages.filter(heading_structure_valid=True).count()
    
    # Content quality
    pages_with_examples = pages.filter(has_examples=True).count()
    pages_with_troubleshooting = pages.filter(has_troubleshooting=True).count()
    avg_content_diversity = pages.aggregate(avg=Avg('content_type_diversity'))['avg'] or 0
    
    # Embeddings metrics
    pages_with_embeddings = pages.filter(page_embedding__isnull=False).exclude(page_embedding=[]).count()
    embeddings_percentage = (pages_with_embeddings / total_count * 100) if total_count > 0 else 0
    
    # Calculate percentage scores
    eeat_percentage = 0
    rag_percentage = 0
    accessibility_percentage = 0
    quality_percentage = 0
    
    if total_count > 0:
        eeat_percentage = ((pages_with_author + pages_with_dates + pages_with_references) / (total_count * 3)) * 100
        rag_percentage = ((pages_with_prerequisites + pages_with_qa) / (total_count * 2)) * 100
        accessibility_percentage = ((pages_mobile_ready + pages_valid_headings) / (total_count * 2)) * 100
        quality_percentage = ((pages_with_examples + pages_with_troubleshooting) / (total_count * 2)) * 100
    
    context = {
        'client': client,
        'page_obj': page_obj,
        'total_count': total_count,
        'avg_word_count': int(avg_word_count),
        'avg_readability': round(avg_readability, 1) if avg_readability else None,
        
        # AI-era SEO metrics
        'eeat_percentage': round(eeat_percentage, 1),
        'rag_percentage': round(rag_percentage, 1),
        'accessibility_percentage': round(accessibility_percentage, 1),
        'quality_percentage': round(quality_percentage, 1),
        'overall_ai_score': round((eeat_percentage + rag_percentage + accessibility_percentage + quality_percentage) / 4, 1),
        
        # Detailed counts
        'pages_with_author': pages_with_author,
        'pages_with_dates': pages_with_dates,
        'pages_with_references': pages_with_references,
        'pages_with_prerequisites': pages_with_prerequisites,
        'pages_with_qa': pages_with_qa,
        'avg_qa_count': round(avg_qa_count, 1),
        'avg_alt_text_quality': round(avg_alt_text_quality * 100, 1),
        'pages_mobile_ready': pages_mobile_ready,
        'pages_valid_headings': pages_valid_headings,
        'pages_with_examples': pages_with_examples,
        'pages_with_troubleshooting': pages_with_troubleshooting,
        'avg_content_diversity': round(avg_content_diversity, 1),
        
        # Embeddings metrics
        'pages_with_embeddings': pages_with_embeddings,
        'embeddings_percentage': round(embeddings_percentage, 1),
        
        # Filter options
        'doc_types': doc_types,
        'jobs': jobs,
        'depths': depths,
        
        # Current filters
        'current_doc_type': doc_type_filter,
        'current_job': job_filter,
        'current_depth': depth_filter,
        'current_has_examples': has_examples,
        'current_has_code': has_code,
        'current_has_embeddings': has_embeddings,
        'current_quality': quality_filter,
        'current_search': search_query,
        'current_sort': sort_by,
    }
    
    return render(request, 'dashboard/client_pages.html', context)


def new_crawl(request):
    """
    Form to create and start a new crawl job.
    """
    if request.method == 'POST':
        target_url = request.POST.get('target_url')
        client_id = request.POST.get('client_id')
        depth_limit = int(request.POST.get('depth_limit', 5))
        use_playwright = request.POST.get('use_playwright', 'auto')
        max_pages = request.POST.get('max_pages')
        capture_html = request.POST.get('capture_html') == 'on'
        screenshots = request.POST.get('screenshots') == 'on'
        
        if not target_url or not client_id:
            messages.error(request, 'Target URL and Client are required.')
            return redirect('dashboard:new_crawl')
        
        try:
            # Handle new client creation
            if client_id == '__new__':
                new_client_name = request.POST.get('new_client_name', '').strip()
                if not new_client_name:
                    messages.error(request, 'Please enter a name for the new client.')
                    return redirect('dashboard:new_crawl')

                # Generate a unique slug from the name
                base_slug = slugify(new_client_name) or 'client'
                slug = base_slug
                counter = 1
                while Client.objects.filter(slug=slug).exists():
                    counter += 1
                    slug = f"{base_slug}-{counter}"

                # Create the new client
                client = Client.objects.create(
                    name=new_client_name,
                    slug=slug,
                    is_active=True,
                )
                messages.info(request, f'Created new client: {client.name}')
            else:
                client = Client.objects.get(id=client_id)
            
            # Build configuration
            config = {
                'depth_limit': depth_limit,
                'use_playwright': use_playwright,
                'capture_html': capture_html,
                'screenshots': screenshots,
            }
            
            # Add max_pages if specified
            if max_pages and max_pages.strip():
                config['max_pages'] = int(max_pages)
            
            # Create the job
            job = CrawlJob.objects.create(
                client=client,
                target_url=target_url,
                status='pending',
                config=config
            )
            
            # Start the crawl task
            task = start_crawl_task.delay(job.id)
            job.celery_task_id = task.id
            job.save(update_fields=['celery_task_id'])
            
            messages.success(request, f'Crawl job #{job.id} created and started!')
            return redirect('dashboard:job_detail', job_id=job.id)
            
        except Client.DoesNotExist:
            messages.error(request, 'Invalid client selected.')
            return redirect('dashboard:new_crawl')
        except Exception as e:
            messages.error(request, f'Error creating crawl: {str(e)}')
            return redirect('dashboard:new_crawl')
    
    # GET request - show form
    clients = Client.objects.filter(is_active=True).order_by('name')
    context = {
        'clients': clients,
    }
    return render(request, 'dashboard/new_crawl.html', context)


@require_POST
def cancel_job(request, job_id):
    """
    Cancel a running or pending crawl job.
    """
    job = get_object_or_404(CrawlJob, id=job_id)
    
    if job.status in ['pending', 'running']:
        # Terminate the Celery task if it exists
        if job.celery_task_id:
            current_app.control.revoke(job.celery_task_id, terminate=True)
        
        # Update job status
        job.status = 'cancelled'
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'completed_at'])
        
        messages.success(request, f'Job #{job_id} has been cancelled.')
    else:
        messages.warning(request, f'Job #{job_id} is {job.status} and cannot be cancelled.')
    
    return redirect('dashboard:job_detail', job_id=job_id)


@require_POST
def delete_job(request, job_id):
    """
    Delete a crawl job and all its associated data.
    """
    job = get_object_or_404(CrawlJob, id=job_id)
    
    # Cancel if running
    if job.status in ['pending', 'running']:
        if job.celery_task_id:
            current_app.control.revoke(job.celery_task_id, terminate=True)
    
    # Store client ID for redirect
    client_id = job.client.id
    
    # Delete the job (cascades to pages)
    job.delete()
    
    messages.success(request, f'Job #{job_id} and all associated data have been deleted.')
    return redirect('dashboard:client_detail', client_id=client_id)


@require_POST
def restart_job(request, job_id):
    """
    Restart a completed, failed, or cancelled job.
    """
    job = get_object_or_404(CrawlJob, id=job_id)
    
    if job.status in ['completed', 'failed', 'cancelled']:
        # Reset job status
        job.status = 'pending'
        job.started_at = None
        job.completed_at = None
        job.error_message = None
        job.pages_crawled = 0
        job.unique_content_pages = 0
        
        # Clear old pages (optional - uncomment if you want to recrawl from scratch)
        # job.pages.all().delete()
        
        job.save()
        
        # Start the crawl task
        task = start_crawl_task.delay(job.id)
        job.celery_task_id = task.id
        job.save(update_fields=['celery_task_id'])
        
        messages.success(request, f'Job #{job_id} has been restarted.')
    else:
        messages.warning(request, f'Job #{job_id} is {job.status} and cannot be restarted.')
    
    return redirect('dashboard:job_detail', job_id=job_id)


@require_POST
def generate_job_embeddings(request, job_id):
    """
    Trigger embedding generation for all pages in a job via Celery.
    
    Enqueues a separate Celery task for each page that needs embeddings.
    """
    job = get_object_or_404(CrawlJob, id=job_id)
    
    # Check if force regeneration is requested
    force = request.POST.get('force') == 'true'
    
    # Filter pages: all if force, otherwise only those without embeddings
    if force:
        pages = CrawledPage.objects.filter(job=job)
    else:
        from django.db.models import Q
        pages = CrawledPage.objects.filter(
            job=job
        ).filter(
            Q(page_embedding__isnull=True) | Q(page_embedding=[])
        )
    
    count = pages.count()
    
    if count == 0:
        if force:
            messages.warning(request, f'No pages found in job #{job_id}.')
        else:
            messages.info(
                request, 
                f'All pages in job #{job_id} already have embeddings. '
                'Use "Force regenerate" to recompute them.'
            )
        return redirect('dashboard:job_detail', job_id=job_id)
    
    # Enqueue Celery tasks for each page
    for page in pages:
        generate_page_embeddings_task.delay(page.id, force=force)
    
    messages.success(
        request,
        f'Embedding generation started for {count} page(s) in job #{job_id}. '
        f'This will take approximately {count * 2} seconds. '
        'Refresh this page or check individual pages to see progress.'
    )
    
    return redirect('dashboard:job_detail', job_id=job_id)


@require_POST
def analyze_job_content(request, job_id):
    """
    Trigger AI content analysis for all pages in a job.
    
    Analyzes pages to extract topics, learning objectives, and prerequisite chains.
    """
    from decouple import config
    from django.db.models import Q
    
    job = get_object_or_404(CrawlJob, id=job_id)
    
    # Get API key
    api_key = config("OPENAI_API_KEY", default=None) or config("OPENAI_KEY", default=None)
    if not api_key:
        messages.error(request, "OPENAI_API_KEY not configured. Cannot analyze content.")
        return redirect('dashboard:job_detail', job_id=job_id)
    
    # Check if force re-analysis is requested
    force = request.POST.get('force') == 'true'
    
    # Filter pages: all if force, otherwise only those without AI analysis
    queryset = CrawledPage.objects.filter(job=job)
    queryset = queryset.exclude(main_content__isnull=True).exclude(main_content="")
    
    # Skip certain doc types to save costs
    # Note: 'unknown' is NOT skipped because AI analysis reclassifies pages
    skip_types = ['navigation', 'landing', 'changelog']
    queryset = queryset.exclude(doc_type__in=skip_types)
    
    if not force:
        queryset = queryset.filter(
            Q(ai_topics__isnull=True) | Q(ai_topics=[])
        )
    
    count = queryset.count()
    
    if count == 0:
        if force:
            messages.warning(request, f'No analyzable pages found in job #{job_id}.')
        else:
            messages.info(
                request, 
                f'All pages in job #{job_id} already have AI analysis. '
                'Use "Force reanalyze" to recompute.'
            )
        return redirect('dashboard:job_detail', job_id=job_id)
    
    # Estimate cost
    estimated_cost = count * 0.00015
    estimated_time_minutes = (count * 2) / 60
    
    messages.info(
        request,
        f'Starting AI content analysis for {count} page(s) in job #{job_id}. '
        f'Estimated cost: ${estimated_cost:.4f}, '
        f'estimated time: {estimated_time_minutes:.1f} minutes. '
        'This will run in the background. Refresh this page to see progress.'
    )
    
    # TODO: In the future, this should be a Celery task for better async handling
    # For now, we'll process synchronously with a limit to avoid timeouts
    
    analyzer = ContentAnalyzer(openai_api_key=api_key)
    success_count = 0
    error_count = 0
    
    # Process pages (limit to 50 to avoid timeout)
    batch_limit = min(count, 50)
    for page in queryset[:batch_limit]:
        try:
            result = analyzer.analyze_page(
                page_id=page.id,
                url=page.url,
                title=page.title,
                main_content=page.main_content,
                sections=page.sections or [],
                doc_type=page.doc_type,
                existing_prerequisites=page.prerequisites or [],
                existing_learning_objectives=page.learning_objectives or [],
            )
            
            # Save results
            page.ai_topics = result["ai_topics"]
            page.ai_learning_objectives = result["ai_learning_objectives"]
            page.ai_prerequisite_chain = result["ai_prerequisite_chain"]
            page.ai_analysis_metadata = result["ai_analysis_metadata"]
            
            # Merge with existing fields
            enhanced_prereqs, enhanced_los = analyzer.merge_with_existing(
                ai_result=result,
                existing_prerequisites=page.prerequisites or [],
                existing_learning_objectives=page.learning_objectives or [],
            )
            page.prerequisites = enhanced_prereqs
            page.learning_objectives = enhanced_los
            page.has_prerequisites = len(enhanced_prereqs) > 0
            page.has_learning_objectives = len(enhanced_los) > 0
            
            page.save(update_fields=[
                'ai_topics',
                'ai_learning_objectives',
                'ai_prerequisite_chain',
                'ai_analysis_metadata',
                'prerequisites',
                'learning_objectives',
                'has_prerequisites',
                'has_learning_objectives',
            ])
            
            success_count += 1
            
        except Exception as exc:
            logger.error(f"Error analyzing page {page.id}: {exc}")
            error_count += 1
            continue
    
    if success_count > 0:
        actual_cost = success_count * 0.00015
        messages.success(
            request,
            f'AI analysis completed: {success_count} pages analyzed '
            f'(${actual_cost:.4f} cost). '
            f'{error_count} errors.'
        )
    else:
        messages.error(request, f'AI analysis failed for all pages. Check logs.')
    
    if count > batch_limit:
        messages.warning(
            request,
            f'Note: Only processed {batch_limit} of {count} pages to avoid timeout. '
            'Run the management command for larger batches: '
            f'python manage.py analyze_content --job-id {job_id}'
        )
    
    return redirect('dashboard:job_detail', job_id=job_id)


def job_logs(request, job_id):
    """
    Stream or display logs for a specific job.
    """
    from django.conf import settings
    from pathlib import Path
    
    job = get_object_or_404(CrawlJob, id=job_id)
    
    # Read recent log entries
    log_file = Path(settings.BASE_DIR) / 'logs' / 'crawler.log'
    
    logs = []
    if log_file.exists():
        try:
            with open(log_file, 'r') as f:
                # Read last 200 lines
                all_lines = f.readlines()
                recent_lines = all_lines[-200:]
                
                # Filter for this job ID
                for line in recent_lines:
                    if f'job {job_id}' in line.lower() or f'job_{job_id}' in line.lower() or f'job:{job_id}' in line.lower():
                        logs.append(line.strip())
        except Exception as e:
            logs.append(f"Error reading logs: {str(e)}")
    
    # If no logs found, show a message
    if not logs:
        logs.append(f"No log entries found for job {job_id} yet. Logs will appear here as the crawl progresses.")
    
    if request.headers.get('Accept') == 'application/json' or request.GET.get('format') == 'json':
        return JsonResponse({'logs': logs, 'count': len(logs)})
    
    context = {
        'job': job,
        'logs': logs,
    }
    return render(request, 'dashboard/job_logs.html', context)


def page_raw_html(request, page_id):
    """
    Display the raw HTML of a crawled page.
    """
    page = get_object_or_404(CrawledPage, id=page_id)
    
    if not page.raw_html:
        messages.warning(request, 'No raw HTML available for this page.')
        return redirect('dashboard:page_detail', page_id=page_id)
    
    # Return as HTML response with syntax highlighting
    context = {
        'page': page,
        'raw_html': page.raw_html,
    }
    return render(request, 'dashboard/page_raw_html.html', context)


def page_screenshot(request, page_id):
    """
    Display the screenshot of a crawled page.
    """
    from django.conf import settings
    from django.http import FileResponse, Http404, HttpResponse
    import os
    
    page = get_object_or_404(CrawledPage, id=page_id)
    
    if not page.screenshot_path:
        return HttpResponse(
            '<html><body style="font-family: system-ui; padding: 2rem; text-align: center;">'
            '<h2>No Screenshot Available</h2>'
            '<p>This page was crawled without screenshots enabled.</p>'
            f'<p><a href="/page/{page_id}/" style="color: #667eea;">← Back to Page Details</a></p>'
            '<p><a href="/page/{}/capture-screenshot/" style="background: #667eea; color: white; padding: 0.5rem 1rem; text-decoration: none; border-radius: 4px;">📸 Capture Screenshot Now</a></p>'
            '</body></html>'.format(page_id),
            content_type='text/html'
        )
    
    # Build full path to screenshot
    screenshot_path = page.screenshot_path
    if os.path.isabs(screenshot_path):
        screenshot_full_path = screenshot_path
    else:
        screenshot_full_path = os.path.join(settings.BASE_DIR, screenshot_path)
    
    if not os.path.exists(screenshot_full_path):
        # Screenshot path exists in DB but file is missing - offer to recapture
        return HttpResponse(
            '<html><body style="font-family: system-ui; padding: 2rem; text-align: center;">'
            '<h2>Screenshot File Not Found</h2>'
            f'<p>Expected location: <code>{screenshot_full_path}</code></p>'
            '<p>The screenshot may have been deleted or failed to save during crawling.</p>'
            f'<p><a href="/page/{page_id}/" style="color: #667eea;">← Back to Page Details</a></p>'
            '<p><a href="/page/{}/capture-screenshot/" style="background: #667eea; color: white; padding: 0.5rem 1rem; text-decoration: none; border-radius: 4px;">📸 Capture Screenshot Now</a></p>'
            '</body></html>'.format(page_id),
            content_type='text/html'
        )
    
    # Return the image file
    return FileResponse(open(screenshot_full_path, 'rb'), content_type='image/png')


@require_POST
def capture_page_screenshot(request, page_id):
    """
    Trigger screenshot capture for a specific page.
    """
    from crawler.tasks import capture_page_screenshot_task
    
    page = get_object_or_404(CrawledPage, id=page_id)
    
    # Start the screenshot capture task
    task = capture_page_screenshot_task.delay(page_id)
    
    messages.success(
        request, 
        f'Screenshot capture started for "{page.title or page.url}". '
        'Refresh the page in a few seconds to see the result.'
    )
    
    return redirect('dashboard:page_detail', page_id=page_id)


@require_POST
def generate_page_embeddings(request, page_id):
    """
    Trigger embedding generation for a specific page via Celery.

    This uses the same logic as the `generate_embeddings` management command,
    but scoped to a single page from the UI.
    """
    page = get_object_or_404(CrawledPage, id=page_id)

    # Enqueue Celery task (force recompute to keep UI deterministic)
    generate_page_embeddings_task.delay(page.id, force=True)

    messages.success(
        request,
        f'Embedding generation started for "{page.title or page.url}". '
        'Refresh this page in a few seconds to see updated embedding status.'
    )

    return redirect('dashboard:page_detail', page_id=page_id)


def page_json(request, page_id):
    """
    Display the complete JSON representation of a page including all metadata and content.
    """
    from django.http import JsonResponse
    from django.core.serializers.json import DjangoJSONEncoder
    import json
    
    page = get_object_or_404(CrawledPage, id=page_id)
    
    # Build comprehensive JSON representation
    page_data = {
        'id': page.id,
        'url': page.url,
        'title': page.title,
        'meta_description': page.meta_description,
        'status_code': page.status_code,
        'depth': page.depth,
        'content_hash': page.content_hash,
        
        # Job and Client info
        'job': {
            'id': page.job.id,
            'target_url': page.job.target_url,
            'status': page.job.status,
            'created_at': page.job.created_at.isoformat() if page.job.created_at else None,
            'started_at': page.job.started_at.isoformat() if page.job.started_at else None,
            'completed_at': page.job.completed_at.isoformat() if page.job.completed_at else None,
            'pages_crawled': page.job.pages_crawled,
            'max_depth': page.job.max_depth,
            'config': page.job.config,
        },
        'client': {
            'id': page.client.id,
            'name': page.client.name,
            'slug': page.client.slug,
            'contact_email': page.client.contact_email,
            'is_active': page.client.is_active,
        },
        
        # Documentation classification
        'classification': {
            'doc_type': page.doc_type,
            'doc_category': page.doc_category,
            'version_info': page.version_info,
        },
        
        # Timestamps
        'timestamps': {
            'crawled_at': page.crawled_at.isoformat() if page.crawled_at else None,
            'last_modified': page.last_modified.isoformat() if page.last_modified else None,
            'published_date': page.published_date,
            'last_updated_text': page.last_updated_text,
        },
        
        # E-E-A-T (Expertise, Authoritativeness, Trust)
        'eeat': {
            'author': page.author,
            'author_bio': page.author_bio,
            'reviewed_by': page.reviewed_by,
            'external_references': page.external_references,
            'reference_count': page.reference_count,
            'has_references': page.has_references,
        },
        
        # Navigation
        'navigation': {
            'breadcrumb': page.breadcrumb,
            'sidebar_position': page.sidebar_position,
            'navigation_title': page.navigation_title,
            'table_of_contents': page.table_of_contents,
        },
        
        # Content structure
        'structure': {
            'headers': page.headers,
            'sections': page.sections,
            'internal_links': page.internal_links,
            'external_links': page.external_links,
            'code_blocks': page.code_blocks,
            'tables': page.tables,
            'images': page.images,
        },
        
        # Special content
        'special_content': {
            'api_endpoints': page.api_endpoints,
            'parameters': page.parameters,
            'warnings': page.warnings,
            'tips': page.tips,
            'questions': page.questions,
        },
        
        # RAG optimization fields
        'rag_context': {
            'prerequisites': page.prerequisites,
            'learning_objectives': page.learning_objectives,
            'next_steps': page.next_steps,
            'has_prerequisites': page.has_prerequisites,
            'has_learning_objectives': page.has_learning_objectives,
            'has_next_steps': page.has_next_steps,
        },
        
        # Content metrics
        'metrics': {
            'word_count': page.word_count,
            'estimated_reading_time': page.estimated_reading_time,
            'paragraph_count': page.paragraph_count,
            'list_count': page.list_count,
            'sections_count': page.sections_count,
            'header_count': len(page.headers) if page.headers else 0,
            'code_block_count': len(page.code_blocks) if page.code_blocks else 0,
            'internal_link_count': len(page.internal_links) if page.internal_links else 0,
            'external_link_count': len(page.external_links) if page.external_links else 0,
            'image_count': len(page.images) if page.images else 0,
            'table_count': len(page.tables) if page.tables else 0,
            'reference_count': page.reference_count,
            'qa_count': page.qa_count,
            'imperative_sentence_count': page.imperative_sentence_count,
            'script_count': page.script_count,
            'stylesheet_count': page.stylesheet_count,
            'aria_labels_count': page.aria_labels_count,
        },
        
        # Content quality
        'quality': {
            'has_examples': page.has_examples,
            'has_diagrams': page.has_diagrams,
            'has_troubleshooting': page.has_troubleshooting,
            'has_tldr': page.has_tldr,
            'has_step_by_step': page.has_step_by_step,
            'has_deprecation_warning': page.has_deprecation_warning,
            'readability_score': page.readability_score,
            'code_to_text_ratio': page.code_to_text_ratio,
            'average_paragraph_length': page.average_paragraph_length,
            'code_blocks_count': len(page.code_blocks) if page.code_blocks else 0,
            'images_count': len(page.images) if page.images else 0,
            'tables_counts': len(page.tables) if page.tables else 0,
            'warnings_count': len(page.warnings) if page.warnings else 0,
            'tips_count': len(page.tips) if page.tips else 0,
        },
        
        # Accessibility
        'accessibility': {
            'alt_text_quality_score': page.alt_text_quality_score,
            'aria_labels_count': page.aria_labels_count,
            'has_skip_links': page.has_skip_links,
        },
        
        # Interactive features
        'interactive': {
            'has_table_of_contents': page.has_table_of_contents,
            'has_search': page.has_search,
            'has_interactive_elements': page.has_interactive_elements,
            'has_videos': page.has_videos,
            'has_copy_buttons': page.has_copy_buttons,
            'has_code_playground': page.has_code_playground,
            'has_api_explorer': page.has_api_explorer,
            'has_feedback_mechanism': page.has_feedback_mechanism,
            'has_version_switcher': page.has_version_switcher,
            'has_community_comments': page.has_community_comments,
        },
        
        # SEO
        'seo': {
            'og_tags': page.og_tags,
            'schema_markup': page.schema_markup,
            'canonical_url': page.canonical_url,
            'meta_keywords': page.meta_keywords,
            'hreflang_tags': page.hreflang_tags,
            'structured_data_types': page.structured_data_types,
            'has_breadcrumb_schema': page.has_breadcrumb_schema,
            'has_article_schema': page.has_article_schema,
            'has_howto_schema': page.has_howto_schema,
            'has_faq_schema': page.has_faq_schema,
        },
        
        # Performance
        'performance': {
            'response_time': page.response_time,
            'page_size': page.page_size,
            'render_method': page.render_method,
            'javascript_render_time': page.javascript_render_time,
            'script_count': page.script_count,
            'stylesheet_count': page.stylesheet_count,
            'third_party_scripts': page.third_party_scripts,
        },
        
        # Q&A pairs
        'qa': {
            'qa_pairs': page.qa_pairs,
            'qa_count': page.qa_count,
            'questions': page.questions,
        },
        
        # Files
        'files': {
            'screenshot_path': page.screenshot_path,
            'has_screenshot': bool(page.screenshot_path),
            'has_raw_html': bool(page.raw_html),
        },
        
        # Main content (full text)
        'content': {
            'main_content': page.main_content,
            'raw_html': page.raw_html if page.raw_html else None,
        },
    }
    
    # Check if request wants HTML view or pure JSON
    if request.GET.get('format') == 'raw':
        # Return pure JSON for API usage
        return JsonResponse(page_data, json_dumps_params={'indent': 2}, encoder=DjangoJSONEncoder)
    else:
        # Return HTML page with pretty-printed JSON
        context = {
            'page': page,
            'json_data': json.dumps(page_data, indent=2, cls=DjangoJSONEncoder),
        }
        return render(request, 'dashboard/page_json.html', context)


def client_taxonomy(request, client_id):
    """
    Display the taxonomy view for a specific client.
    
    Shows the hierarchical organization of documentation based on:
    - Semantic clustering (from embeddings)
    - Topic categorization (from AI analysis)
    - Prerequisite relationships
    """
    from django.conf import settings
    from pathlib import Path
    import json
    import glob
    
    client = get_object_or_404(Client, id=client_id)
    logger.info(f"Client taxonomy view called for client {client_id}")
    
    # Look for taxonomy files in the taxonomies directory
    taxonomies_dir = Path(settings.BASE_DIR) / 'taxonomies'
    
    # Find all taxonomy JSON files for this client
    # Pattern: {client_slug}_taxonomy_*.json
    taxonomy_files = []
    if taxonomies_dir.exists():
        pattern = f"{client.slug}_taxonomy_*.json"
        taxonomy_files = sorted(
            taxonomies_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True  # Most recent first
        )
    
    taxonomy_data = None
    taxonomy_file_path = None
    error_message = None
    
    if taxonomy_files:
        # Load the most recent taxonomy file
        taxonomy_file_path = taxonomy_files[0]
        try:
            with open(taxonomy_file_path, 'r') as f:
                taxonomy_data = json.load(f)
            logger.info(f"Loaded taxonomy from {taxonomy_file_path}")
        except Exception as e:
            logger.error(f"Error loading taxonomy file {taxonomy_file_path}: {e}")
            error_message = f"Error loading taxonomy: {str(e)}"
    else:
        logger.warning(f"No taxonomy files found for client {client.slug}")
        error_message = (
            f"No taxonomy has been generated for {client.name} yet. "
            f"Run 'python manage.py build_taxonomy --client-id {client_id}' to create one."
        )
    
    context = {
        'client': client,
        'taxonomy': taxonomy_data,
        'taxonomy_file': taxonomy_file_path.name if taxonomy_file_path else None,
        'available_taxonomies': [f.name for f in taxonomy_files],
        'error_message': error_message,
    }
    
    return render(request, 'dashboard/client_taxonomy.html', context)
