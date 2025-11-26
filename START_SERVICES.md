# Starting Services

Quick reference for starting all required services for the Documentation Crawler.

## Prerequisites

```bash
cd /Users/steve.bresnick/Projects/docsscraper
source .venv/bin/activate
```

## 1. PostgreSQL Database

Make sure PostgreSQL is running:
```bash
# Check if running
pg_isready

# Or check with psql
psql -U docanalyzer -d docanalyzer -c "SELECT version();"
```

## 2. Celery Worker (REQUIRED for crawls and screenshots)

**Important:** Must listen to all queues for screenshot capture to work!

```bash
celery -A config worker -l info -Q celery,crawling,analysis
```

### Common Celery Commands

```bash
# Check if Celery is running
pgrep -fl celery

# Check active queues
celery -A config inspect active_queues

# Check registered tasks
celery -A config inspect registered | grep screenshot

# Stop Celery
pkill -f "celery -A config worker"

# View active tasks
celery -A config inspect active

# View queued tasks
celery -A config inspect reserved
```

## 3. Django Development Server

```bash
python manage.py runserver
```

Then visit: http://localhost:8000/

## 4. Playwright (if not already installed)

Playwright is required for JavaScript rendering and screenshots:

```bash
playwright install chromium
```

## Running Everything Together

### Terminal 1: Celery Worker
```bash
cd /Users/steve.bresnick/Projects/docsscraper
source .venv/bin/activate
celery -A config worker -l info -Q celery,crawling,analysis
```

### Terminal 2: Django Server
```bash
cd /Users/steve.bresnick/Projects/docsscraper
source .venv/bin/activate
python manage.py runserver
```

## Troubleshooting

### "Nothing happened when I clicked Capture Screenshot"

This usually means Celery is not running or not listening to the `crawling` queue.

**Solution:**
1. Stop any running Celery workers: `pkill -f "celery -A config worker"`
2. Start Celery with all queues: `celery -A config worker -l info -Q celery,crawling,analysis`
3. Verify queues: `celery -A config inspect active_queues`

### "You cannot call this from an async context"

This error was fixed by restructuring the `capture_page_screenshot_task` to handle database operations outside the Playwright context. If you see this error, make sure you have the latest version of `crawler/tasks.py`.

### "Screenshot file not found"

1. Check if the file exists on disk:
```bash
find screenshots/ -name "*.png"
```

2. Check the database screenshot_path:
```bash
python manage.py shell -c "from crawler.models import CrawledPage; p = CrawledPage.objects.get(id=YOUR_PAGE_ID); print(p.screenshot_path)"
```

3. Verify the path is correct (should be relative like `screenshots/domain.com/path/screenshot.png`)

## Logs

- **Celery/Crawler logs:** `logs/crawler.log`
- **Django logs:** `logs/docanalyzer.log`
- **JSON logs:** `logs/my-log.json`

View live logs:
```bash
tail -f logs/crawler.log
```

## Database Migrations

If you've pulled new code with model changes:

```bash
python manage.py migrate
```

Check for pending migrations:
```bash
python manage.py showmigrations
```

## Environment Variables

Make sure your `.env` file has these settings:
```bash
# Database
DB_NAME=docanalyzer
DB_USER=docanalyzer
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# Screenshot Storage (local by default)
SCREENSHOT_STORAGE_BACKEND=local
```

## Production Notes

For production deployment:

1. Use a process manager like `supervisor` or `systemd` to keep Celery running
2. Use `gunicorn` instead of `python manage.py runserver`
3. Set up proper logging rotation
4. Consider using Redis as a message broker for Celery
5. Configure S3 for screenshot storage (see `SCREENSHOT_IMPLEMENTATION.md`)

