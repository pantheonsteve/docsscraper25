# 🧪 Pre-Crawl Analysis Workflow - Testing Checklist

## Prerequisites
- [ ] Django server running: `python manage.py runserver`
- [ ] Celery worker running: `celery -A config worker -l info -Q celery,crawling,analysis`
- [ ] Anthropic API key in `.env`: `ANTHROPIC_API_KEY=sk-ant-...`
- [ ] At least one active client in the database

## Test Workflow

### ✅ Step 1: Navigate to New Crawl
1. Open browser to `http://localhost:8000/crawl/new/`
2. **Expected:** New crawl form displays
3. **Verify:** "Pre-Analyze Site" button is visible

### ✅ Step 2: Trigger Pre-Analysis
1. Select a client from dropdown
2. Enter test URL: `https://docs.datadoghq.com/logs/`
3. Click "🔍 Pre-Analyze Site (AI-powered)" button
4. **Expected:** 
   - Button becomes disabled and shows loading state
   - Status message appears: "⏳ Analyzing site structure..."
   - Page redirects to analysis results page (may take 30-60 seconds)

### ✅ Step 3: Review Analysis Results
**URL:** `http://localhost:8000/precrawl/review/<config_id>/`

**Verify the following sections appear:**

#### Header
- [ ] Title: "AI Crawl Configuration"
- [ ] Domain name displayed
- [ ] Confidence badge (High/Medium/Low)
- [ ] Number of pages analyzed

#### Main Content Selector
- [ ] Displays a CSS selector (e.g., `.markdown-body`)
- [ ] Selector is in a code-style box
- [ ] Explanation text below

#### Exclude Selectors
- [ ] Shows list of selectors to exclude (e.g., `nav`, `header`, `.sidebar`)
- [ ] Each in its own code-style box
- [ ] Explanation text

#### Link Extraction Rules
- [ ] "Links to Follow" selector
- [ ] "Links to Ignore" selector
- [ ] "In-Page Navigation" selector (if detected)
- [ ] Explanation text

#### Accessibility Analysis
- [ ] Full content selector (if detected)
- [ ] TOC selector (if detected)

#### AI Reasoning
- [ ] Blue box with AI's explanation
- [ ] Reasoning makes sense for the site

#### Patterns Detected
- [ ] Content indicators list (classes/IDs)
- [ ] Navigation indicators list

#### Pages Analyzed
- [ ] List of URLs that were sampled
- [ ] Shows "... and X more" if > 5 pages

#### Action Buttons
- [ ] Three buttons visible:
  - ✅ Approve & Start Crawl (green)
  - ❌ Reject & Re-analyze (red)
  - ← Back (gray)

### ✅ Step 4: Approve Configuration
1. Click "✅ Approve & Start Crawl"
2. **Expected:**
   - Redirects to new crawl form
   - Green banner appears: "Using AI-Optimized Configuration"
   - Shows config name in banner
   - Form is pre-populated with original client and URL

### ✅ Step 5: Start Optimized Crawl
1. Verify green banner is showing
2. Adjust other settings if needed:
   - Depth Limit
   - JavaScript Rendering
   - Page Limit
   - Capture HTML
   - Screenshots
3. Click "🚀 Start Crawl"
4. **Expected:**
   - Success message: "Crawl job #X created and started!"
   - Redirects to job detail page

### ✅ Step 6: Verify Configuration in Job
**URL:** `http://localhost:8000/job/<job_id>/`

**Check "Crawl Configuration" section:**
- [ ] Shows all configured settings
- [ ] If AI config was used, spider logs should mention it

**Check job logs (when job starts):**
```
Look for log lines like:
"Using crawl configuration: <config_name>"
"Main content selector: <selector>"
```

### ✅ Step 7: Verify Spider Behavior
Once crawl is running, check:

1. **Content Extraction**
   - Pages should have cleaner content
   - Less navigation text in `main_content` field

2. **Link Following**
   - Check "Pages Found" count
   - Should be MUCH lower than without config
   - Example: 150 pages instead of 1,540

3. **Screenshots** (if enabled)
   - Should still capture FULL page
   - Not affected by content selectors

### ✅ Step 8: Test Rejection Flow
1. Start a new pre-analysis
2. On review page, click "❌ Reject & Re-analyze"
3. **Expected:**
   - Returns to new crawl form
   - Message: "Configuration rejected. You can run a new analysis."
   - Config status in DB: `rejected`

### ✅ Step 9: Test Direct URL Access
1. Get config ID from a previous analysis
2. Navigate directly to: `http://localhost:8000/precrawl/review/<config_id>/`
3. **Expected:**
   - Review page loads
   - If already approved/rejected, action buttons may be disabled
   - Status shown at bottom

## 🔍 Things to Check

### Database
```sql
-- Check configurations
SELECT id, name, status, confidence, created_at 
FROM crawler_crawlconfiguration 
ORDER BY created_at DESC 
LIMIT 5;

-- Check if config was used in jobs
SELECT id, target_url, config 
FROM core_crawljob 
WHERE config::text LIKE '%crawl_config_id%' 
ORDER BY created_at DESC 
LIMIT 5;
```

### Logs
```bash
# Django logs
tail -f logs/django.log | grep -i "crawl config"

# Crawler logs
tail -f logs/crawler.log | grep -i "config"

# Celery logs
# (Should see analysis task running)
```

### API Key Issues
If analysis fails immediately:
```bash
# Check API key is set
python manage.py shell
>>> from decouple import config
>>> config('ANTHROPIC_API_KEY')
# Should output: 'sk-ant-...'
```

## 🐛 Common Issues

### Issue: "Pre-Analyze" button does nothing
**Check:**
- Browser console for JavaScript errors
- CSRF token is present in form
- Client is selected

### Issue: Analysis takes too long (> 2 min)
**Possible causes:**
- Site is slow or blocking requests
- Network issues
- Too many sample pages

**Check:**
```bash
tail -f logs/crawler.log
# Look for "Fetching HTML from..." messages
```

### Issue: No selectors generated
**Possible causes:**
- AI couldn't parse HTML structure
- Site has unusual structure
- Sample pages too different from each other

**Check:**
- Review AI reasoning in results
- Try a different, more representative URL

### Issue: Selectors don't work during crawl
**Possible causes:**
- Site structure changed
- Selectors too specific
- JavaScript required but not enabled

**Check:**
- Enable Playwright: "Always"
- Review crawler logs for selector errors
- Test selectors manually in browser console

## ✅ Success Criteria

All of the following should be true:

- [ ] Pre-analysis completes in 30-90 seconds
- [ ] Review page shows all sections correctly
- [ ] Approval flow works (approve → redirect → banner shown)
- [ ] Configuration is stored in database
- [ ] Starting a crawl includes config ID in job.config
- [ ] Spider loads and uses configuration
- [ ] Link count is dramatically reduced
- [ ] Content quality is improved
- [ ] Screenshots remain unaffected
- [ ] Rejection flow works

## 📊 Expected Results

### Good Analysis Output Example
```
Main Content Selector: .markdown-body
Exclude Selectors: 
  - nav.sidebar
  - header.site-header
  - .breadcrumbs
  - footer
Link Include: main.content a
Link Exclude: .sidenav a, nav a
In-Page Navigation: .toc a, a.header-anchor
Confidence: high
```

### Improved Crawl Metrics
- **Before:** 1,540 links found → 1,540 pages queued
- **After:** 150 links found → 150 pages queued
- **Improvement:** 90% reduction in noise ✨

## 🎯 Next Steps After Testing

If all tests pass:
1. ✅ Mark feature as production-ready
2. 📚 Share guide with team
3. 🎓 Train users on workflow
4. 📈 Monitor crawl quality improvements
5. 🔧 Fine-tune based on feedback

If issues found:
1. 🐛 Document issues in detail
2. 🔍 Check relevant logs
3. 💬 Report to development team
4. 🛠️ Apply fixes and re-test

