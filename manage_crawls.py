"""
Standalone script to manage (list, cancel) crawl jobs.

Usage:
    python manage_crawls.py list
    python manage_crawls.py cancel --job=5
    python manage_crawls.py cancel --job=5 --force
"""

import os
import sys
import django
import argparse

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import CrawlJob
from celery.result import AsyncResult


def list_jobs(status=None):
    """List crawl jobs, optionally filtered by status."""
    jobs = CrawlJob.objects.all().select_related('client')
    
    if status:
        jobs = jobs.filter(status=status)
    
    jobs = jobs.order_by('-created_at')[:20]  # Show last 20
    
    if not jobs:
        print("No jobs found")
        return
    
    print(f"\n{'='*100}")
    print(f"{'ID':<6} {'Status':<12} {'Client':<20} {'URL':<40} {'Pages':<8}")
    print(f"{'='*100}")
    
    for job in jobs:
        url_short = job.target_url[:37] + '...' if len(job.target_url) > 40 else job.target_url
        client_short = job.client.name[:17] + '...' if len(job.client.name) > 20 else job.client.name
        
        # Color code status
        status_display = job.status.upper()
        if job.status == 'running':
            status_display = f'\033[93m{status_display}\033[0m'  # Yellow
        elif job.status == 'completed':
            status_display = f'\033[92m{status_display}\033[0m'  # Green
        elif job.status in ['failed', 'cancelled']:
            status_display = f'\033[91m{status_display}\033[0m'  # Red
        
        print(f"{job.id:<6} {status_display:<21} {client_short:<20} {url_short:<40} {job.pages_crawled:<8}")
    
    print(f"{'='*100}\n")
    
    # Show counts by status
    from django.db.models import Count
    status_counts = CrawlJob.objects.values('status').annotate(count=Count('id'))
    
    print("Status Summary:")
    for item in status_counts:
        print(f"  {item['status']}: {item['count']}")


def cancel_job(job_id, force=False):
    """Cancel a specific job."""
    try:
        job = CrawlJob.objects.get(id=job_id)
    except CrawlJob.DoesNotExist:
        print(f"❌ Error: Job {job_id} not found")
        sys.exit(1)
    
    # Check if job can be cancelled
    if job.status in ['completed', 'failed', 'cancelled'] and not force:
        print(f"⚠️  Job {job_id} is already {job.status}")
        print("   Use --force to override")
        sys.exit(1)
    
    print(f"\nCancelling job {job_id}...")
    print(f"  Status: {job.status}")
    print(f"  Client: {job.client.name}")
    print(f"  URL: {job.target_url}")
    print(f"  Pages crawled: {job.pages_crawled}")
    
    # Try to revoke Celery task
    if job.celery_task_id:
        try:
            result = AsyncResult(job.celery_task_id)
            result.revoke(terminate=True)
            print(f"  ✓ Revoked Celery task: {job.celery_task_id}")
        except Exception as e:
            print(f"  ⚠️  Could not revoke Celery task: {str(e)}")
    else:
        print("  (No Celery task to revoke)")
    
    # Update status
    job.status = 'cancelled'
    job.error_message = 'Cancelled by user'
    job.save(update_fields=['status', 'error_message'])
    
    print(f"\n✓ Job {job_id} cancelled successfully")
    print("\nNote: The crawler process may take a few seconds to stop.")


def main():
    parser = argparse.ArgumentParser(description='Manage crawl jobs')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List crawl jobs')
    list_parser.add_argument(
        '--status',
        choices=['pending', 'running', 'paused', 'completed', 'failed', 'cancelled'],
        help='Filter by status'
    )
    
    # Cancel command
    cancel_parser = subparsers.add_parser('cancel', help='Cancel a crawl job')
    cancel_parser.add_argument(
        '--job',
        type=int,
        required=True,
        help='Job ID to cancel'
    )
    cancel_parser.add_argument(
        '--force',
        action='store_true',
        help='Force cancel even if job is not running'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == 'list':
        list_jobs(args.status)
    elif args.command == 'cancel':
        cancel_job(args.job, args.force)


if __name__ == '__main__':
    main()
