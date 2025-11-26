"""
Standalone script to deduplicate pages for a client.
Can be run directly from the project root.

Usage:
    python deduplicate_pages_standalone.py --client-slug=pantheon --dry-run
    python deduplicate_pages_standalone.py --client-slug=pantheon
    python deduplicate_pages_standalone.py --all
"""

import os
import sys
import django
import argparse

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db.models import Count
from core.models import Client
from crawler.models import CrawledPage


def deduplicate_client(client, dry_run=False):
    """Deduplicate pages for a single client."""
    print(f'\n{"="*70}')
    print(f'Processing: {client.name} (ID: {client.id})')
    print(f'{"="*70}\n')

    # Find URLs with multiple copies
    duplicate_urls = (
        CrawledPage.objects
        .filter(job__client=client)
        .values('url')
        .annotate(count=Count('id'))
        .filter(count__gt=1)
        .order_by('-count')
    )

    if not duplicate_urls:
        print(f'✓ No duplicates found for {client.name}')
        return 0, 0

    print(f'Found {len(duplicate_urls)} URLs with duplicates\n')

    pages_deleted = 0
    pages_kept = 0
    duplicate_details = []

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

        # Keep the most recent
        page_to_keep = pages[0]
        pages_to_delete = pages[1:]

        duplicate_details.append({
            'url': url,
            'total': count,
            'keep': page_to_keep,
            'delete': pages_to_delete
        })

        pages_kept += 1
        pages_deleted += len(pages_to_delete)

    # Display details
    for detail in duplicate_details[:10]:  # Show first 10
        print(f"\nURL: {detail['url'][:80]}{'...' if len(detail['url']) > 80 else ''}")
        print(f"  Copies found: {detail['total']}")
        print(f"  ✓ KEEP:   ID {detail['keep'].id:6} | Job {detail['keep'].job.id:6} | {detail['keep'].crawled_at}")
        
        for page in detail['delete']:
            print(f"  ✗ DELETE: ID {page.id:6} | Job {page.job.id:6} | {page.crawled_at}")

    if len(duplicate_details) > 10:
        print(f"\n... and {len(duplicate_details) - 10} more duplicate URLs")

    # Perform deletion
    if not dry_run:
        print(f"\nDeleting {pages_deleted} duplicate pages...")
        for detail in duplicate_details:
            for page in detail['delete']:
                page.delete()
        print("✓ Deletion complete")
    else:
        print(f"\n[DRY RUN] Would delete {pages_deleted} duplicate pages")

    print(f'\n{client.name} Summary:')
    print(f'  Unique pages kept: {pages_kept}')
    print(f'  Duplicates {"would be " if dry_run else ""}deleted: {pages_deleted}')

    return pages_kept, pages_deleted


def main():
    parser = argparse.ArgumentParser(description='Deduplicate crawled pages')
    parser.add_argument('--client-slug', type=str, help='Client slug to deduplicate')
    parser.add_argument('--all', action='store_true', help='Deduplicate all clients')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without deleting')
    
    args = parser.parse_args()

    if not args.client_slug and not args.all:
        print("Error: You must specify either --client-slug or --all")
        sys.exit(1)

    if args.dry_run:
        print("\n" + "="*70)
        print("DRY RUN MODE - No changes will be made")
        print("="*70)

    # Get clients
    if args.all:
        clients = Client.objects.filter(is_active=True)
        print(f"\nProcessing all {clients.count()} active clients...")
    else:
        try:
            clients = [Client.objects.get(slug=args.client_slug)]
        except Client.DoesNotExist:
            print(f'Error: Client "{args.client_slug}" not found')
            sys.exit(1)

    # Process each client
    total_kept = 0
    total_deleted = 0

    for client in clients:
        kept, deleted = deduplicate_client(client, args.dry_run)
        total_kept += kept
        total_deleted += deleted

    # Final summary
    print(f'\n{"="*70}')
    print('OVERALL SUMMARY')
    print(f'{"="*70}')
    print(f'Total unique pages: {total_kept}')
    print(f'Total duplicates {"would be " if args.dry_run else ""}removed: {total_deleted}')
    
    if args.dry_run:
        print('\n⚠️  This was a DRY RUN - no changes were made')
        print('Run without --dry-run to actually delete duplicates')
    else:
        print('\n✓ Deduplication complete!')


if __name__ == '__main__':
    main()
