"""
Management command to sync doc_type field with ai_doc_type for already-analyzed pages.

This is useful after AI analysis has been run to update the main doc_type field
with the AI's better classification.
"""

from django.core.management.base import BaseCommand
from crawler.models import CrawledPage
from django.db.models import Q


class Command(BaseCommand):
    help = "Sync doc_type field with ai_doc_type for pages that have AI analysis"

    def add_arguments(self, parser):
        parser.add_argument(
            "--job-id",
            type=int,
            help="Sync only pages in a specific job",
        )
        parser.add_argument(
            "--client-id",
            type=int,
            help="Sync only pages for a specific client",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without making changes",
        )

    def handle(self, *args, **options):
        job_id = options.get("job_id")
        client_id = options.get("client_id")
        dry_run = options.get("dry_run")

        # Build queryset - pages with AI classification but not synced
        queryset = CrawledPage.objects.exclude(
            Q(ai_doc_type__isnull=True) | Q(ai_doc_type="")
        )

        if job_id:
            queryset = queryset.filter(job_id=job_id)
        if client_id:
            queryset = queryset.filter(client_id=client_id)

        total = queryset.count()

        if total == 0:
            self.stdout.write("No pages found with ai_doc_type to sync.")
            return

        # Doc type mapping (AI format -> Django model format)
        doc_type_mapping = {
            'api-reference': 'api_reference',
            'how-to': 'guide',
            'tutorial': 'tutorial',
            'reference': 'api_reference',
            'guide': 'guide',
            'concept': 'concept',
            'troubleshooting': 'troubleshooting',
            'quickstart': 'quickstart',
            'example': 'example',
            'faq': 'faq',
            'changelog': 'changelog',
        }

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN - No changes will be made")
            )
            self.stdout.write(f"\nWould sync {total} pages\n")

        update_count = 0
        no_change_count = 0

        for page in queryset:
            ai_type = page.ai_doc_type.lower() if page.ai_doc_type else None
            if not ai_type:
                continue

            mapped_type = doc_type_mapping.get(ai_type, page.doc_type)

            if mapped_type != page.doc_type:
                if not dry_run:
                    page.doc_type = mapped_type
                    page.save(update_fields=['doc_type'])
                    update_count += 1
                    self.stdout.write(
                        f"  Page {page.id}: '{page.doc_type}' -> '{mapped_type}'"
                    )
                else:
                    update_count += 1
                    self.stdout.write(
                        f"  Page {page.id}: '{page.doc_type}' -> '{mapped_type}' (would update)"
                    )
            else:
                no_change_count += 1

        self.stdout.write("\n" + "="*60)
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Would update {update_count} pages, {no_change_count} already correct"
                )
            )
            self.stdout.write(
                "\nRun without --dry-run to apply changes"
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated {update_count} pages, {no_change_count} already correct"
                )
            )

