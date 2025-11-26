# Screenshot Implementation Guide

## Overview

This document describes the hierarchical screenshot storage system implemented for the documentation crawler. Screenshots are stored in a directory structure that mirrors the URL path structure, with S3 migration support built in.

## Features

### 1. Hierarchical Storage Structure

Screenshots are stored following the URL path structure:
```
screenshots/
└── datadoghq/
    └── logs/
        └── observability-pipelines/
            └── screenshot.png
```

**Example URL to Path Mapping:**
- URL: `https://docs.datadoghq.com/logs/observability-pipelines`
- Path: `screenshots/datadoghq/logs/observability-pipelines/screenshot.png`

### 2. Automatic Screenshot Capture During Crawl

When starting a new crawl, you can enable screenshot capture:

1. Go to **New Crawl** page
2. Check the **"Capture Screenshots"** checkbox
3. Note: This automatically enables Playwright (required for screenshots)
4. Start the crawl

Screenshots will be captured for every page during the crawl.

### 3. On-Demand Screenshot Capture

For pages that were already crawled without screenshots, you can capture them on-demand:

1. Go to any page detail page
2. If no screenshot exists, you'll see a **"📸 Capture Screenshot"** button (orange color)
3. Click the button
4. A Celery task starts in the background
5. Refresh the page after a few seconds
6. The button will change to **"📸 View Screenshot"** once captured

### 4. Viewing Screenshots

Once captured, screenshots can be viewed in two ways:

1. **Inline View**: Click "📸 View Screenshot" button on the page detail page
2. **Direct Link**: Access via `/page/<page_id>/screenshot/` URL

## Technical Implementation

### Directory Structure

```
/Users/steve.bresnick/Projects/docsscraper/
├── crawler/
│   ├── spiders/
│   │   └── doc_spider.py          # Modified: URL-based screenshot path
│   ├── tasks.py                    # New: capture_page_screenshot_task
│   └── screenshot_storage.py       # New: Storage abstraction layer
├── dashboard/
│   ├── views.py                    # New: capture_page_screenshot view
│   ├── urls.py                     # New: capture-screenshot route
│   └── templates/dashboard/
│       └── page_detail.html        # Modified: Capture button
├── config/
│   └── settings.py                 # New: SCREENSHOT_STORAGE_* settings
└── screenshots/                    # Generated: Screenshot files
```

### Key Components

#### 1. Spider Screenshot Capture (`doc_spider.py`)

```python
def capture_screenshot(self, response):
    """Capture screenshot with URL-based directory structure"""
    parsed_url = urlparse(response.url)
    domain = parsed_url.netloc.replace('www.', '')
    url_path = parsed_url.path.strip('/')
    
    # Creates: screenshots/<domain>/<path>/screenshot.png
    screenshot_dir = os.path.join(settings.BASE_DIR, 'screenshots', domain, url_path)
    os.makedirs(screenshot_dir, exist_ok=True)
    
    filepath = os.path.join(screenshot_dir, 'screenshot.png')
    page.screenshot(path=filepath, full_page=True)
```

#### 2. On-Demand Capture Task (`tasks.py`)

```python
@shared_task
def capture_page_screenshot_task(page_id):
    """Capture screenshot for a single page using Playwright"""
    # 1. Load page from database
    # 2. Launch Playwright browser
    # 3. Navigate to URL
    # 4. Take full-page screenshot
    # 5. Save with URL-based path structure
    # 6. Update database with screenshot path
```

#### 3. Dashboard View (`views.py`)

```python
@require_POST
def capture_page_screenshot(request, page_id):
    """Trigger async screenshot capture"""
    capture_page_screenshot_task.delay(page_id)
    messages.success(request, 'Screenshot capture started...')
    return redirect('dashboard:page_detail', page_id=page_id)
```

#### 4. Storage Abstraction (`screenshot_storage.py`)

Provides a clean abstraction layer for future S3 migration:

```python
class ScreenshotStorage:
    def get_screenshot_path(self, url):
        """Generate path from URL"""
    
    def save_screenshot(self, filepath, url):
        """Save to local or S3"""
    
    def get_screenshot_url(self, screenshot_path):
        """Get access URL (local path or presigned S3 URL)"""
```

## Configuration

### Local Storage (Default)

In `config/settings.py`:
```python
SCREENSHOT_STORAGE_BACKEND = 'local'  # Default
```

### S3 Storage (Future)

To migrate to S3 storage:

1. Update `.env`:
```bash
SCREENSHOT_STORAGE_BACKEND=s3
SCREENSHOT_S3_BUCKET=your-bucket-name
SCREENSHOT_S3_PREFIX=screenshots/
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
```

2. Install boto3:
```bash
pip install boto3
```

3. Uncomment S3 implementation in `screenshot_storage.py`

4. Screenshots will automatically upload to S3 on next capture

## URL Patterns

### Screenshot Viewing
- **View**: `GET /page/<page_id>/screenshot/`
- **Purpose**: Display the screenshot image
- **Returns**: PNG image file

### Screenshot Capture
- **Capture**: `POST /page/<page_id>/capture-screenshot/`
- **Purpose**: Trigger async screenshot capture
- **Returns**: Redirect to page detail with success message

## Database Schema

The `CrawledPage` model includes:

```python
class CrawledPage(models.Model):
    # ... existing fields ...
    screenshot_path = models.CharField(
        max_length=500, 
        blank=True, 
        null=True,
        help_text="Path to the full-page screenshot"
    )
```

**Example values:**
- Local: `screenshots/datadoghq/logs/guide/screenshot.png`
- S3: `s3://my-bucket/screenshots/datadoghq/logs/guide/screenshot.png`

## Testing

### Important: Starting Celery Worker

The screenshot capture task runs in the `crawling` queue. Make sure to start Celery with all queues:

```bash
cd /Users/steve.bresnick/Projects/docsscraper
source .venv/bin/activate
celery -A config worker -l info -Q celery,crawling,analysis
```

**Note:** If you start Celery with just `celery -A config worker -l info`, it will only listen to the default `celery` queue and screenshot tasks won't run!

### Test New Crawl with Screenshots

1. Start Celery worker (see above for correct command)

2. Create a new crawl:
   - URL: `https://docs.datadoghq.com/logs/`
   - Max Pages: `5` (for testing)
   - Depth Limit: `2`
   - Enable Playwright: ✓
   - Capture Screenshots: ✓

3. Monitor the crawl in the job detail page

4. Check that screenshots appear in `screenshots/datadoghq/logs/...`

5. View page detail and verify "View Screenshot" button works

### Test On-Demand Screenshot Capture

1. Find a page without a screenshot
2. Click "📸 Capture Screenshot"
3. Wait 5-10 seconds
4. Refresh the page
5. Verify the screenshot appears

### Test Directory Structure

```bash
# Check screenshot directory structure
ls -R screenshots/

# Should show:
# screenshots/datadoghq/logs/observability-pipelines/screenshot.png
# screenshots/datadoghq/logs/guide/screenshot.png
# etc.
```

## Troubleshooting

### Screenshots Not Appearing or "Nothing Happened" When Clicking Button

**Most Common Issue:** Celery is not listening to the `crawling` queue!

1. **Check Celery is running with correct queues:**
```bash
pgrep -fl celery
celery -A config inspect active_queues
```

If you don't see `crawling` in the active queues, restart Celery with:
```bash
pkill -f "celery -A config worker"
cd /Users/steve.bresnick/Projects/docsscraper
source .venv/bin/activate
celery -A config worker -l info -Q celery,crawling,analysis
```

2. **Check Celery logs:**
```bash
tail -f logs/crawler.log
```

3. **Check screenshot directory permissions:**
```bash
ls -la screenshots/
```

4. **Verify Playwright is installed:**
```bash
playwright install chromium
```

### File Not Found Errors

1. **Check database screenshot_path:**
```python
python manage.py shell
>>> from crawler.models import CrawledPage
>>> page = CrawledPage.objects.get(id=YOUR_PAGE_ID)
>>> print(page.screenshot_path)
>>> import os
>>> print(os.path.exists(page.screenshot_path))
```

2. **Check BASE_DIR settings:**
```python
from django.conf import settings
print(settings.BASE_DIR)
```

### Screenshot Quality Issues

Screenshots are captured with:
- **Viewport**: 1920x1080
- **Mode**: Full page (scrolls to capture entire page)
- **Format**: PNG
- **Browser**: Chromium (headless)

To adjust quality, modify the Playwright configuration in `capture_page_screenshot_task`.

## Future Enhancements

### Planned Features

1. **S3 Integration**: Automatic upload to S3 bucket
2. **Thumbnail Generation**: Create smaller preview images
3. **Screenshot Comparison**: Track visual changes over time
4. **Bulk Capture**: Button to capture screenshots for all pages in a job
5. **Screenshot Gallery**: Grid view of all screenshots
6. **PDF Export**: Export screenshots to PDF report
7. **Scheduled Re-capture**: Automatically update screenshots periodically

### Migration Path

When ready to migrate to S3:

1. Enable S3 in settings
2. Run migration script to upload existing screenshots
3. Update database paths to S3 URLs
4. Keep local copies as backup (optional)
5. Serve via CloudFront for better performance

## Cost Considerations

### Local Storage
- **Pros**: Free, fast access, no external dependencies
- **Cons**: Limited by disk space, not shareable across servers

### S3 Storage
- **Pros**: Unlimited storage, shareable, durable, CDN integration
- **Cons**: Storage costs, transfer costs, API latency

**Estimated S3 Costs** (assuming 1MB per screenshot):
- 10,000 pages = 10GB storage ≈ $0.23/month
- 1,000,000 pages = 1TB storage ≈ $23/month
- Plus transfer costs for viewing screenshots

## Summary

The screenshot system provides:
- ✅ URL-based hierarchical storage
- ✅ Automatic capture during crawls
- ✅ On-demand capture for existing pages
- ✅ Full-page PNG screenshots
- ✅ S3-ready architecture
- ✅ Simple UI integration
- ✅ Async processing with Celery

The implementation is production-ready for local storage and can be easily migrated to S3 when needed.

