"""
Django management command to deduplicate crawled pages for a client.

Usage:
    python manage.py deduplicate_pages --client-slug=<slug>
    python manage.py deduplicate_pages --client-slug=<slug> --dry-run
    python manage.py deduplicate_pages --all-clients
"""

from django.core.management.base import BaseCommand
from django.db.models import Count
from core.models import Client
from crawler.models import CrawledPage


class Command(BaseCommand):
    help = 'Deduplicate crawled pages for a client, keeping the most recent version'

    def add_arguments(self, parser):
        parser.add_argument(
            '--client-slug',
            type=str,
            help='Slug of the client to deduplicate pages for'
        )
        parser.add_argument(
            '--all-clients',
            action='store_true',
            help='Deduplicate pages for all clients'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        client_slug = options.get('client_slug')
        all_clients = options.get('all_clients')
        dry_run = options.get('dry_run')

        if not client_slug and not all_clients:
            self.stdout.write(self.style.ERROR('Error: You must specify either --client-slug or --all-clients'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))

        # Get clients to process
        if all_clients:
            clients = Client.objects.filter(is_active=True)
        else:
            try:
                clients = [Client.objects.get(slug=client_slug)]
            except Client.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Error: Client with slug "{client_slug}" not found'))
                return

        total_deleted = 0
        total_kept = 0

        for client in clients:
            self.stdout.write(f'\n{"="*60}')
            self.stdout.write(f'Processing client: {client.name} (ID: {client.id})')
            self.stdout.write(f'{"="*60}\n')

            # Find URLs with duplicates
            duplicate_urls = (
                CrawledPage.objects
                .filter(job__client=client)
                .values('url')
                .annotate(count=Count('id'))
                .filter(count__gt=1)
                .order_by('-count')
            )

            if not duplicate_urls:
                self.stdout.write(self.style.SUCCESS(f'✓ No duplicates found for {client.name}'))
                continue

            self.stdout.write(f'Found {len(duplicate_urls)} URLs with duplicates\n')

            client_deleted = 0
            client_kept = 0

            for dup_info in duplicate_urls:
                url = dup_info['url']
                count = dup_info['count']

                # Get all pages for this URL, ordered by most recent first
                pages = list(
                    CrawledPage.objects
                    .filter(job__client=client, url=url)
                    .order_by('-crawled_at')
                    .select_related('job')
                )

                # Keep the most recent, delete the rest
                page_to_keep = pages[0]
                pages_to_delete = pages[1:]

                self.stdout.write(f'\nURL: {url}')
                self.stdout.write(f'  Total copies: {count}')
                self.stdout.write(f'  ✓ Keeping: ID {page_to_keep.id} from Job {page_to_keep.job.id} (crawled {page_to_keep.crawled_at})')

                for page in pages_to_delete:
                    self.stdout.write(
                        f'  ✗ Deleting: ID {page.id} from Job {page.job.id} (crawled {page.crawled_at})'
                    )

                    if not dry_run:
                        page.delete()

                client_deleted += len(pages_to_delete)
                client_kept += 1

            self.stdout.write(self.style.SUCCESS(f'\n{client.name} Summary:'))
            self.stdout.write(f'  Pages kept: {client_kept}')
            self.stdout.write(f'  Pages deleted: {client_deleted}')

            total_deleted += client_deleted
            total_kept += client_kept

        # Final summary
        self.stdout.write(f'\n{"="*60}')
        self.stdout.write(self.style.SUCCESS('OVERALL SUMMARY'))
        self.stdout.write(f'{"="*60}')
        self.stdout.write(f'Total unique pages kept: {total_kept}')
        self.stdout.write(f'Total duplicate pages deleted: {total_deleted}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\nThis was a DRY RUN - no changes were made'))
            self.stdout.write('Run without --dry-run to actually delete duplicates')
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Deduplication complete!'))
