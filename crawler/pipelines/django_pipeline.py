"""
Scrapy pipeline for saving crawled data to Django models.
"""

import os
import sys
import django
import logging
from twisted.internet import threads

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from crawler.models import CrawledPage, CrawlError
from core.models import CrawlJob
from crawler.language_detector import is_english
from crawler.tasks import capture_page_screenshot_task

logger = logging.getLogger('crawler')


class DjangoStoragePipeline:
    """
    Pipeline that saves crawled pages to Django database.
    Handles deduplication and error logging.
    """

    def __init__(self):
        self.seen_content_hashes = set()
        self.seen_urls = set()
        self.job = None

    def _open_spider_sync(self, spider):
        """Synchronous helper for open_spider."""
        if hasattr(spider, 'job_id') and spider.job_id:
            try:
                self.job = CrawlJob.objects.get(id=spider.job_id)
                self.job.mark_started()
                logger.info(f"Pipeline initialized for job {self.job.id}")

                # Load existing hashes for this job to avoid duplicates
                existing_hashes = CrawledPage.objects.filter(
                    job=self.job
                ).values_list('content_hash', flat=True)
                self.seen_content_hashes = set(existing_hashes)

                # Load existing URLs
                existing_urls = CrawledPage.objects.filter(
                    job=self.job
                ).values_list('url', flat=True)
                self.seen_urls = set(existing_urls)

                logger.info(f"Loaded {len(self.seen_content_hashes)} existing content hashes")
                logger.info(f"Loaded {len(self.seen_urls)} existing URLs")

            except CrawlJob.DoesNotExist:
                logger.error(f"Job {spider.job_id} not found")
                self.job = None

    def open_spider(self, spider):
        """Initialize pipeline when spider opens."""
        return threads.deferToThread(self._open_spider_sync, spider)

    def _close_spider_sync(self, spider):
        """Synchronous helper for close_spider."""
        if self.job:
            # Mark job as completed (unless it failed)
            if self.job.status == 'running':
                self.job.mark_completed()
                logger.info(f"Job {self.job.id} completed successfully with {self.job.pages_crawled} pages")

    def close_spider(self, spider):
        """Finalize pipeline when spider closes."""
        return threads.deferToThread(self._close_spider_sync, spider)

    def _process_item_sync(self, item, spider):
        """Synchronous helper for process_item."""
        if not self.job:
            logger.warning("No job associated with spider, skipping item")
            return item

        # Handle error items
        if item.get('error'):
            self._save_error_sync(item, spider)
            return item

        # Language filtering: Drop non-English pages
        detected_lang = item.get('detected_language', 'unknown')
        if not is_english(detected_lang):
            logger.info(f"Dropping non-English page ({detected_lang}): {item['url']}")
            # Raise DropItem to signal Scrapy to drop this item
            from scrapy.exceptions import DropItem
            raise DropItem(f"Non-English page ({detected_lang}): {item['url']}")

        # Generate content hash
        import hashlib
        content_hash = hashlib.sha256(item.get('main_content', '').encode()).hexdigest()

        # Check for content duplication (not URL duplication)
        is_duplicate = content_hash in self.seen_content_hashes
        if is_duplicate:
            logger.info(f"Duplicate content detected: {item['url']}")

        # Get client from job
        client = self.job.client

        # Save or update the page (client-level deduplication)
        try:
            page, created = CrawledPage.objects.update_or_create(
                client=client,
                url=item['url'],
                defaults={
                    'job': self.job,  # Update to latest job
                    'depth': item['depth'],
                    'title': item.get('title', ''),
                    'main_content': item.get('main_content', ''),
                    'raw_html': item.get('raw_html'),
                    'screenshot_path': item.get('screenshot_path'),
                    'meta_description': item.get('meta_description', ''),
                    'doc_type': item.get('doc_type', 'unknown'),
                    'version_info': item.get('version_info', ''),
                    'breadcrumb': item.get('breadcrumb', []),
                    'navigation_title': item.get('navigation_title', ''),
                    'headers': item.get('headers', {}),
                    'code_blocks': item.get('code_blocks', []),
                    'internal_links': item.get('internal_links', []),
                    'external_links': item.get('external_links', []),
                    'tables': item.get('tables', []),
                    'images': item.get('images', []),
                    'sections': item.get('sections', []),
                    'table_of_contents': item.get('table_of_contents', []),
                    'api_endpoints': item.get('api_endpoints', []),
                    'warnings': item.get('warnings', []),
                    'tips': item.get('tips', []),
                    'questions': item.get('questions', []),
                    'og_tags': item.get('og_tags', {}),
                    'schema_markup': item.get('schema_markup', {}),
                    'canonical_url': item.get('canonical_url', ''),
                    'word_count': item.get('word_count', 0),
                    'readability_score': item.get('readability_score'),
                    'estimated_reading_time': item.get('estimated_reading_time', 0),
                    'has_table_of_contents': item.get('has_table_of_contents', False),
                    'has_search': item.get('has_search', False),
                    'has_examples': item.get('has_examples', False),
                    'has_videos': item.get('has_videos', False),
                    'has_diagrams': item.get('has_diagrams', False),
                    'has_troubleshooting': item.get('has_troubleshooting', False),
                    'example_to_explanation_ratio': item.get('example_to_explanation_ratio', 0.0),
                    'content_type_diversity': item.get('content_type_diversity', 0),
                    'has_copy_buttons': item.get('has_copy_buttons', False),
                    'content_hash': content_hash,
                    'response_time': item.get('response_time', 0),
                    'page_size': item.get('page_size', 0),
                    'status_code': item.get('status_code', 200),
                    'is_duplicate': is_duplicate,
                }
            )

            # Add to seen sets
            self.seen_content_hashes.add(content_hash)
            self.seen_urls.add(item['url'])

            # Update job statistics
            # Only increment pages_crawled if this is a new URL for THIS crawl
            if created:
                self.job.pages_crawled += 1
                if not is_duplicate:
                    self.job.unique_content_pages += 1
                self.job.save(update_fields=['pages_crawled', 'unique_content_pages'])
                logger.info(f"Created new page: {page.url} (ID: {page.id})")
            else:
                # Still count it for this job's stats, but log it as an update
                self.job.pages_crawled += 1
                self.job.save(update_fields=['pages_crawled'])
                logger.info(f"Updated existing page: {page.url} (ID: {page.id})")

            # Schedule asynchronous screenshot capture via Celery if enabled
            try:
                if self.job.config.get('screenshots') and not page.screenshot_path:
                    capture_page_screenshot_task.delay(page.id)
                    logger.info(f"Enqueued screenshot task for page {page.id} ({page.url})")
            except Exception as e:
                logger.error(f"Error enqueueing screenshot task for page {page.id}: {e}", exc_info=True)

            # Schedule embeddings generation if configured
            try:
                if self.job.config.get('generate_embeddings'):
                    from crawler.tasks import generate_page_embeddings_task

                    generate_page_embeddings_task.delay(page.id)
                    logger.info(f"Enqueued embeddings task for page {page.id} ({page.url})")
            except Exception as e:
                logger.error(f"Error enqueueing embeddings task for page {page.id}: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error saving page {item['url']}: {str(e)}", exc_info=True)

        return item

    def process_item(self, item, spider):
        """Process each crawled item."""
        return threads.deferToThread(self._process_item_sync, item, spider)

    def _save_error_sync(self, item, spider):
        """Save crawl errors to the database."""
        try:
            error = CrawlError.objects.create(
                job=self.job,
                url=item['url'],
                error_type=self.classify_error(item['error_type']),
                error_message=item['error_message'],
            )
            logger.info(f"Saved error: {error.url}")

        except Exception as e:
            logger.error(f"Error saving error record: {str(e)}")

    @staticmethod
    def classify_error(error_type):
        """Classify error type into predefined categories."""
        error_type_lower = error_type.lower()

        if 'timeout' in error_type_lower:
            return 'timeout'
        elif 'http' in error_type_lower or 'status' in error_type_lower:
            return 'http_error'
        elif 'connection' in error_type_lower or 'dns' in error_type_lower:
            return 'connection_error'
        elif 'parse' in error_type_lower:
            return 'parse_error'
        else:
            return 'other'
