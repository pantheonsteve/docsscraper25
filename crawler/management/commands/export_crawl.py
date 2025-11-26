"""
Management command to export crawl data.
"""

from django.core.management.base import BaseCommand, CommandError
from core.models import CrawlJob
from crawler.models import CrawledPage
import json
import csv
import sys


class Command(BaseCommand):
    help = 'Export crawl data to JSON or CSV'

    def add_arguments(self, parser):
        parser.add_argument(
            '--job',
            type=int,
            required=True,
            help='Job ID to export'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'csv'],
            default='json',
            help='Export format (json or csv)'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path (default: stdout)'
        )
        parser.add_argument(
            '--include-html',
            action='store_true',
            help='Include raw HTML in export'
        )

    def handle(self, *args, **options):
        job_id = options['job']
        format_type = options['format']
        output_file = options.get('output')
        include_html = options['include_html']

        try:
            job = CrawlJob.objects.get(id=job_id)
        except CrawlJob.DoesNotExist:
            raise CommandError(f'Job {job_id} not found')

        # Get all pages for this job
        pages = CrawledPage.objects.filter(job=job).order_by('depth', 'url')

        if not pages.exists():
            self.stdout.write(self.style.WARNING('No pages found for this job'))
            return

        self.stdout.write(f'Exporting {pages.count()} pages from job #{job_id}...')

        # Prepare output
        if output_file:
            output = open(output_file, 'w', encoding='utf-8')
        else:
            output = sys.stdout

        try:
            if format_type == 'json':
                self.export_json(job, pages, output, include_html)
            else:
                self.export_csv(job, pages, output, include_html)

            if output_file:
                self.stdout.write(
                    self.style.SUCCESS(f'Export completed: {output_file}')
                )
        finally:
            if output_file:
                output.close()

    def export_json(self, job, pages, output, include_html):
        """Export data as JSON."""
        data = {
            'job': {
                'id': job.id,
                'client': job.client.name,
                'target_url': job.target_url,
                'status': job.status,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'stats': job.stats,
            },
            'pages': []
        }

        for page in pages:
            page_data = {
                'url': page.url,
                'depth': page.depth,
                'title': page.title,
                'main_content': page.main_content,
                'meta_description': page.meta_description,
                'headers': page.headers,
                'code_blocks': page.code_blocks,
                'internal_links': page.internal_links,
                'external_links': page.external_links,
                'status_code': page.status_code,
                'response_time': page.response_time,
                'page_size': page.page_size,
                'crawled_at': page.crawled_at.isoformat(),
                'is_duplicate': page.is_duplicate,
            }

            if include_html and page.raw_html:
                page_data['raw_html'] = page.raw_html

            data['pages'].append(page_data)

        json.dump(data, output, indent=2, ensure_ascii=False)

    def export_csv(self, job, pages, output, include_html):
        """Export data as CSV."""
        fieldnames = [
            'url', 'depth', 'title', 'meta_description', 'status_code',
            'response_time', 'page_size', 'word_count', 'code_blocks_count',
            'internal_links_count', 'external_links_count', 'crawled_at',
            'is_duplicate'
        ]

        if include_html:
            fieldnames.append('raw_html')

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for page in pages:
            row = {
                'url': page.url,
                'depth': page.depth,
                'title': page.title,
                'meta_description': page.meta_description,
                'status_code': page.status_code,
                'response_time': page.response_time,
                'page_size': page.page_size,
                'word_count': page.get_word_count(),
                'code_blocks_count': page.get_code_block_count(),
                'internal_links_count': page.get_internal_link_count(),
                'external_links_count': page.get_external_link_count(),
                'crawled_at': page.crawled_at.isoformat(),
                'is_duplicate': page.is_duplicate,
            }

            if include_html:
                row['raw_html'] = page.raw_html or ''

            writer.writerow(row)
