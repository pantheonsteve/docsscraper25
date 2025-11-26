# Quick Start: New Crawler Features

Three new features have been added to the crawler!

## 🚀 Quick Examples

### 1. Test Crawl (Limit Pages)

```bash
# Crawl only 10 pages - perfect for testing
python manage.py crawl --url https://docs.example.com --max-pages 10
```

### 2. Capture Raw HTML

```bash
# Store the original HTML for each page
python manage.py crawl --url https://docs.example.com --capture-html
```

### 3. Take Screenshots

```bash
# Capture full-page screenshots (requires Playwright)
python manage.py crawl --url https://docs.example.com --screenshots
```

### 4. All Together

```bash
# Test crawl with all features
python manage.py crawl \
  --url https://docs.example.com \
  --max-pages 10 \
  --capture-html \
  --screenshots
```

---

## 📋 Before You Start

### Run the Database Migration

```bash
python manage.py migrate crawler
```

This adds the `screenshot_path` field to the database.

### Verify Playwright (for screenshots)

If you want to use screenshots, make sure Playwright is installed:

```bash
pip install scrapy-playwright
playwright install chromium
```

---

## 💡 Common Use Cases

### Testing a New Site

```bash
# Quick test: 5 pages with screenshots
python manage.py crawl \
  --url https://docs.newsite.com \
  --max-pages 5 \
  --screenshots \
  --client "Test Crawl"
```

### Development/Debugging

```bash
# Capture HTML for debugging without screenshots
python manage.py crawl \
  --url https://docs.example.com \
  --max-pages 20 \
  --capture-html \
  --client "Debug Crawl"
```

### Full Production Crawl

```bash
# Complete crawl with HTML and screenshots
python manage.py crawl \
  --url https://docs.production.com \
  --capture-html \
  --screenshots \
  --async \
  --client "Production"
```

---

## 📁 Where Files Are Stored

### Screenshots
- **Location**: `screenshots/<job_id>/`
- **Format**: PNG files
- **Example**: `screenshots/123/0001_getting-started.png`

### Raw HTML
- **Location**: Database (`CrawledPage.raw_html` field)
- **Access**: Django admin or Python shell

---

## 🔍 Viewing the Data

### Check Screenshots

```bash
# List screenshots for job ID 123
ls screenshots/123/

# Open a screenshot (macOS)
open screenshots/123/0001_index.png
```

### Access Raw HTML (Python)

```python
from crawler.models import CrawledPage

# Get a page with raw HTML
page = CrawledPage.objects.filter(raw_html__isnull=False).first()
print(page.raw_html[:500])  # Print first 500 chars
```

### Check Screenshot Paths (Python)

```python
from crawler.models import CrawledPage

# Get all pages with screenshots
pages = CrawledPage.objects.filter(screenshot_path__isnull=False)
for page in pages:
    print(f"{page.url} -> {page.screenshot_path}")
```

---

## ⚡ Performance Tips

1. **Start small**: Use `--max-pages 5` for initial tests
2. **Screenshots are slow**: Add 1-3 seconds per page
3. **HTML is cheap**: Minimal performance impact
4. **Test before production**: Always test on small crawls first

---

## 🎯 What's Changed

### New Command Arguments

| Argument | What it does |
|----------|--------------|
| `--max-pages 10` | Stop after 10 pages |
| `--capture-html` | Save raw HTML |
| `--screenshots` | Take page screenshots |

### New Database Fields

- `CrawledPage.raw_html` (TextField)
- `CrawledPage.screenshot_path` (CharField)

### New Configuration Options

These are stored in `CrawlJob.config`:
- `max_pages`: Page limit
- `capture_html`: HTML capture flag
- `screenshots`: Screenshot flag

---

## 🐛 Troubleshooting

### Screenshots not working?

1. Install Playwright: `playwright install chromium`
2. Check that `--screenshots` flag is set
3. Verify Playwright downloads by checking logs

### Raw HTML not saved?

1. Run migrations: `python manage.py migrate crawler`
2. Check that `--capture-html` flag is set
3. Verify in Django admin

### Page limit not working?

1. Check the crawl logs for "CLOSESPIDER_PAGECOUNT"
2. Verify `--max-pages` is set correctly
3. Note: Some pages might be filtered out before counting

---

## 📚 More Information

See `CRAWLER_FEATURES.md` for complete documentation including:
- Detailed explanations
- Advanced usage examples
- API reference
- Storage management
- Best practices

---

## 🎉 Ready to Use!

Try a simple test:

```bash
python manage.py crawl \
  --url https://docs.python.org \
  --max-pages 3 \
  --screenshots \
  --client "Python Docs Test"
```

Then check:
- Django admin: See the pages with screenshots
- File system: `ls screenshots/` 
- Logs: `tail -f logs/crawler.log`

---

*Need help? Check CRAWLER_FEATURES.md for full documentation*

