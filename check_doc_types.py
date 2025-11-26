#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import CrawlJob
from crawler.models import CrawledPage
from django.db.models import Count

job = CrawlJob.objects.get(id=16)
print(f"Job #{job.id}: {job.target_url}")
print(f"Total pages: {job.pages.count()}\n")

# Check doc_type distribution
doc_types = job.pages.values('doc_type').annotate(count=Count('id')).order_by('-count')
print("Document Type Distribution:")
for dt in doc_types:
    print(f"  {dt['doc_type']}: {dt['count']} pages")

# Show some examples of pages classified as api_reference
api_pages = job.pages.filter(doc_type='api_reference')[:10]
if api_pages:
    print("\nExample pages classified as 'api_reference':")
    for page in api_pages:
        print(f"  - {page.url}")
        print(f"    Title: {page.title}")
