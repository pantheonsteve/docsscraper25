# Docsscraper Deduplication Implementation

## What Was Changed

I've implemented client-level page deduplication to prevent duplicate pages across multiple crawl jobs. Here's a summary of all changes:

### 1. Model Changes (`crawler/models.py`)
- **Added** `client` field to `CrawledPage` model
- **Changed** unique constraint from `['job', 'url']` to `['client', 'url']`
- **Added** index on `['client', 'crawled_at']` for efficient queries

### 2. Pipeline Changes (`crawler/pipelines/django_pipeline.py`)
- **Changed** from `create()` to `update_or_create()` for page saving
- **Uses** `client + url` as unique key (instead of `job + url`)
- **Updates** existing pages with latest crawl data automatically
- **Tracks** which job last updated each page

### 3. Database Migrations
Created three migrations in sequence:
- `0004_add_client_to_crawledpage.py` - Adds nullable client field
- `0005_populate_client_field.py` - Populates client from job
- `0006_make_client_non_nullable.py` - Makes client required and adds unique constraint

### 4. Deduplication Tools
- **Management command**: `crawler/management/commands/deduplicate_pages.py`
- **Standalone script**: `deduplicate_pages_standalone.py` (project root)

---

## How It Works

### Before
```
Job 1: Page(url='docs.com/api', job=1)
Job 2: Page(url='docs.com/api', job=2)
Job 3: Page(url='docs.com/api', job=3)
→ 3 copies of the same page! ❌
```

### After
```
Job 1: Page(url='docs.com/api', job=1, client=X)
Job 2: Page(url='docs.com/api', job=2, client=X)  ← Updates existing
Job 3: Page(url='docs.com/api', job=3, client=X)  ← Updates existing
→ 1 page, always up-to-date! ✅
```

---

## Installation Steps

### Step 1: Backup Your Database (CRITICAL!)
```bash
# PostgreSQL
pg_dump -U postgres docsscraper > backup_$(date +%Y%m%d).sql

# Or Django
python manage.py dumpdata crawler.crawledpage > pages_backup.json
```

### Step 2: Run Migrations
```bash
python manage.py migrate
```

This will:
1. Add the client field (nullable)
2. Populate client from job for all existing pages
3. Make client field required
4. Add the unique constraint on client + url

**Expected output:**
```
Running migrations:
  Applying crawler.0004_add_client_to_crawledpage... OK
  Applying crawler.0005_populate_client_field... OK
    Populated 1000 pages...
    Populated 2000 pages...
    Finished: Populated client field for 2847 pages
  Applying crawler.0006_make_client_non_nullable... OK
```

### Step 3: Clean Up Existing Duplicates

**Option A: Using Django Management Command**
```bash
# Preview what will be deleted (recommended first step)
python manage.py deduplicate_pages --client-slug=pantheon --dry-run

# Actually delete duplicates
python manage.py deduplicate_pages --client-slug=pantheon

# Or all clients at once
python manage.py deduplicate_pages --all-clients
```

**Option B: Using Standalone Script**
```bash
# Preview
python deduplicate_pages_standalone.py --client-slug=pantheon --dry-run

# Delete
python deduplicate_pages_standalone.py --client-slug=pantheon

# All clients
python deduplicate_pages_standalone.py --all
```

---

## Usage Examples

### Check for Duplicates
```python
from crawler.models import CrawledPage
from django.db.models import Count

# Find duplicate URLs for a client
duplicates = (
    CrawledPage.objects
    .filter(job__client__slug='pantheon')
    .values('url')
    .annotate(count=Count('id'))
    .filter(count__gt=1)
)

print(f"Found {len(duplicates)} duplicate URLs")
for dup in duplicates[:5]:
    print(f"  {dup['url']}: {dup['count']} copies")
```

### Query Pages
```python
# Get all pages for a client (no duplicates after deduplication!)
pages = CrawledPage.objects.filter(client=client)

# Get pages last updated by a specific job
pages = CrawledPage.objects.filter(client=client, job=job)

# Count total unique pages per client
from django.db.models import Count
Client.objects.annotate(
    total_pages=Count('pages')
).values('name', 'total_pages')
```

### Run a New Crawl
When you run a new crawl now:
- New URLs will be **created**
- Existing URLs will be **updated** with latest content
- The `job` field will point to the most recent job
- No duplicates will be created!

---

## Verification Steps

### 1. Check Migration Status
```bash
python manage.py showmigrations crawler
```

Expected output should show:
```
crawler
  [X] 0001_initial
  [X] 0002_pagerelationship_alter_crawledpage_options_and_more
  [X] 0003_crawledpage_alt_text_quality_score_and_more
  [X] 0004_add_client_to_crawledpage
  [X] 0005_populate_client_field
  [X] 0006_make_client_non_nullable
```

### 2. Verify No Duplicates Remain
```bash
python manage.py deduplicate_pages --all-clients --dry-run
```

Should show "No duplicates found" for all clients.

### 3. Test a New Crawl
Run a test crawl and verify:
- Existing pages are updated (check logs for "Updated existing page")
- New pages are created (check logs for "Created new page")
- No duplicate constraint errors

---

## Expected Results

### Database Size Reduction
If you had 3-4 copies of each page:
- **Before**: 2,847 pages (1,824 duplicates)
- **After**: 1,023 pages (0 duplicates)
- **Space saved**: ~64%

### Query Performance
- Faster queries (smaller tables)
- Simpler queries (no need to filter by latest job)
- Better indexing on client + crawled_at

---

## Rollback Plan

If something goes wrong:

### Option 1: Restore from Backup
```bash
psql -U postgres docsscraper < backup_20241118.sql
```

### Option 2: Reverse Migrations
```bash
python manage.py migrate crawler 0003
```

Then revert code changes in:
- `crawler/models.py` (remove client field, restore unique_together)
- `crawler/pipelines/django_pipeline.py` (restore old logic)

---

## Troubleshooting

### Migration Errors

**Error**: `column "client_id" does not exist`
- You may have skipped migration 0004. Run: `python manage.py migrate crawler 0004`

**Error**: `duplicate key value violates unique constraint`
- Run deduplication BEFORE migration 0006:
  ```bash
  python manage.py migrate crawler 0005
  python manage.py deduplicate_pages --all-clients
  python manage.py migrate crawler 0006
  ```

### Deduplication Issues

**No duplicates found but I know they exist**
- Check you're using the correct client slug
- Try: `python manage.py deduplicate_pages --all-clients --dry-run`

**Script hangs or is very slow**
- Normal for large datasets. It processes in batches.
- Check database CPU/memory usage

---

## What's Next?

### Future Enhancements

1. **Automatic cleanup of old jobs**
   - After deduplication, you might not need jobs older than X days
   - Could add a management command to archive/delete old jobs

2. **Page history tracking**
   - Add a `PageVersion` model if you want full change history
   - Store previous versions before updating

3. **Stale page detection**
   - Add `last_seen_at` field
   - Mark pages that haven't been crawled in recent jobs

4. **Monitoring**
   - Add alerts if duplicate count ever exceeds 0
   - Track page update frequency

---

## Support

If you encounter any issues:

1. Check the migrations ran successfully: `python manage.py showmigrations`
2. Review logs during crawl for any errors
3. Run deduplication in dry-run mode first
4. Keep database backups before making changes

---

## Summary

✅ Model updated with client field
✅ Pipeline updated to use update_or_create
✅ Three migrations created and ready to run
✅ Deduplication tools provided
✅ Documentation complete

**Next step**: Backup database, then run `python manage.py migrate`
