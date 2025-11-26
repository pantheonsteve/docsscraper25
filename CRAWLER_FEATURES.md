# Crawler New Features Documentation

This document describes the new features added to the documentation crawler.

## Features Overview

### 1. Page Limit (for Testing)
### 2. Raw HTML Capture
### 3. Screenshot Capture

---

## 1. Page Limit

**Purpose**: Limit the number of pages crawled, useful for testing without running a full crawl.

**Usage**:

```bash
python manage.py crawl --url https://example.com/docs --max-pages 10
```

**How it works**:
- The `--max-pages` parameter sets a limit on the total number of pages to crawl
- When the limit is reached, Scrapy will automatically stop the crawl
- This uses Scrapy's built-in `CLOSESPIDER_PAGECOUNT` setting

**Examples**:

```bash
# Crawl only 5 pages (quick test)
python manage.py crawl --url https://docs.example.com --max-pages 5

# Crawl 50 pages with depth limit of 3
python manage.py crawl --url https://docs.example.com --max-pages 50 --depth 3
```

---

## 2. Raw HTML Capture

**Purpose**: Store the raw HTML of each page for later reprocessing or analysis.

**Usage**:

```bash
python manage.py crawl --url https://example.com/docs --capture-html
```

**How it works**:
- The `--capture-html` flag enables HTML storage
- The full HTML response is saved to the `raw_html` field in the database
- This allows you to reprocess pages without re-crawling

**Storage**:
- Stored in: `CrawledPage.raw_html` (TextField)
- Database field: `raw_html`

**Examples**:

```bash
# Capture HTML for later analysis
python manage.py crawl --url https://docs.example.com --capture-html

# Capture HTML with page limit (testing)
python manage.py crawl --url https://docs.example.com --capture-html --max-pages 10
```

**Use Cases**:
- Debugging extraction issues
- Re-running analysis without re-crawling
- Archiving original content
- Training ML models on HTML structure

---

## 3. Screenshot Capture

**Purpose**: Take full-page screenshots of each crawled page.

**Usage**:

```bash
python manage.py crawl --url https://example.com/docs --screenshots
```

**How it works**:
- The `--screenshots` flag enables screenshot capture
- Requires Playwright (automatically enabled when screenshots are requested)
- Takes full-page screenshots using Playwright's screenshot API
- Saves screenshots to disk and stores the path in the database

**Storage**:
- Directory: `screenshots/<job_id>/`
- Filename format: `<sequence>_<url_path>.png`
- Database field: `CrawledPage.screenshot_path`
- Example: `screenshots/123/0001_getting-started.png`

**Requirements**:
- Playwright must be installed and configured
- Screenshots automatically enable Playwright if not already enabled

**Examples**:

```bash
# Capture screenshots of all pages
python manage.py crawl --url https://docs.example.com --screenshots

# Capture screenshots with page limit (testing)
python manage.py crawl --url https://docs.example.com --screenshots --max-pages 5

# Force Playwright and capture screenshots
python manage.py crawl --url https://docs.example.com --playwright always --screenshots
```

**Use Cases**:
- Visual regression testing
- Content auditing
- Design analysis
- Creating visual documentation archives
- Compliance/legal records

**Performance Notes**:
- Screenshots add overhead to crawling
- Each screenshot operation takes ~1-3 seconds
- File sizes vary (typically 100KB - 2MB per screenshot)
- Consider using `--max-pages` for testing

---

## Combining Features

You can combine multiple features in a single crawl:

```bash
# Full-featured test crawl (limit pages, capture HTML and screenshots)
python manage.py crawl \
  --url https://docs.example.com \
  --max-pages 10 \
  --capture-html \
  --screenshots \
  --depth 2

# Production crawl with HTML and screenshots (no page limit)
python manage.py crawl \
  --url https://docs.example.com \
  --capture-html \
  --screenshots \
  --playwright always \
  --async
```

---

## Database Schema Changes

A new migration has been created:

- **Migration**: `crawler/migrations/0008_add_screenshot_path.py`
- **Field**: `CrawledPage.screenshot_path` (CharField, max_length=500, nullable)

**Apply the migration**:

```bash
python manage.py migrate crawler
```

---

## Accessing the Data

### Python/Django Shell

```python
from crawler.models import CrawledPage

# Get a page with screenshots
page = CrawledPage.objects.filter(screenshot_path__isnull=False).first()
print(f"Screenshot: {page.screenshot_path}")

# Get a page with raw HTML
page = CrawledPage.objects.filter(raw_html__isnull=False).first()
print(f"HTML length: {len(page.raw_html)}")

# Get pages from a specific job with screenshots
from core.models import CrawlJob
job = CrawlJob.objects.get(id=123)
pages_with_screenshots = job.pages.filter(screenshot_path__isnull=False)
```

### Viewing Screenshots

Screenshots are stored in the filesystem:

```bash
# List all screenshots for a job
ls screenshots/123/

# View a screenshot (macOS)
open screenshots/123/0001_getting-started.png

# View a screenshot (Linux)
xdg-open screenshots/123/0001_getting-started.png
```

---

## Configuration Storage

Configuration is stored in the `CrawlJob.config` JSON field:

```json
{
  "depth_limit": 5,
  "use_playwright": "auto",
  "capture_html": true,
  "screenshots": true,
  "max_pages": 10
}
```

---

## Tips and Best Practices

### For Testing

1. Always use `--max-pages` when testing new features
2. Start with small values (5-10 pages)
3. Test on a single documentation site first

### For Production

1. Consider storage requirements for raw HTML and screenshots
2. Monitor disk space when using screenshots
3. Use `--async` for background processing
4. Set up proper backup for the screenshots directory

### Performance Optimization

1. Use `--max-pages` to limit test crawls
2. Raw HTML capture has minimal performance impact
3. Screenshots add significant time (1-3 seconds per page)
4. Consider crawling without screenshots first, then re-crawl specific pages

### Storage Management

```bash
# Check screenshots directory size
du -sh screenshots/

# Remove old screenshots (example: job 123)
rm -rf screenshots/123/

# Clean up raw HTML in database (if needed)
# Use Django admin or shell to clear raw_html field for old pages
```

---

## Troubleshooting

### Screenshots not working

1. Check if Playwright is installed:
   ```bash
   pip install scrapy-playwright
   playwright install chromium
   ```

2. Verify Playwright is enabled in the crawl

3. Check logs for errors related to screenshot capture

### Raw HTML not saved

1. Verify `--capture-html` flag is set
2. Check database field exists (run migrations)
3. Verify pipeline is saving the field

### Page limit not working

1. Verify `--max-pages` parameter is set
2. Check Scrapy settings are being applied
3. Review crawler logs for CLOSESPIDER_PAGECOUNT messages

---

## Example Workflows

### Quick Test of New Documentation Site

```bash
# Test with 5 pages, capture everything
python manage.py crawl \
  --url https://docs.newsite.com \
  --max-pages 5 \
  --capture-html \
  --screenshots \
  --client "NewSite Test"
```

### Full Production Crawl

```bash
# Full crawl with all features
python manage.py crawl \
  --url https://docs.production.com \
  --capture-html \
  --screenshots \
  --depth 10 \
  --async \
  --client "Production Docs"
```

### Archive Existing Documentation

```bash
# Comprehensive archive with visuals
python manage.py crawl \
  --url https://docs.archive.com \
  --capture-html \
  --screenshots \
  --playwright always \
  --client "Archive Project"
```

---

## API Reference

### Command Line Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--max-pages` | int | None | Maximum number of pages to crawl |
| `--capture-html` | flag | False | Store raw HTML for each page |
| `--screenshots` | flag | False | Capture full-page screenshots |
| `--playwright` | choice | auto | Playwright usage: auto/always/never |
| `--url` | string | Required | Starting URL for the crawl |
| `--client` | string | "Default" | Client name or ID |
| `--depth` | int | 5 | Maximum crawl depth |
| `--async` | flag | False | Run asynchronously via Celery |

### Model Fields

**CrawledPage.raw_html**
- Type: TextField
- Nullable: Yes
- Description: Original HTML response

**CrawledPage.screenshot_path**
- Type: CharField(max_length=500)
- Nullable: Yes
- Description: Relative path to screenshot file

---

## Future Enhancements

Potential improvements for these features:

1. **Selective HTML capture**: Only capture HTML for specific page types
2. **Screenshot formats**: Support for different formats (JPEG, WebP)
3. **Thumbnail generation**: Create smaller preview images
4. **Cloud storage**: Store screenshots in S3/GCS instead of local disk
5. **Screenshot comparison**: Visual diff between crawls
6. **HTML compression**: Compress raw HTML to save space
7. **Viewport options**: Different screenshot sizes (mobile, tablet, desktop)

---

## Support

For issues or questions about these features:

1. Check the logs: `logs/crawler.log`
2. Review Django admin: `/admin/crawler/crawledpage/`
3. Check the database: Verify fields are populated
4. Review this documentation for examples

---

*Last updated: 2025-11-20*

