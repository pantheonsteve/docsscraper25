# Troubleshooting: Screenshot Capture Button Not Working

## Quick Diagnosis

If the "📸 Capture Screenshot" button is not working in the UI, follow these steps:

### 1. Check if Celery is Running with Correct Queues

```bash
pgrep -fl celery
celery -A config inspect active_queues
```

You should see `crawling` in the active queues. If not:

```bash
pkill -f "celery -A config worker"
cd /Users/steve.bresnick/Projects/docsscraper
source .venv/bin/activate
celery -A config worker -l info -Q celery,crawling,analysis
```

### 2. Check if Django Server Picked Up Changes

Sometimes the Django development server doesn't auto-reload after code changes. **Restart it:**

```bash
# Find and stop the server
pgrep -fl "manage.py runserver"
pkill -f "manage.py runserver"

# Start it again
cd /Users/steve.bresnick/Projects/docsscraper
source .venv/bin/activate
python manage.py runserver
```

### 3. Verify the Button is Visible

Go to a page without a screenshot:
- Example: http://localhost:8000/page/533/

You should see:
- ✅ **Orange button** "📸 Capture Screenshot" if no screenshot exists
- ✅ **Blue button** "📸 View Screenshot" if screenshot exists

### 4. Test Manually

```bash
cd /Users/steve.bresnick/Projects/docsscraper
source .venv/bin/activate
python manage.py shell
```

Then in the shell:
```python
from crawler.tasks import capture_page_screenshot_task
from crawler.models import CrawledPage

# Get a page without screenshot
page = CrawledPage.objects.filter(screenshot_path__isnull=True).first()
print(f"Testing with page {page.id}")

# Trigger capture
task = capture_page_screenshot_task.delay(page.id)
print(f"Task ID: {task.id}")

# Wait 5 seconds then check
import time
time.sleep(5)

page.refresh_from_db()
print(f"Screenshot path: {page.screenshot_path}")
```

If this works, then Celery is fine and the issue is in the UI/browser.

### 5. Check Browser Console

Open browser developer tools (F12) and check for:
- ❌ JavaScript errors
- ❌ CSRF token errors
- ❌ Network errors (look at Network tab)

### 6. Check Server Logs

Look for errors when clicking the button:
```bash
# Watch Django logs in real-time
tail -f logs/docanalyzer.log

# Or check Celery logs
tail -f logs/crawler.log
```

## Common Issues

### Issue 1: Button Not Visible
**Symptom:** Can't see the "Capture Screenshot" button

**Causes:**
- Page already has a screenshot (check `page.screenshot_path`)
- CSS styling issue hiding the button
- Template not rendering correctly

**Solution:**
```python
# Check if page has screenshot
from crawler.models import CrawledPage
page = CrawledPage.objects.get(id=YOUR_PAGE_ID)
print(f"Has screenshot: {bool(page.screenshot_path)}")
print(f"Path: {page.screenshot_path}")
```

### Issue 2: Button Visible But Nothing Happens
**Symptom:** Button appears but clicking does nothing

**Causes:**
- Celery not listening to `crawling` queue
- CSRF token issue
- JavaScript preventing form submission

**Solution:**
1. Check Celery queues (see step 1 above)
2. Hard refresh browser (Ctrl+Shift+R or Cmd+Shift+R)
3. Check browser console for errors

### Issue 3: Button Click Causes Error
**Symptom:** Error page or error message after clicking

**Causes:**
- View not found (404)
- Permission error (403)
- Server error (500)

**Solution:**
- Check Django server console for traceback
- Verify URL routing in `dashboard/urls.py`
- Check logs: `tail -f logs/docanalyzer.log`

### Issue 4: Task Never Completes
**Symptom:** Button clicked, message shows, but screenshot never appears

**Causes:**
- Celery task failing
- Playwright not installed
- Permission issues creating screenshot directory

**Solution:**
```bash
# Check Celery logs for errors
tail -50 logs/crawler.log | grep -i error

# Check if Playwright is installed
playwright install chromium

# Check screenshot directory permissions
ls -la screenshots/
```

## Verification Checklist

- [ ] Celery running with `-Q celery,crawling,analysis`
- [ ] Django development server running
- [ ] Can see "Capture Screenshot" button on pages without screenshots
- [ ] No JavaScript errors in browser console
- [ ] Clicking button shows success message
- [ ] Screenshot appears after ~5-10 seconds (refresh page)
- [ ] Screenshot file exists in `screenshots/` directory

## Test URLs

Pages without screenshots (should show Capture button):
```
http://localhost:8000/page/533/
```

Pages with screenshots (should show View button):
```
http://localhost:8000/page/1161/
http://localhost:8000/page/4360/
http://localhost:8000/page/952/
```

## Still Not Working?

If you've tried everything above and it's still not working, run this comprehensive test:

```bash
cd /Users/steve.bresnick/Projects/docsscraper
source .venv/bin/activate

python manage.py shell -c "
print('=== Screenshot System Diagnostic ===')
print()

# 1. Check models
from crawler.models import CrawledPage
total = CrawledPage.objects.count()
with_ss = CrawledPage.objects.filter(screenshot_path__isnull=False).count()
without_ss = CrawledPage.objects.filter(screenshot_path__isnull=True).count()
print(f'Pages: {total} total, {with_ss} with screenshots, {without_ss} without')
print()

# 2. Check Celery task
from crawler.tasks import capture_page_screenshot_task
print(f'Task available: {capture_page_screenshot_task}')
print()

# 3. Check URL routing
from django.urls import reverse
try:
    url = reverse('dashboard:capture_page_screenshot', args=[1])
    print(f'✅ URL routing OK: {url}')
except Exception as e:
    print(f'❌ URL routing ERROR: {e}')
print()

# 4. Test a capture
page = CrawledPage.objects.filter(screenshot_path__isnull=True).first()
if page:
    print(f'Testing capture for page {page.id}...')
    task = capture_page_screenshot_task.delay(page.id)
    print(f'Task triggered: {task.id}')
    print(f'Task state: {task.state}')
else:
    print('No pages available for testing')
"
```

This will show you exactly where the problem is.

