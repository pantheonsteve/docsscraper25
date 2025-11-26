I need you to build a professional web scraping system for analyzing enterprise documentation sites. This is for a consulting business that provides detailed documentation analysis reports to B2B SaaS companies.

## Business Context
- I'm building a service that crawls documentation sites (typically 5k-50k pages) and generates analysis reports worth $5k-25k to clients
- The system needs to handle long-running crawls (up to 24 hours) professionally
- Crawl first, analyze later pattern - we store everything then run multiple analyses on the same data
- Must be polite and professional when crawling client sites (rate limiting is critical)

## Architecture Requirements

### Core Stack
- Django as the central orchestration layer (all components integrated as Django apps)
- Scrapy for the actual web crawling engine
- PostgreSQL 16 for persistent storage (in Docker container)
- Redis for URL frontier and task queue (in Docker container)
- Celery for background task processing
- Playwright for JavaScript-rendered pages
- Python 3.11+ in a local venv (NOT containerized initially)

### Django App Structure
Create these Django apps:
1. `core` - Shared models (Client, CrawlJob), authentication, base functionality
2. `crawler` - Scrapy integration, CrawledPage model, crawl management
3. `analyzer` - LLM analysis tasks (placeholder for now)
4. `reports` - Report generation (placeholder for now)
5. `dashboard` - Web UI for clients and monitoring

### Data Models

Core models needed:
```
CrawlJob
- client (FK)
- target_url
- status (pending/running/complete/failed)
- config (JSON: depth_limit, patterns, etc.)
- started_at, completed_at
- stats (JSON: pages_crawled, errors, etc.)

CrawledPage  
- job (FK to CrawlJob)
- url (indexed)
- depth
- title
- main_content (extracted text)
- raw_html (optional, for reprocessing)
- code_blocks (JSON)
- internal_links (JSON)
- external_links (JSON)
- headers (JSON: h1-h6 text)
- meta_description
- crawled_at
- response_time
- page_size
- content_hash (for deduplication)
```

### Crawler Specifications

The Scrapy spider should:
1. Use a breadth-first crawl strategy
2. Respect robots.txt
3. Implement polite crawling (1-2 requests/second)
4. Extract and clean main content (remove nav, headers, footers)
5. Detect and extract code blocks with language detection
6. Build a link graph (internal and external links)
7. Handle both static HTML and JavaScript-rendered pages
8. Implement resume capability (save state for restart)
9. Deduplicate pages based on content hash
10. Stay within the original domain unless specified

### Storage Strategy
- Redis: URL frontier (pending URLs), deduplication set, crawl statistics
- PostgreSQL: Crawled content, analysis results, client data
- Filesystem: Optional HTML archive for reprocessing

### Key Features to Implement

1. **Crawl Management**
   - Start/stop/resume crawls via Django admin and API
   - Real-time progress monitoring
   - Multiple concurrent crawls support
   - Configurable depth limits and URL patterns

2. **Smart Extraction**
   - Detect documentation patterns (API reference, tutorials, guides)
   - Extract structured data (tables, code samples)
   - Identify version information
   - Capture navigation structure

3. **Error Handling**
   - Retry failed pages with exponential backoff
   - Handle rate limiting gracefully
   - Log all errors with context
   - Alert on critical failures

4. **Professional Features**
   - Progress webhooks for client notifications
   - Crawl scheduling
   - Domain whitelist/blacklist
   - Custom headers and authentication support

### Development Setup

Create this directory structure:
```
docanalyzer/
├── docker-compose.yml (PostgreSQL, Redis only)
├── requirements.txt
├── .env
├── manage.py
├── config/
│   ├── settings.py
│   ├── celery.py
│   └── urls.py
├── core/
├── crawler/
│   ├── models.py
│   ├── tasks.py
│   ├── spiders/
│   │   └── doc_spider.py
│   └── management/commands/
│       └── crawl.py
├── analyzer/
├── reports/
└── dashboard/
```

### Specific Implementation Requirements

1. **Docker Compose Setup**
   - PostgreSQL 16 with persistent volume
   - Redis with persistence enabled
   - Exposed ports for local development
   - Health checks

2. **Celery Configuration**
   - Separate queues for crawling and analysis
   - Result backend in Redis
   - Proper error handling and retries
   - Scheduled tasks support (celery beat)

3. **Scrapy Integration**
   - Integrate with Django models directly
   - Use Redis for distributed crawling (scrapy-redis)
   - Custom pipelines for data cleaning
   - Middleware for JavaScript rendering

4. **Playwright Integration**
   - Render JavaScript-heavy pages on demand
   - Cache rendered content
   - Detect when JavaScript rendering is needed
   - Handle single-page applications

5. **Management Commands**
   Create these Django management commands:
   - `crawl --url=<url> --depth=<n>` - Start a crawl
   - `crawl_status --job=<id>` - Check crawl status
   - `export_crawl --job=<id>` - Export crawl data
   - `analyze_crawl --job=<id>` - Run analysis (placeholder)

### Testing & Monitoring

Include:
- Basic test suite for crawl functionality
- Logging configuration for debugging
- Django admin interface for all models
- Simple dashboard view showing crawl progress
- API endpoint for crawl status

### Performance Requirements
- Handle 50,000 pages without memory issues
- Support resume after interruption
- Concurrent crawling of multiple sites
- Efficient deduplication
- Rate limiting to respect server resources

### Security & Professional Considerations
- User-Agent string identifying the crawler
- Respect rate limits and server load
- Authentication support for protected docs
- No crawling of sensitive URLs (admin, login, etc.)
- Data encryption for client content

## Output Expectations

Build a production-ready foundation that:
1. Can crawl a documentation site completely and professionally
2. Stores all content in a queryable format
3. Provides real-time progress monitoring
4. Handles failures gracefully
5. Can be extended with analysis and reporting features

Focus on robustness and professional polish over features. This needs to work reliably for paying clients, not be a proof-of-concept.

Please implement this system with clear documentation and comments explaining key architectural decisions.
