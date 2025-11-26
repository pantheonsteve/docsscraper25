"""
Management command to start a crawl job.
"""

from django.core.management.base import BaseCommand, CommandError
from core.models import Client, CrawlJob
from crawler.tasks import start_crawl_task


class Command(BaseCommand):
    help = 'Start a documentation crawl'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            required=True,
            help='The starting URL to crawl'
        )
        parser.add_argument(
            '--client',
            type=str,
            help='Client name or ID'
        )
        parser.add_argument(
            '--depth',
            type=int,
            default=5,
            help='Maximum crawl depth (default: 5)'
        )
        parser.add_argument(
            '--domains',
            type=str,
            help='Comma-separated list of allowed domains'
        )
        parser.add_argument(
            '--async',
            action='store_true',
            dest='async_mode',
            help='Run crawl asynchronously via Celery'
        )
        parser.add_argument(
            '--playwright',
            choices=['auto', 'always', 'never'],
            default='auto',
            help='Use Playwright for JavaScript rendering: auto (detect), always (force), never (disable). Default: auto'
        )
        parser.add_argument(
            '--max-pages',
            type=int,
            help='Maximum number of pages to crawl (useful for testing)'
        )
        parser.add_argument(
            '--capture-html',
            action='store_true',
            help='Capture and store raw HTML for each page'
        )
        parser.add_argument(
            '--screenshots',
            action='store_true',
            help='Capture screenshots of each page (requires Playwright)'
        )

    def handle(self, *args, **options):
        url = options['url']
        client_name = options.get('client')
        depth = options['depth']
        domains = options.get('domains')
        async_mode = options['async_mode']
        playwright_mode = options['playwright']
        max_pages = options.get('max_pages')
        capture_html = options.get('capture_html', False)
        screenshots = options.get('screenshots', False)

        # Get or create client
        if client_name:
            try:
                if client_name.isdigit():
                    client = Client.objects.get(id=int(client_name))
                else:
                    client, created = Client.objects.get_or_create(
                        name=client_name,
                        defaults={
                            'slug': client_name.lower().replace(' ', '-'),
                            'contact_email': 'noreply@example.com'
                        }
                    )
                    if created:
                        self.stdout.write(
                            self.style.SUCCESS(f'Created new client: {client.name}')
                        )
            except Client.DoesNotExist:
                raise CommandError(f'Client "{client_name}" not found')
        else:
            # Create a default client
            client, created = Client.objects.get_or_create(
                name='Default',
                defaults={
                    'slug': 'default',
                    'contact_email': 'noreply@example.com'
                }
            )

        # Build configuration
        config = {
            'depth_limit': depth,
            'use_playwright': playwright_mode,  # 'auto', 'always', or 'never'
            'capture_html': capture_html,
            'screenshots': screenshots,
        }

        if max_pages:
            config['max_pages'] = max_pages

        if domains:
            config['allowed_domains'] = [d.strip() for d in domains.split(',')]

        # Create the crawl job
        job = CrawlJob.objects.create(
            client=client,
            target_url=url,
            config=config
        )

        self.stdout.write(
            self.style.SUCCESS(f'Created crawl job #{job.id} for {url}')
        )

        # Start the crawl
        if async_mode:
            task = start_crawl_task.delay(job.id)
            job.celery_task_id = task.id
            job.save(update_fields=['celery_task_id'])

            self.stdout.write(
                self.style.SUCCESS(
                    f'Crawl started asynchronously (Celery task: {task.id})'
                )
            )
            self.stdout.write(
                f'Monitor progress with: python manage.py crawl_status --job={job.id}'
            )
        else:
            self.stdout.write('Starting synchronous crawl (this may take a while)...')
            result = start_crawl_task(job.id)

            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Crawl completed! Crawled {result["pages_crawled"]} pages'
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'Crawl failed: {result["error"]}')
                )
