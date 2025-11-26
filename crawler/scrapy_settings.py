"""
Scrapy settings for the documentation crawler.
These settings are used when running Scrapy spiders.
"""

import os
import sys

# Setup Django integration
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Initialize Django
import django
django.setup()

# Scrapy settings
BOT_NAME = 'docanalyzer'

SPIDER_MODULES = ['crawler.spiders']
NEWSPIDER_MODULE = 'crawler.spiders'

# Crawl responsibly by identifying yourself
USER_AGENT = os.getenv('CRAWLER_USER_AGENT', 'DocAnalyzer Bot (+https://yourcompany.com/bot)')

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Configure maximum concurrent requests
CONCURRENT_REQUESTS = int(os.getenv('CRAWLER_CONCURRENT_REQUESTS', 16))

# Configure a delay for requests for the same website
DOWNLOAD_DELAY = float(os.getenv('CRAWLER_POLITENESS_DELAY', 0.5))

# Disable cookies (enabled by default)
COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
TELNETCONSOLE_ENABLED = False

# Override the default request headers
DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en',
}

# Enable or disable spider middlewares
SPIDER_MIDDLEWARES = {
    'scrapy.spidermiddlewares.depth.DepthMiddleware': 100,
    'scrapy.spidermiddlewares.httperror.HttpErrorMiddleware': 50,
}

# Enable or disable downloader middlewares
DOWNLOADER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': 90,
}

# Enable or disable extensions
EXTENSIONS = {
    'scrapy.extensions.telnet.TelnetConsole': None,
}

# Configure item pipelines
ITEM_PIPELINES = {
    'crawler.pipelines.django_pipeline.DjangoStoragePipeline': 300,
}

# Enable and configure HTTP caching (disabled by default)
HTTPCACHE_ENABLED = False

# Retry settings
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408, 429]

# Timeout settings
DOWNLOAD_TIMEOUT = 60

# Auto-throttle settings
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_MAX_DELAY = 10.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
AUTOTHROTTLE_DEBUG = False

# Depth limit (can be overridden per spider)
DEPTH_LIMIT = int(os.getenv('CRAWLER_DEFAULT_DEPTH_LIMIT', 5))

# Breadth-first crawling
DEPTH_PRIORITY = 1
SCHEDULER_DISK_QUEUE = 'scrapy.squeues.PickleFifoDiskQueue'
SCHEDULER_MEMORY_QUEUE = 'scrapy.squeues.FifoMemoryQueue'

# Logging
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(levelname)s: %(message)s'

# Playwright settings (for JavaScript rendering)
# Playwright is ENABLED but pages must explicitly request it via meta={'playwright': True}
# This allows selective JS rendering only when needed
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

PLAYWRIGHT_BROWSER_TYPE = 'chromium'
PLAYWRIGHT_LAUNCH_OPTIONS = {
    'headless': True,
    'args': [
        '--disable-blink-features=AutomationControlled',  # Avoid detection
        '--disable-dev-shm-usage',  # Overcome limited resource problems
        '--no-sandbox',  # Required for some environments
    ]
}

# Only use Playwright when explicitly requested in request.meta
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000  # 30 seconds
PLAYWRIGHT_ABORT_REQUEST = lambda req: req.resource_type in ['image', 'stylesheet', 'font']  # Skip unnecessary resources

# Redis settings (for distributed crawling - optional)
# Uncomment to enable scrapy-redis
# SCHEDULER = "scrapy_redis.scheduler.Scheduler"
# DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"
# REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
