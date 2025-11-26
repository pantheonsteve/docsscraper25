"""
Management command to cancel a running crawl job.
"""

from django.core.management.base import BaseCommand, CommandError
from core.models import CrawlJob
from celery.result import AsyncResult


class Command(BaseCommand):
    help = 'Cancel a running or pending crawl job'

    def add_arguments(self, parser):
        parser.add_argument(
            '--job',
            type=int,
            required=True,
            help='Job ID to cancel'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force cancel even if job is not running'
        )

    def handle(self, *args, **options):
        job_id = options['job']
        force = options['force']

        try:
            job = CrawlJob.objects.get(id=job_id)
        except CrawlJob.DoesNotExist:
            raise CommandError(f'Job {job_id} not found')

        # Check if job can be cancelled
        if job.status in ['completed', 'failed', 'cancelled'] and not force:
            self.stdout.write(
                self.style.WARNING(
                    f'Job {job_id} is already {job.status}. Use --force to override.'
                )
            )
            return

        self.stdout.write(f'Cancelling job {job_id} (status: {job.status})...')

        # Try to revoke Celery task if it exists
        if job.celery_task_id:
            try:
                result = AsyncResult(job.celery_task_id)
                result.revoke(terminate=True)
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Revoked Celery task: {job.celery_task_id}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'Could not revoke Celery task: {str(e)}')
                )

        # Update job status
        old_status = job.status
        job.status = 'cancelled'
        job.error_message = 'Cancelled by user'
        job.save(update_fields=['status', 'error_message'])

        self.stdout.write(
            self.style.SUCCESS(
                f'✓ Job {job_id} cancelled (was: {old_status})'
            )
        )

        # Show job details
        self.stdout.write('\n--- Job Details ---')
        self.stdout.write(f'Client: {job.client.name}')
        self.stdout.write(f'Target URL: {job.target_url}')
        self.stdout.write(f'Pages crawled: {job.pages_crawled}')
        self.stdout.write(f'Started at: {job.started_at or "Not started"}')

        if job.celery_task_id:
            self.stdout.write(
                '\nNote: The crawler process may take a few seconds to stop.'
            )
