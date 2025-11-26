"""
Management command to check crawl job status.
"""

from django.core.management.base import BaseCommand, CommandError
from core.models import CrawlJob
import json


class Command(BaseCommand):
    help = 'Check the status of a crawl job'

    def add_arguments(self, parser):
        parser.add_argument(
            '--job',
            type=int,
            required=True,
            help='Job ID to check'
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output as JSON'
        )

    def handle(self, *args, **options):
        job_id = options['job']
        json_output = options['json']

        try:
            job = CrawlJob.objects.get(id=job_id)
        except CrawlJob.DoesNotExist:
            raise CommandError(f'Job {job_id} not found')

        if json_output:
            # Output as JSON
            data = {
                'id': job.id,
                'client': job.client.name,
                'target_url': job.target_url,
                'status': job.status,
                'created_at': job.created_at.isoformat() if job.created_at else None,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'duration': job.get_duration(),
                'stats': job.stats,
                'progress_percentage': job.progress_percentage,
                'error_message': job.error_message,
            }
            self.stdout.write(json.dumps(data, indent=2))
        else:
            # Human-readable output
            self.stdout.write(self.style.SUCCESS(f'\n=== Crawl Job #{job.id} ==='))
            self.stdout.write(f'Client: {job.client.name}')
            self.stdout.write(f'Target URL: {job.target_url}')
            self.stdout.write(f'Status: {self.colorize_status(job.status)}')

            if job.started_at:
                self.stdout.write(f'Started: {job.started_at}')

            if job.completed_at:
                self.stdout.write(f'Completed: {job.completed_at}')

            duration = job.get_duration()
            if duration:
                hours = int(duration // 3600)
                minutes = int((duration % 3600) // 60)
                seconds = int(duration % 60)
                self.stdout.write(f'Duration: {hours}h {minutes}m {seconds}s')

            if job.stats:
                self.stdout.write('\n--- Statistics ---')
                for key, value in job.stats.items():
                    self.stdout.write(f'{key}: {value}')

            if job.status in ['running', 'pending']:
                self.stdout.write(f'\nProgress: {job.progress_percentage}%')

            if job.error_message:
                self.stdout.write(self.style.ERROR(f'\nError: {job.error_message}'))

    def colorize_status(self, status):
        """Return colorized status string."""
        colors = {
            'pending': self.style.WARNING,
            'running': self.style.HTTP_INFO,
            'paused': self.style.WARNING,
            'completed': self.style.SUCCESS,
            'failed': self.style.ERROR,
            'cancelled': self.style.ERROR,
        }
        color_func = colors.get(status, lambda x: x)
        return color_func(status.upper())
