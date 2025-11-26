#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import CrawlJob

job = CrawlJob.objects.get(id=16)
print(f"Job #{job.id}: {job.target_url}")
print(f"Status: {job.status}")
print(f"Pages crawled: {job.pages.count()}")
print(f"Created: {job.created_at}")
