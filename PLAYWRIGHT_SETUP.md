# Playwright Integration for JavaScript Rendering

## ✅ Setup Complete

Your crawler now has full Playwright support for scraping JavaScript-rendered pages (React, Vue, Angular, Next.js, etc.).

## What Was Done

1. **✅ Database column fixed** - Renamed `unigue_content_pages` → `unique_content_pages`
2. **✅ scrapy-playwright installed** - Package is already in requirements.txt and installed
3. **✅ Download handlers configured** - Playwright handlers are enabled in `crawler/scrapy_settings.py`
4. **✅ Auto-detection implemented** - Spider can automatically detect if JS rendering is needed
5. **✅ Three rendering modes** - `auto`, `always`, `never`

## One-Time Setup Required

Install Chromium browser (only needs to be done once):

```bash
cd /Users/steve.bresnick/Projects/docsscraper
. .venv/bin/activate
playwright install chromium
```

This downloads ~130MB of browser files.

## How to Use

### Auto-detect Mode (Recommended)
```bash
python manage.py crawl --url=https://docs.example.com --playwright=auto
```

The spider will:
- Check the first page for JS framework indicators (React, Vue, Angular, Next.js, Gatsby, etc.)
- Analyze content-to-script ratio
- Look for SPA root elements (`#root`, `#app`, `__next`, etc.)
- Use Playwright for all pages if JS is detected, otherwise use standard HTTP requests

### Always Use Playwright
```bash
python manage.py crawl --url=https://docs.example.com --playwright=always
```

Forces Playwright for every page. Use when:
- You know the site is a SPA (single-page application)
- Auto-detection misses dynamic content
- Content consistently loads via JavaScript

### Never Use Playwright
```bash
python manage.py crawl --url=https://docs.example.com --playwright=never
```

Standard HTTP requests only. Use when:
- Site is pure static HTML (Jekyll, Hugo, WordPress, etc.)
- Maximum speed is required
- You've confirmed no JS rendering is needed

## Via API

When starting crawls via API, include in the config:

```json
{
  "client_id": 1,
  "target_url": "https://docs.example.com",
  "config": {
    "depth_limit": 5,
    "use_playwright": "auto"
  }
}
```

## Performance Comparison

| Mode | Speed | Resource Usage | Best For |
|------|-------|----------------|----------|
| `never` | ⚡⚡⚡ Fastest | Low (50MB RAM) | Static HTML sites |
| `auto` | ⚡⚡ Fast | Medium (100MB RAM) | Unknown sites |
| `always` | ⚡ Slower | High (150-200MB RAM/browser) | Known SPAs |

## How Detection Works

The spider's `_detect_javascript_requirement()` method checks for:

1. **Framework keywords** - react, vue, angular, next.js, gatsby, docusaurus, vuepress, etc.
2. **Content-to-script ratio** - If 5+ scripts but <500 chars of content
3. **SPA root elements** - Empty `#root`, `#app`, `#app-root`, `__next`, `__nuxt` divs
4. **React/Vue attributes** - `data-reactroot`, `data-react-helmet`, `data-vue-ssr`

## Configuration

Playwright settings in `crawler/scrapy_settings.py`:

```python
PLAYWRIGHT_BROWSER_TYPE = 'chromium'
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000  # 30 seconds
PLAYWRIGHT_ABORT_REQUEST = lambda req: req.resource_type in ['image', 'stylesheet', 'font']
```

This automatically skips loading images, stylesheets, and fonts for better performance.

## Testing

Test on a JavaScript-heavy site:

```bash
# Test with auto-detection
python manage.py crawl --url=https://react.dev --playwright=auto --depth=2

# Should detect React and use Playwright automatically
```

## Troubleshooting

**Problem:** `playwright: command not found`
**Solution:** Make sure you activated the virtual environment:
```bash
. .venv/bin/activate
playwright install chromium
```

**Problem:** Crawl is very slow
**Solution:** Use `--playwright=never` if the site doesn't need JS rendering, or reduce `CONCURRENT_REQUESTS` in settings when using Playwright.

**Problem:** Pages appear empty
**Solution:** Try `--playwright=always` - the site may need JS rendering but wasn't detected.

## Files Modified

- `core/models.py` - Removed `db_column` workaround
- `core/migrations/0003_rename_unigue_to_unique_content_pages.py` - SQL migration to fix column name
- `crawler/spiders/doc_spider.py` - Already has full Playwright support with auto-detection
- `crawler/scrapy_settings.py` - Playwright handlers are configured

## Next Steps

1. Run `playwright install chromium` to complete setup
2. Test with a JavaScript-heavy documentation site
3. Monitor performance and adjust settings as needed
4. Configure per-client Playwright preferences in Django admin if needed

