# DocAnalyzer - Professional Documentation Crawler

A production-ready web scraping system for analyzing enterprise documentation sites. Built with Django, Scrapy, and Celery for professional B2B SaaS documentation analysis services.

## Features

- **Professional Web Crawling**: Polite, breadth-first crawling with robots.txt compliance
- **Intelligent Content Extraction**: Removes navigation/headers/footers, extracts main content
- **Code Block Detection**: Identifies and extracts code samples with language detection
- **Link Graph Building**: Tracks internal and external link relationships
- **Deduplication**: Content-hash based duplicate detection
- **JavaScript Support**: Playwright integration for dynamic content
- **Resume Capability**: Redis-backed state for crawl interruption recovery
- **Real-time Monitoring**: Web dashboard and API for progress tracking
- **Background Processing**: Celery tasks for long-running crawls (up to 24 hours)
- **Export Functionality**: Export crawled data to JSON or CSV
- **Client Management**: Multi-client support with webhook notifications

## Architecture

### Core Stack
- **Django 4.2+**: Central orchestration and data management
- **Scrapy**: Web crawling engine with custom spider
- **PostgreSQL 16**: Persistent data storage
- **Redis**: Task queue, URL frontier, and deduplication
- **Celery**: Background task processing
- **Playwright**: JavaScript rendering for dynamic sites
- **Python 3.11+**: Local virtual environment

### Django Apps
1. **core**: Client and CrawlJob models, shared functionality
2. **crawler**: Scrapy spider, CrawledPage model, crawl management
3. **analyzer**: Analysis tasks (placeholder for LLM features)
4. **reports**: Report generation (placeholder)
5. **dashboard**: Web UI for monitoring and client access

## Quick Start

### Prerequisites
- Python 3.11+
- Podman Desktop and podman-compose
- Git

### Installation

1. **Clone the repository**
```bash
cd docsscraper
```

2. **Start infrastructure (PostgreSQL and Redis)**
```bash
podman-compose up -d
```

3. **Set up Python environment**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

4. **Install Playwright browsers**
```bash
playwright install chromium
```

5. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your settings
```

6. **Run database migrations**
```bash
python manage.py migrate
```

7. **Create a superuser**
```bash
python manage.py createsuperuser
```

8. **Start the development server**
```bash
python manage.py runserver
```

9. **Start Celery worker (in a separate terminal)**
```bash
cd /Users/steve.bresnick/Projects/docsscraper
source .venv/bin/activate

# Recommended: listen on all queues (required for screenshots)
celery -A config worker -l info -Q celery,crawling,analysis
```

10. **Optional: Start Celery beat for scheduled tasks**
```bash
cd /Users/steve.bresnick/Projects/docsscraper
source .venv/bin/activate
celery -A config beat -l info
```

## Usage

### Starting a Crawl via Command Line

```bash
# Basic crawl
python manage.py crawl --url=https://docs.example.com

# Advanced options
python manage.py crawl \
  --url=https://docs.example.com \
  --client="Example Corp" \
  --depth=10 \
  --domains=example.com,docs.example.com \
  --playwright=auto \
  --async

# Playwright options for JavaScript rendering:
#   --playwright=auto   (default) Auto-detect if JS rendering is needed
#   --playwright=always Force Playwright for all pages (slower but handles SPAs)
#   --playwright=never  Disable Playwright (faster, standard HTTP requests only)
```

### Checking Crawl Status

```bash
# Human-readable output
python manage.py crawl_status --job=1

# JSON output
python manage.py crawl_status --job=1 --json
```

### Celery Worker Cheatsheet

From the project root:

```bash
# Start worker (all queues: default, crawling, analysis)
celery -A config worker -l info -Q celery,crawling,analysis

# See active queues
celery -A config inspect active_queues

# See active tasks
celery -A config inspect active

# See queued tasks
celery -A config inspect reserved

# Stop all workers (development only)
pkill -f "celery -A config worker"
```

### Exporting Crawl Data

```bash
# Export to JSON
python manage.py export_crawl --job=1 --format=json --output=crawl_data.json

# Export to CSV
python manage.py export_crawl --job=1 --format=csv --output=crawl_data.csv

# Include raw HTML
python manage.py export_crawl --job=1 --format=json --include-html --output=full_export.json
```

### Using the API

**Start a crawl:**
```bash
curl -X POST http://localhost:8000/api/crawler/start/ \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 1,
    "target_url": "https://docs.example.com",
    "config": {
      "depth_limit": 5,
      "allowed_domains": ["docs.example.com"]
    }
  }'
```

**Check crawl status:**
```bash
curl http://localhost:8000/api/crawler/status/1/
```

### Using the Dashboard

1. Access the dashboard at `http://localhost:8000/`
2. View real-time crawl statistics
3. Monitor job progress
4. Browse crawled pages
5. View error reports

### Using the Admin Interface

1. Access Django admin at `http://localhost:8000/admin/`
2. Manage clients, jobs, and crawled pages
3. View detailed statistics
4. Configure crawl settings

## Configuration

### Environment Variables

Key environment variables (see `.env.example` for full list):

- `SECRET_KEY`: Django secret key (change in production!)
- `DEBUG`: Debug mode (False in production)
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `CRAWLER_USER_AGENT`: Bot identification string
- `CRAWLER_POLITENESS_DELAY`: Delay between requests (seconds)
- `CRAWLER_CONCURRENT_REQUESTS`: Max concurrent requests
- `CRAWLER_DEFAULT_DEPTH_LIMIT`: Default crawl depth
- `OPENAI_API_KEY`: API key for generating embeddings with text-embedding-3-small

### Crawler Settings

The crawler respects the following configuration options (set per job):

- `depth_limit`: Maximum crawl depth (default: 5)
- `allowed_domains`: List of domains to crawl
- `url_patterns`: Regex patterns for URL filtering
- `authentication`: Custom headers/auth for protected docs

## Data Models

### CrawlJob
Orchestrates crawl execution:
- Tracks status (pending/running/completed/failed)
- Stores configuration and statistics
- Links to Client and CrawledPages

### CrawledPage
Stores extracted content:
- Main content (cleaned text)
- Structured data (headers, code blocks, links)
- Metadata (response time, page size, depth)
- Content hash for deduplication

### Client
Represents service clients:
- Contact information
- Webhook URL for notifications
- Links to all crawl jobs

## Development

### Project Structure
```
docsscraper/
├── config/              # Django configuration
├── core/                # Core models and shared functionality
├── crawler/             # Scrapy spider and crawl management
│   ├── spiders/         # Scrapy spiders
│   ├── pipelines/       # Data processing pipelines
│   └── management/      # Django management commands
├── analyzer/            # Analysis features (placeholder)
├── reports/             # Report generation (placeholder)
├── dashboard/           # Web UI
└── docker-compose.yml   # Infrastructure setup
```

### Running Tests
```bash
python manage.py test
```

### Code Style
The project follows Django best practices and PEP 8 style guidelines.

## Production Deployment

### Checklist
1. Set `DEBUG=False` in environment
2. Change `SECRET_KEY` to a secure random value
3. Configure `ALLOWED_HOSTS`
4. Set up proper database credentials
5. Configure Redis with persistence
6. Set up SSL/TLS for web traffic
7. Configure proper logging
8. Set up monitoring and alerting
9. Configure backup strategy
10. Set `ENCRYPTION_KEY` for client data

### Recommended Setup
- Use a process manager like systemd or Supervisor for Celery workers
- Use Gunicorn or uWSGI for serving Django
- Use Nginx as reverse proxy
- Set up database connection pooling
- Configure Redis with AOF persistence
- Implement log rotation
- Set up error tracking (e.g., Sentry)

## Scaling Considerations

### For Large Crawls (50k+ pages)
- Increase Celery worker count
- Use Redis Cluster for distributed state
- Configure database connection pooling
- Enable Scrapy's scrapy-redis for distributed crawling
- Consider splitting crawls by subdomain/path

### Performance Tuning
- Adjust `CRAWLER_CONCURRENT_REQUESTS` based on target site capacity
- Tune `CRAWLER_POLITENESS_DELAY` for balance between speed and politeness
- Configure PostgreSQL connection pooling
- Enable database query optimization
- Use Redis persistence strategically

## JavaScript Rendering with Playwright

### Overview
The crawler includes intelligent JavaScript rendering via Playwright, supporting modern documentation sites built with React, Vue, Next.js, Gatsby, and other JavaScript frameworks.

### Rendering Modes

**Auto-detect (default):**
```bash
python manage.py crawl --url=https://docs.example.com --playwright=auto
```
- Automatically detects if JavaScript rendering is needed
- Checks first page for JS framework indicators (React, Vue, Angular, etc.)
- Analyzes content-to-script ratio
- Looks for SPA root elements (`#root`, `#app`, `__next`, etc.)
- Falls back to standard HTTP requests if JS not needed (faster)

**Always:**
```bash
python manage.py crawl --url=https://docs.example.com --playwright=always
```
- Forces Playwright for all pages
- Recommended for known SPAs or dynamic sites
- Slower but most reliable for JavaScript-heavy sites
- Waits for network to be idle before extracting content

**Never:**
```bash
python manage.py crawl --url=https://docs.example.com --playwright=never
```
- Disables JavaScript rendering completely
- Uses standard HTTP requests only
- Fastest option for static HTML sites
- Won't capture dynamically loaded content

### When to Use Each Mode

**Use `--playwright=auto` (default) when:**
- You're not sure if the site needs JS rendering
- You want optimal performance with automatic detection
- Crawling mixed content (some pages static, some dynamic)

**Use `--playwright=always` when:**
- Documentation is a known SPA (React, Vue, Angular, etc.)
- Content consistently loads via JavaScript
- Auto-detection misses dynamic content
- Site heavily relies on client-side rendering

**Use `--playwright=never` when:**
- Site is pure HTML (WordPress, Jekyll, Hugo, etc.)
- Maximum speed is required
- You've confirmed no JS rendering is needed
- Crawling API documentation with static HTML

### Performance Considerations

| Mode | Speed | Resource Usage | Reliability |
|------|-------|----------------|-------------|
| Never | ⚡⚡⚡ Fastest | Low | High (for static) |
| Auto | ⚡⚡ Fast | Medium | High |
| Always | ⚡ Slower | High | Highest (for JS) |

**Tips:**
- Auto-detect adds minimal overhead (only first page analyzed)
- Playwright uses ~100-200MB RAM per concurrent browser
- Consider reducing concurrent requests when using `--playwright=always`
- Playwright automatically skips images, fonts, and stylesheets for speed

### Configuration via API

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

## Troubleshooting

### Common Issues

**Crawl not starting:**
- Check Celery worker is running
- Verify Redis connection
- Check Django logs for errors

**Playwright browser not found:**
- Run `playwright install chromium` in your virtual environment
- Ensure Chromium downloaded successfully (~150MB)
- Check `~/.cache/ms-playwright/` for installed browsers

**Memory issues:**
- Reduce `CRAWLER_CONCURRENT_REQUESTS`
- Use `--playwright=auto` or `--playwright=never` instead of `always`
- Enable incremental crawling
- Configure Scrapy memory limits

**Slow crawling:**
- Use `--playwright=never` if site doesn't need JS
- Increase `CRAWLER_CONCURRENT_REQUESTS` (with caution for Playwright)
- Reduce `CRAWLER_POLITENESS_DELAY`
- Check target site response times

**Empty content with Playwright:**
- Site may have bot detection - check logs for errors
- Try adjusting `PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT`
- Some sites block headless browsers

**Database connection errors:**
- Verify PostgreSQL is running
- Check database credentials
- Ensure migrations are applied

## License

Proprietary - All rights reserved

## Support

For issues and questions, please contact the development team.
