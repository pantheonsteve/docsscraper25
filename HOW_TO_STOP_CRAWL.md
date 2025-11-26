# How to Stop/Cancel a Crawl

## Quick Reference

### Option 1: Using Management Command
```bash
# Cancel a running crawl
python manage.py cancel_crawl --job=5

# Force cancel (even if already stopped)
python manage.py cancel_crawl --job=5 --force
```

### Option 2: Using Standalone Script
```bash
# List all jobs
python manage_crawls.py list

# List only running jobs
python manage_crawls.py list --status=running

# Cancel a specific job
python manage_crawls.py cancel --job=5

# Force cancel
python manage_crawls.py cancel --job=5 --force
```

### Option 3: Quick Manual Stop
```bash
# If running synchronously, just press Ctrl+C in the terminal
# The job status will remain 'running' until manually updated

# Update status manually via Django shell
python manage.py shell
>>> from core.models import CrawlJob
>>> job = CrawlJob.objects.get(id=5)
>>> job.status = 'cancelled'
>>> job.save()
```

---

## Detailed Guide

### Finding Your Job ID

**Method 1: Check crawl status**
```bash
python manage.py crawl_status --job=5
```

**Method 2: List all jobs**
```bash
python manage_crawls.py list
```

Output will show:
```
======================================================================================================
ID     Status       Client               URL                                      Pages   
======================================================================================================
5      RUNNING      Datadog              https://docs.datadog.com                 142     
4      COMPLETED    Pantheon             https://docs.pantheon.io                 523     
3      FAILED       Test                 https://example.com                      0       
======================================================================================================
```

**Method 3: Django Admin**
- Go to http://localhost:8000/admin/
- Navigate to Core > Crawl jobs
- Find your job and note the ID

---

## What Happens When You Cancel?

1. **Job status** is updated to `'cancelled'`
2. **Celery task** is revoked (if running async)
3. **Crawler process** receives termination signal
4. **Partial data** is preserved (pages already crawled remain in database)
5. **Job remains viewable** in history with 'cancelled' status

### Data Preservation
- ✅ All pages crawled **before** cancellation are saved
- ✅ Statistics show partial progress
- ✅ You can view the incomplete data
- ❌ The crawl won't resume automatically

---

## Stopping Different Types of Crawls

### Synchronous Crawl (No --async flag)
```bash
# Running command:
python manage.py crawl --url=https://docs.example.com

# To stop: Press Ctrl+C in the terminal
# Then update status manually:
python manage.py cancel_crawl --job=5 --force
```

### Async Crawl (With --async flag)
```bash
# Running command:
python manage.py crawl --url=https://docs.example.com --async

# To stop: Use cancel command
python manage.py cancel_crawl --job=5
```

**Note**: Async crawls run in a Celery worker, so they'll keep running even if you close the terminal that started them.

---

## Troubleshooting

### "Job is already completed/failed/cancelled"
If you see this message but the crawler is still running:
```bash
# Use --force to update anyway
python manage.py cancel_crawl --job=5 --force
```

### Crawler Won't Stop
If the crawler keeps running after cancellation:

1. **Check Celery workers**:
```bash
# Find running Celery workers
ps aux | grep celery

# Kill them if necessary
pkill -f celery
```

2. **Check for zombie processes**:
```bash
# Find Python processes running scrapy
ps aux | grep scrapy

# Kill specific process
kill <PID>
```

3. **Nuclear option** (stops all crawls):
```bash
# Stop all Celery workers
pkill -9 -f celery

# Then restart Celery
celery -A config worker -l info -Q crawling,analysis
```

### Job Stuck in 'running' State
If a job shows 'running' but isn't actually crawling:
```bash
# Force update to cancelled
python manage.py cancel_crawl --job=5 --force
```

---

## Resuming After Cancellation

Currently, there's no automatic resume feature. To recrawl:

1. **Start a new crawl** with the same URL:
```bash
python manage.py crawl \
  --url=https://docs.example.com \
  --client="ClientName" \
  --async
```

2. **Check for duplicates** after crawl completes:
```bash
python manage.py deduplicate_pages --client-slug=clientname
```

The new crawl will update existing pages and add new ones.

---

## Best Practices

### Before Cancelling
1. ✅ Note the job ID
2. ✅ Check how many pages have been crawled
3. ✅ Consider if you're close to completion

### After Cancelling
1. ✅ Verify the crawler has actually stopped
2. ✅ Check the database for partial data
3. ✅ Update any external systems that track the crawl

### Monitoring
```bash
# Watch job progress in real-time
watch -n 5 'python manage.py crawl_status --job=5'

# Or with the standalone script
watch -n 5 'python manage_crawls.py list --status=running'
```

---

## Examples

### Cancel a specific running job
```bash
# First, find the job
python manage_crawls.py list --status=running

# Output shows:
# 5      RUNNING      Datadog              https://docs.datadog.com

# Cancel it
python manage.py cancel_crawl --job=5
```

### Cancel all running jobs
```bash
# Get all running job IDs
python manage.py shell -c "
from core.models import CrawlJob
for job in CrawlJob.objects.filter(status='running'):
    print(f'Cancelling job {job.id}...')
    job.status = 'cancelled'
    job.save()
print('Done')
"
```

### Emergency stop everything
```bash
# Stop all Celery tasks
pkill -9 -f celery

# Update all running jobs to cancelled
python manage.py shell -c "
from core.models import CrawlJob
CrawlJob.objects.filter(status='running').update(status='cancelled')
"

# Restart Celery
celery -A config worker -l info -Q crawling,analysis
```

---

## API Endpoints (Future)

If you're using the API, cancellation can also be done via:
```bash
curl -X POST http://localhost:8000/api/crawler/cancel/5/
```

*(This endpoint may need to be added to the API if it doesn't exist yet)*

---

## Summary

**Quick commands you'll use most:**
```bash
# List jobs
python manage_crawls.py list

# Cancel a job
python manage.py cancel_crawl --job=5

# Check status
python manage.py crawl_status --job=5
```

**Remember:**
- Cancelled crawls preserve partial data
- Use `--force` if the job status is stuck
- Async crawls need Celery workers to be running
- Always verify the crawler has actually stopped
