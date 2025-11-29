"""
Celery tasks for crawler operations.
"""

from celery import shared_task
from django.conf import settings
import logging
import subprocess
import os
from scrapy.utils.project import get_project_settings
from scrapy.crawler import CrawlerProcess
from crawler.models import CrawlJob

logger = logging.getLogger('crawler')


@shared_task(bind=True, time_limit=86400)  # 24 hour time limit
def start_crawl_task(self, job_id):
    """
    Start a Scrapy crawl for the given job.

    Args:
        job_id: The ID of the CrawlJob to execute

    Returns:
        dict: Crawl results and statistics
    """
    from core.models import CrawlJob

    logger.info(f"Starting crawl task for job {job_id}")

    try:
        # Get the job
        job = CrawlJob.objects.get(id=job_id)

        # Update job status
        job.mark_started()

        # Get configuration
        target_url = job.target_url
        max_depth = job.get_depth_limit()
        allowed_domains = ','.join(job.get_allowed_domains()) if job.get_allowed_domains() else None
        use_playwright = job.config.get('use_playwright', 'auto')
        max_pages = job.config.get('max_pages')
        capture_html = job.config.get('capture_html', False)
        screenshots = job.config.get('screenshots', False)
        crawl_config_id = job.config.get('crawl_config_id')

        # Build Scrapy command
        scrapy_settings_path = os.path.join(
            os.path.dirname(__file__),
            'scrapy_settings.py'
        )

        cmd = [
            'scrapy',
            'crawl',
            'doc_spider',
            '-a', f'job_id={job_id}',
            '-a', f'start_url={target_url}',
            '-a', f'max_depth={max_depth}',
            '-a', f'use_playwright={use_playwright}',
            '-a', f'capture_html={capture_html}',
            '-a', f'screenshots={screenshots}',
        ]
        
        # Add crawl config if provided
        if crawl_config_id:
            cmd.extend(['-a', f'crawl_config_id={crawl_config_id}'])

        if allowed_domains:
            cmd.extend(['-a', f'allowed_domains={allowed_domains}'])

        # Add settings module
        cmd.extend(['--set', f'SETTINGS_MODULE=crawler.scrapy_settings'])
        
        # Set page limit if specified
        if max_pages:
            cmd.extend(['-s', f'CLOSESPIDER_PAGECOUNT={max_pages}'])

        # Set environment variables
        env = os.environ.copy()
        env['SCRAPY_SETTINGS_MODULE'] = 'crawler.scrapy_settings'
        # Add project root to PYTHONPATH so Scrapy can find the crawler module
        env['PYTHONPATH'] = str(settings.BASE_DIR)

        logger.info(f"Running command: {' '.join(cmd)}")

        # Run Scrapy as subprocess
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            cwd=settings.BASE_DIR
        )

        # Log output
        if result.stdout:
            logger.info(f"Scrapy stdout:\n{result.stdout}")
        if result.stderr:
            logger.warning(f"Scrapy stderr:\n{result.stderr}")

        # Refresh job from database
        job.refresh_from_db()

        if result.returncode != 0:
            error_msg = f"Scrapy exited with code {result.returncode}"
            if result.stderr:
                error_msg += f"\n{result.stderr}"
            logger.error(error_msg)
            job.mark_failed(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'stats': job.stats
            }

        # If job wasn't marked as completed by pipeline, mark it now
        if job.status == 'running':
            job.mark_completed()

        logger.info(f"Crawl completed for job {job_id}")

        # Send webhook notification if configured
        if job.client.webhook_url:
            send_webhook_notification.delay(job.id, 'completed')

        return {
            'success': True,
            'stats': job.stats,
            'pages_crawled': job.stats.get('pages_crawled', 0)
        }

    except CrawlJob.DoesNotExist:
        error_msg = f"Job {job_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}

    except Exception as e:
        error_msg = f"Error in crawl task: {str(e)}"
        logger.exception(error_msg)

        # Try to mark job as failed
        try:
            job = CrawlJob.objects.get(id=job_id)
            job.mark_failed(error_msg)
        except:
            pass

        return {'success': False, 'error': error_msg}


@shared_task
def send_webhook_notification(job_id, event_type):
    """
    Send a webhook notification for a job event.

    Args:
        job_id: The ID of the CrawlJob
        event_type: Type of event (started, completed, failed, progress)
    """
    import requests
    from core.models import CrawlJob

    try:
        job = CrawlJob.objects.get(id=job_id)

        if not job.client.webhook_url:
            logger.debug(f"No webhook URL configured for job {job_id}")
            return

        payload = {
            'event': event_type,
            'job_id': job.id,
            'client_id': job.client.id,
            'target_url': job.target_url,
            'status': job.status,
            'stats': job.stats,
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        }

        response = requests.post(
            job.client.webhook_url,
            json=payload,
            timeout=settings.WEBHOOK_TIMEOUT
        )

        if response.status_code == 200:
            logger.info(f"Webhook notification sent for job {job_id}: {event_type}")
        else:
            logger.warning(f"Webhook returned status {response.status_code} for job {job_id}")

    except CrawlJob.DoesNotExist:
        logger.error(f"Job {job_id} not found for webhook")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending webhook for job {job_id}: {str(e)}")
    except Exception as e:
        logger.exception(f"Unexpected error sending webhook for job {job_id}")


@shared_task
def resume_crawl_task(job_id):
    """
    Resume a paused or failed crawl.

    Args:
        job_id: The ID of the CrawlJob to resume
    """
    from core.models import CrawlJob

    try:
        job = CrawlJob.objects.get(id=job_id)

        if job.status not in ['paused', 'failed']:
            logger.warning(f"Cannot resume job {job_id} with status {job.status}")
            return {'success': False, 'error': 'Job cannot be resumed'}

        # Reset status
        job.status = 'pending'
        job.save(update_fields=['status'])

        # Start the crawl
        return start_crawl_task(job_id)

    except CrawlJob.DoesNotExist:
        return {'success': False, 'error': f'Job {job_id} not found'}


@shared_task
def cleanup_old_crawls(days=30):
    """
    Clean up old completed crawls and their associated data.

    Args:
        days: Delete crawls older than this many days
    """
    from django.utils import timezone
    from datetime import timedelta
    from core.models import CrawlJob

    cutoff_date = timezone.now() - timedelta(days=days)

    old_jobs = CrawlJob.objects.filter(
        status='completed',
        completed_at__lt=cutoff_date
    )

    count = old_jobs.count()
    logger.info(f"Cleaning up {count} crawls older than {days} days")

    old_jobs.delete()

    return {'deleted': count}


@shared_task
def capture_page_screenshot_task(page_id):
    """
    Capture a screenshot for a single page on-demand.
    
    Args:
        page_id: The ID of the CrawledPage to screenshot
        
    Returns:
        dict: Success status and screenshot path
    """
    from crawler.models import CrawledPage
    from playwright.sync_api import sync_playwright
    from urllib.parse import urlparse
    import os
    from django.conf import settings
    import django
    
    # Ensure Django is set up for sync operations
    django.setup()
    
    logger.info(f"Starting screenshot capture for page {page_id}")
    
    try:
        page = CrawledPage.objects.get(id=page_id)
        page_url = page.url  # Store URL before entering Playwright context
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            pw_page = context.new_page()
            
            # Navigate to the page
            logger.info(f"Navigating to {page_url}")
            pw_page.goto(page_url, wait_until='networkidle', timeout=30000)
            
            # Parse URL to create hierarchical directory structure
            parsed_url = urlparse(page_url)
            domain = parsed_url.netloc.replace('www.', '')
            url_path = parsed_url.path.strip('/')
            
            # Build directory structure
            if url_path:
                screenshot_dir = os.path.join(settings.BASE_DIR, 'screenshots', domain, url_path)
            else:
                screenshot_dir = os.path.join(settings.BASE_DIR, 'screenshots', domain)
            
            os.makedirs(screenshot_dir, exist_ok=True)
            
            # Save screenshot
            filename = 'screenshot.png'
            filepath = os.path.join(screenshot_dir, filename)
            pw_page.screenshot(path=filepath, full_page=True)
            
            # Calculate relative path
            if url_path:
                relative_path = os.path.join('screenshots', domain, url_path, filename)
            else:
                relative_path = os.path.join('screenshots', domain, filename)
            
            browser.close()
        
        # Update database AFTER exiting Playwright context
        page.screenshot_path = relative_path
        page.save(update_fields=['screenshot_path'])
        
        logger.info(f"Screenshot captured successfully: {relative_path}")
        
        return {
            'success': True,
            'screenshot_path': relative_path,
            'page_id': page_id
        }
            
    except CrawledPage.DoesNotExist:
        error_msg = f"Page {page_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}
    
    except Exception as e:
        error_msg = f"Error capturing screenshot for page {page_id}: {str(e)}"
        logger.exception(error_msg)
        return {'success': False, 'error': error_msg}


@shared_task(bind=True, time_limit=300, max_retries=3, default_retry_delay=60)
def generate_page_embeddings_task(self, page_id, force=False):
    """
    Generate OpenAI embeddings for a single crawled page.

    Uses the OpenAI text-embedding-3-small model to compute:
    - A full-page embedding (stored in `page.page_embedding`)
    - One embedding per section (stored in `page.section_embeddings`)
    
    Retries up to 3 times on transient failures (rate limits, network errors).
    """
    from decouple import config
    from crawler.models import CrawledPage
    from openai import OpenAI, RateLimitError, APIError, APIConnectionError

    api_key = config("OPENAI_API_KEY", default=None) or config("OPENAI_KEY", default=None)
    if not api_key:
        logger.error(f"[Embeddings] Page {page_id}: OPENAI_API_KEY not set")
        return {"success": False, "error": "OPENAI_API_KEY not configured"}

    try:
        page = CrawledPage.objects.get(id=page_id)
    except CrawledPage.DoesNotExist:
        logger.error(f"[Embeddings] Page {page_id} not found in database")
        return {"success": False, "error": f"Page {page_id} not found"}

    if not page.main_content:
        logger.info(f"[Embeddings] Page {page_id} ({page.url}): No main_content; skipping")
        return {"success": False, "error": "Page has no main_content"}

    if not force and page.page_embedding:
        logger.info(f"[Embeddings] Page {page_id} ({page.url}): Already has embeddings; skipping")
        return {"success": True, "skipped": True}

    client = OpenAI(api_key=api_key)
    EMBEDDING_MODEL = "text-embedding-3-small"

    # Build input texts: first the full page, then each section
    inputs = []
    index_map = []

    full_text = (page.main_content or "").strip()
    if full_text:
        inputs.append(full_text)
        index_map.append(("page", None))

    sections = page.sections or []
    for idx, section in enumerate(sections):
        content = (section.get("content") or "").strip()
        if not content:
            continue
        heading = (section.get("heading") or "").strip()
        text = f"{heading}\n\n{content}" if heading else content
        inputs.append(text)
        index_map.append(("section", idx))

    if not inputs:
        logger.warning(f"[Embeddings] Page {page_id} ({page.url}): No text content to embed")
        return {"success": False, "error": "No text content to embed"}

    logger.info(
        f"[Embeddings] Page {page_id} ({page.url}): Generating {len(inputs)} embeddings using {EMBEDDING_MODEL}"
    )

    try:
        # Call OpenAI API with error handling
        resp = client.embeddings.create(model=EMBEDDING_MODEL, input=inputs)
        vectors = [d.embedding for d in resp.data]
        
    except RateLimitError as e:
        logger.warning(
            f"[Embeddings] Page {page_id}: Rate limit hit, retrying in 60s (attempt {self.request.retries + 1}/3)"
        )
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        
    except (APIConnectionError, APIError) as e:
        logger.warning(
            f"[Embeddings] Page {page_id}: API error ({type(e).__name__}), retrying (attempt {self.request.retries + 1}/3)"
        )
        # Retry transient API errors
        raise self.retry(exc=e, countdown=30 * (2 ** self.request.retries))
        
    except Exception as e:
        # Non-retryable error (e.g., invalid input)
        logger.error(
            f"[Embeddings] Page {page_id} ({page.url}): Failed with {type(e).__name__}: {str(e)}"
        )
        return {"success": False, "error": f"{type(e).__name__}: {str(e)}"}

    # Process embeddings
    page_embedding = []
    section_embeddings = []

    for (kind, idx), vec in zip(index_map, vectors):
        if kind == "page":
            page_embedding = vec
        else:
            section = (page.sections or [])[idx]
            section_embeddings.append(
                {
                    "index": idx,
                    "heading": section.get("heading"),
                    "level": section.get("level"),
                    "word_count": section.get("word_count"),
                    "has_code": section.get("has_code"),
                    "has_list": section.get("has_list"),
                    "content": section.get("content"),
                    "embedding_model": EMBEDDING_MODEL,
                    "embedding": vec,
                }
            )

    # Generate learning objective embeddings if page has AI-extracted LOs
    learning_objective_embeddings = []
    if page.ai_learning_objectives:
        lo_inputs = []
        for lo in page.ai_learning_objectives:
            objective = lo.get("objective", "")
            bloom_level = lo.get("bloom_level", "")
            bloom_verb = lo.get("bloom_verb", "")
            difficulty = lo.get("difficulty", "")
            
            # Create rich text for embedding
            parts = [f"Context: {page.title}"]
            parts.append(f"Objective: {objective}")
            if bloom_verb:
                parts.append(f"Action: {bloom_verb}")
            if bloom_level:
                parts.append(f"Level: {bloom_level}")
            if difficulty:
                parts.append(f"Difficulty: {difficulty}")
            
            lo_inputs.append(" | ".join(parts))
        
        if lo_inputs:
            try:
                logger.info(f"[Embeddings] Page {page_id}: Generating {len(lo_inputs)} learning objective embeddings")
                lo_resp = client.embeddings.create(model=EMBEDDING_MODEL, input=lo_inputs)
                lo_vectors = [d.embedding for d in lo_resp.data]
                
                for lo, vec in zip(page.ai_learning_objectives, lo_vectors):
                    learning_objective_embeddings.append({
                        "objective": lo.get("objective", ""),
                        "bloom_level": lo.get("bloom_level", ""),
                        "bloom_verb": lo.get("bloom_verb", ""),
                        "difficulty": lo.get("difficulty", ""),
                        "estimated_time_minutes": lo.get("estimated_time_minutes"),
                        "measurable": lo.get("measurable"),
                        "embedding_model": EMBEDDING_MODEL,
                        "embedding": vec,
                    })
            except Exception as e:
                logger.warning(f"[Embeddings] Page {page_id}: Failed to generate LO embeddings: {e}")
                # Continue without LO embeddings - not critical
    
    # Save to database
    try:
        page.page_embedding = page_embedding
        page.section_embeddings = section_embeddings
        page.learning_objective_embeddings = learning_objective_embeddings
        page.save(update_fields=[
            "page_embedding", 
            "section_embeddings",
            "learning_objective_embeddings"
        ])
        
        logger.info(
            f"[Embeddings] Page {page_id} ({page.url}): ✓ Saved {len(section_embeddings)} section + "
            f"{len(learning_objective_embeddings)} LO embeddings (+ full-page)"
        )
        return {
            "success": True, 
            "sections": len(section_embeddings),
            "learning_objectives": len(learning_objective_embeddings),
            "page_id": page_id
        }
        
    except Exception as e:
        logger.error(
            f"[Embeddings] Page {page_id}: Failed to save to database: {str(e)}"
        )
        return {"success": False, "error": f"Database error: {str(e)}"}
