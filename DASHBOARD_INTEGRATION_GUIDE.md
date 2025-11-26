# Dashboard Integration Guide

## Overview

The crawler's new features (page limit, raw HTML capture, and screenshots) are now fully integrated into the web dashboard! You can configure and launch crawls directly from your browser.

## ✨ What's New

### 1. Enhanced Crawl Configuration Form
- **Page Limit**: Test crawls with a specific number of pages
- **Raw HTML Capture**: Store original HTML for reprocessing
- **Screenshots**: Capture full-page screenshots
- **Smart UI**: Auto-enables Playwright when screenshots are selected

### 2. Improved Job Detail View
- See all configuration options at a glance
- Visual indicators for enabled features
- Clear display of test mode (when page limit is set)

### 3. Enhanced Page Detail View
- **View Screenshots**: See full-page screenshots inline or in a new tab
- **View Raw HTML**: Browse the original HTML with syntax highlighting
- **Copy HTML**: One-click copy to clipboard
- Quick access buttons in the header

## 🚀 How to Use

### Starting a New Crawl

1. **Navigate to New Crawl Form**
   - Go to `/dashboard/crawl/new/`
   - Or click "New Crawl" button from the dashboard

2. **Fill Out the Form**

   **Required Fields:**
   - **Client**: Select or create a client
   - **Target URL**: The starting URL for the crawl

   **Configuration Options:**
   - **Depth Limit** (default: 5): Maximum crawl depth
   - **JavaScript Rendering**: 
     - Auto-detect (recommended)
     - Always (for SPAs)
     - Never (faster)
   - **Page Limit** (optional): Limit pages for testing
   - **☑ Capture Raw HTML**: Store original HTML
   - **☑ Capture Screenshots**: Take full-page screenshots

3. **Submit**
   - Click "🚀 Start Crawl"
   - You'll be redirected to the job detail page
   - The crawl starts immediately

### Example Configurations

#### Quick Test Crawl
```
Client: Test Company
Target URL: https://docs.python.org
Depth Limit: 3
Page Limit: 5
☑ Capture Raw HTML
☑ Capture Screenshots
```
*Perfect for testing - crawls only 5 pages with all features*

#### Development Crawl
```
Client: Dev Testing
Target URL: https://docs.example.com
Depth Limit: 5
Page Limit: 20
☑ Capture Raw HTML
☐ Capture Screenshots
```
*Good for debugging - captures HTML but skips slow screenshots*

#### Production Crawl
```
Client: Production Site
Target URL: https://docs.production.com
Depth Limit: 10
Page Limit: (leave empty)
☑ Capture Raw HTML
☑ Capture Screenshots
JavaScript: Always
```
*Full crawl with all features and guaranteed JavaScript support*

## 📊 Viewing Crawl Results

### Job Detail Page

**Location**: `/dashboard/job/<job_id>/`

**What You'll See:**
- Job status and statistics
- Configuration details (including new features)
- Real-time updates for running crawls
- List of crawled pages
- Error reports

**New Configuration Section:**
- Page Limit: Shows if test mode is active
- Playwright: JavaScript rendering mode
- Raw HTML Capture: Enabled/Disabled status
- Screenshots: Enabled/Disabled status with performance note

### Page Detail Page

**Location**: `/dashboard/page/<page_id>/`

**New Features:**

1. **Action Buttons (in header)**
   - **📄 View Raw HTML**: Opens raw HTML viewer (if HTML was captured)
   - **📸 View Screenshot**: Shows screenshot inline (if screenshot was taken)
   - **View Live Page**: Opens the actual page in a new tab
   - **← Back to Job**: Returns to job detail

2. **Screenshot Section**
   - Click "📸 View Screenshot" to reveal
   - Image displays inline with border and shadow
   - "Open Full Size" button opens in new tab
   - Smooth scroll to screenshot

3. **All Original Features Still Available**
   - AI Readiness scores
   - E-E-A-T metrics
   - Content analysis
   - SEO signals
   - And more!

### Raw HTML Viewer

**Location**: `/dashboard/page/<page_id>/raw-html/`

**Features:**
- Dark theme code viewer
- Syntax-friendly monospace font
- Horizontal and vertical scrolling
- One-click copy to clipboard
- HTML size and line count statistics
- Links to page detail and live page

**Use Cases:**
- Debug parsing issues
- Inspect original markup
- Compare HTML across crawls
- Extract specific elements
- Verify capture accuracy

## 🎯 Dashboard URL Structure

```
/dashboard/                              → Main dashboard
/dashboard/crawl/new/                    → New crawl form
/dashboard/job/<job_id>/                 → Job detail
/dashboard/page/<page_id>/               → Page detail (analysis)
/dashboard/page/<page_id>/raw-html/      → Raw HTML viewer
/dashboard/page/<page_id>/screenshot/    → Screenshot image (PNG)
/dashboard/client/<client_id>/           → Client overview
/dashboard/client/<client_id>/pages/     → All pages for client
```

## 💡 Tips and Best Practices

### For Testing

1. **Always use page limit** when testing new sites
   ```
   Page Limit: 5-10
   ```

2. **Start without screenshots** for faster testing
   ```
   ☐ Capture Screenshots (first test)
   ☑ Capture Screenshots (after validation)
   ```

3. **Use auto-detect Playwright** unless you know the site needs it
   ```
   JavaScript: Auto-detect
   ```

### For Production

1. **Consider storage** when enabling HTML capture
   - Raw HTML can be 100-500KB per page
   - Screenshots are 100KB-2MB per page
   - Monitor disk space

2. **Be selective with screenshots**
   - Screenshots add 1-3 seconds per page
   - Use page limit to test first
   - Consider capturing only for specific doc types

3. **Document your configuration**
   - Note why certain features are enabled
   - Track configuration in client notes

### Performance Optimization

| Feature | Impact | When to Use |
|---------|--------|-------------|
| Page Limit | None (stops early) | Always for testing |
| Raw HTML | Minimal (~1-2% slower) | Most crawls |
| Screenshots | High (~1-3s per page) | When visuals needed |
| Playwright Always | Moderate (~500ms per page) | Only for SPAs |

## 📸 Screenshot Features

### What Gets Captured

- **Full page screenshots**: Entire scrollable height
- **Rendered state**: After JavaScript execution
- **PNG format**: High quality, lossless
- **Organized storage**: `screenshots/<job_id>/`

### Accessing Screenshots

**Three Ways:**

1. **From Page Detail**
   - Click "📸 View Screenshot" button
   - Appears inline on the page

2. **Direct URL**
   - `/dashboard/page/<page_id>/screenshot/`
   - Returns PNG image directly

3. **File System**
   - `screenshots/<job_id>/<sequence>_<url_path>.png`
   - Files named by sequence and URL

### Screenshot Naming

```
screenshots/
├── 123/                           # Job ID
│   ├── 0001_index.png            # First page (index)
│   ├── 0002_getting-started.png  # Second page
│   ├── 0003_api-reference.png    # Third page
│   └── ...
├── 124/
│   └── ...
```

## 📄 Raw HTML Features

### What Gets Stored

- **Complete HTML**: Exactly as received from server
- **After JavaScript**: If Playwright is used
- **Original encoding**: Preserved as-is
- **Database storage**: `CrawledPage.raw_html` field

### Accessing Raw HTML

**Two Ways:**

1. **From Page Detail**
   - Click "📄 View Raw HTML" button
   - Opens in HTML viewer

2. **Direct URL**
   - `/dashboard/page/<page_id>/raw-html/`

### HTML Viewer Features

- **Dark theme**: Easy on eyes for long viewing
- **Code formatting**: Monospace font with line wrapping
- **Copy button**: One-click copy to clipboard
- **Statistics**: Shows HTML size and line count
- **Responsive**: Scrollable for large HTML files

## 🔄 Workflow Examples

### Test New Documentation Site

```
1. Go to /dashboard/crawl/new/
2. Configure:
   - Target URL: New site URL
   - Page Limit: 5
   - ☑ Capture HTML
   - ☑ Screenshots
3. Submit and wait (~30 seconds for 5 pages)
4. Review results:
   - Check screenshots for visual accuracy
   - Review HTML if parsing issues
   - Validate metrics and analysis
5. If good, re-run without page limit
```

### Debug Parsing Issue

```
1. Find problematic page in dashboard
2. Click "📄 View Raw HTML"
3. Review structure and content
4. Copy HTML for local testing
5. Fix parser/spider code
6. Re-crawl to verify fix
```

### Compare Site Versions

```
1. Crawl site with ☑ Capture HTML + ☑ Screenshots
2. Wait for site update
3. Crawl again with same config
4. Compare:
   - Screenshots: Visual changes
   - HTML: Structural changes
   - Metrics: Content quality changes
```

## 🎨 UI/UX Enhancements

### Smart Form Behavior

- **Auto-enable Playwright**: When screenshots are checked
- **Visual feedback**: Checkboxes with clear labels
- **Helpful tips**: Info box explains page limit
- **Validation**: URL and client required

### Visual Indicators

- **Test Mode Badge**: Shows when page limit is set
- **Feature Status**: Green checkmarks for enabled features
- **Performance Notes**: Reminds about screenshot overhead
- **Live Updates**: Real-time status for running crawls

### Responsive Design

- All pages work on mobile and tablet
- Buttons stack appropriately
- Images scale to screen size
- Forms are touch-friendly

## 📊 Monitoring and Management

### Check Crawl Status

1. Go to `/dashboard/`
2. Find your job in "Recent Jobs"
3. Click to view details
4. For running crawls, see live updates

### Cancel a Crawl

1. Go to job detail page
2. Click "Cancel Job" button
3. Confirm cancellation
4. Job will stop within seconds

### Restart a Crawl

1. Go to completed/failed job detail
2. Click "Restart Job"
3. Crawl starts with same configuration
4. Previous data is not deleted (incremental)

### Delete a Job

1. Go to job detail page
2. Click "Delete Job"
3. Confirm deletion
4. All pages and screenshots are removed

## 🔧 Technical Details

### Database Fields

**New/Updated Fields:**
- `CrawledPage.raw_html` (TextField, nullable)
- `CrawledPage.screenshot_path` (CharField, nullable)

**Config Storage:**
- `CrawlJob.config` (JSONField)
  ```json
  {
    "depth_limit": 5,
    "use_playwright": "auto",
    "max_pages": 10,
    "capture_html": true,
    "screenshots": true
  }
  ```

### Screenshot Storage

- **Location**: `BASE_DIR/screenshots/<job_id>/`
- **Format**: PNG images
- **Naming**: `<sequence>_<url_path>.png`
- **Path in DB**: `screenshots/<job_id>/<filename>.png`

### URL Routing

```python
# New URL patterns
path('page/<int:page_id>/raw-html/', views.page_raw_html, name='page_raw_html'),
path('page/<int:page_id>/screenshot/', views.page_screenshot, name='page_screenshot'),
```

### View Functions

**New Views:**
- `page_raw_html(request, page_id)`: Displays raw HTML
- `page_screenshot(request, page_id)`: Serves screenshot image

**Updated Views:**
- `new_crawl(request)`: Handles new configuration options
- `page_detail(request, page_id)`: Shows screenshot and HTML buttons

## 🎁 Bonus Features

### Configuration Presets (Future Enhancement)

Could add preset buttons:
- "Quick Test" (5 pages, HTML only)
- "Full Analysis" (unlimited, HTML + screenshots)
- "Visual Audit" (moderate depth, screenshots only)

### Bulk Operations (Future Enhancement)

Could add ability to:
- Compare pages across crawls
- Export screenshots as ZIP
- Bulk download raw HTML
- Generate visual reports

### Advanced Filtering (Future Enhancement)

Could filter pages by:
- Has screenshot
- Has raw HTML
- Screenshot size
- HTML size

## 📝 Summary

The dashboard now provides a complete interface for:
- ✅ Configuring crawls with all new features
- ✅ Monitoring crawl progress in real-time
- ✅ Viewing configuration details
- ✅ Accessing screenshots inline or full-size
- ✅ Browsing raw HTML with syntax highlighting
- ✅ Managing crawl lifecycle (start, stop, restart, delete)

**No command line required!** Everything can be done through the web interface.

## 🆘 Troubleshooting

### Screenshots Not Appearing

1. Check that `--screenshots` was enabled in config
2. Verify Playwright is installed
3. Check job detail for error messages
4. Look for screenshot files on disk: `ls screenshots/<job_id>/`

### Raw HTML Button Missing

1. Verify `--capture-html` was enabled
2. Check database: `page.raw_html` should not be NULL
3. Re-run crawl with HTML capture enabled

### Page Limit Not Working

1. Check job configuration in job detail view
2. Verify `max_pages` value in `job.config`
3. Check that Scrapy received the setting in logs

### Large Storage Usage

1. Monitor: `du -sh screenshots/`
2. Consider disabling features for some crawls
3. Delete old job data regularly
4. Use page limits for testing

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                    DASHBOARD QUICK START                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Start New Crawl:                                        │
│     /dashboard/crawl/new/                                   │
│                                                              │
│  2. Configure Features:                                     │
│     ☑ Page Limit (for testing)                            │
│     ☑ Capture HTML (minimal overhead)                     │
│     ☑ Screenshots (1-3s per page)                         │
│                                                              │
│  3. Monitor Progress:                                       │
│     /dashboard/job/<id>/ (auto-refreshes)                  │
│                                                              │
│  4. View Results:                                           │
│     /dashboard/page/<id>/ (full analysis)                  │
│     /dashboard/page/<id>/screenshot/ (image)               │
│     /dashboard/page/<id>/raw-html/ (HTML viewer)           │
│                                                              │
│  5. Management:                                             │
│     Cancel | Restart | Delete (buttons on job detail)      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

*Created: 2025-11-20*
*Version: 1.0*

