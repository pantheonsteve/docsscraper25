# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a professional web scraping system for analyzing enterprise documentation sites. It crawls documentation sites (5k-50k pages), stores the data, and enables analysis reports for B2B SaaS consulting clients. The business model is "crawl first, analyze later" - comprehensive data collection followed by multiple analyses on the same dataset.

## Architecture

### Core Stack
- **Django**: Central orchestration layer (all components as Django apps)
- **Scrapy**: Web crawling engine with scrapy-redis for distributed crawling
- **PostgreSQL 16**: Persistent storage (Docker container)
- **Redis**: URL frontier, task queue, deduplication (Docker container)
- **Celery**: Background task processing with separate queues for crawling and analysis
- **Playwright**: JavaScript rendering for SPAs and dynamic content
- **Python 3.11+**: Local venv (NOT containerized)

### Django Apps Structure
1. **core**: Shared models (Client, CrawlJob), authentication, base functionality
2. **crawler**: Scrapy integration, CrawledPage model, crawl orchestration
3. **analyzer**: LLM analysis tasks (placeholder)
4. **reports**: Report generation (placeholder)
5. **dashboard**: Web UI for monitoring and client access

### Data Models

**CrawlJob**: Orchestrates crawl execution
- Tracks status (pending/running/complete/failed)
- Stores config (depth_limit, patterns, auth)
- Maintains stats (pages_crawled, errors)

**CrawledPage**: Stores extracted content
- Main content (cleaned text, no nav/headers/footers)
- Structured data: code_blocks, internal_links, external_links, headers (h1-h6)
- Metadata: title, meta_description, response_time, page_size
- content_hash for deduplication
- Optional raw_html for reprocessing

### Storage Strategy
- **Redis**: URL frontier (pending), deduplication set, real-time stats
- **PostgreSQL**: Crawled content, analysis results, client data
- **Filesystem**: Optional HTML archive for reprocessing

## Development Commands

### Initial Setup
```bash
# Start infrastructure
docker-compose up -d

# Setup Python environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Database migrations
python manage.py migrate

# Run Celery worker
celery -A config worker -l info

# Run Celery beat (scheduler)
celery -A config beat -l info

# Run development server
python manage.py runserver
```

### Crawl Management Commands
```bash
# Start a crawl
python manage.py crawl --url=<url> --depth=<n>

# Check crawl status
python manage.py crawl_status --job=<id>

# Export crawl data
python manage.py export_crawl --job=<id>

# Run analysis (placeholder)
python manage.py analyze_crawl --job=<id>
```

### Testing
```bash
# Run test suite
python manage.py test

# Run specific app tests
python manage.py test crawler
```

## Crawler Specifications

The Scrapy spider (`crawler/spiders/doc_spider.py`) implements:
1. **Breadth-first crawl strategy** with configurable depth limits
2. **Polite crawling**: 1-2 requests/second, respects robots.txt
3. **Content extraction**: Removes nav/headers/footers, extracts main content
4. **Code block detection**: Language-aware extraction
5. **Link graph**: Tracks internal and external links
6. **JavaScript handling**: Playwright integration for dynamic content
7. **Resume capability**: Redis-backed state for restart
8. **Deduplication**: Content-hash based
9. **Domain scoping**: Stays within original domain unless configured otherwise

## Key Implementation Notes

### Scrapy-Django Integration
- Scrapy spider imports Django models directly
- Pipeline saves to PostgreSQL via Django ORM
- Settings configured in `config/settings.py`

### Celery Task Queues
- `crawling` queue: Long-running crawl tasks
- `analysis` queue: CPU-intensive analysis tasks
- Redis as result backend

### Playwright Integration
- Detects JavaScript-rendered pages automatically
- Caches rendered content to avoid re-rendering
- Handles SPAs and infinite-scroll patterns

### Error Handling
- Exponential backoff for failed pages
- Graceful rate-limit handling
- Comprehensive logging with context
- Critical failure alerts

## Professional Crawling Requirements

### Politeness
- User-Agent identifies the crawler and business
- Rate limiting configurable per site
- Respects Retry-After headers
- Avoids crawling admin/login/sensitive URLs

### Robustness
- Must handle 50,000 pages without memory issues
- Support interruption and resume
- Concurrent crawling of multiple sites
- Efficient deduplication at scale

### Client Features
- Real-time progress webhooks
- Crawl scheduling
- Domain whitelist/blacklist
- Custom headers and authentication support

## Extension Points

### Analysis Pipeline (Future)
The `analyzer` app is a placeholder for LLM-based analysis:
- Documentation structure analysis
- Content gap detection
- API reference completeness
- Tutorial quality scoring

### Reporting (Future)
The `reports` app will generate client deliverables:
- PDF/HTML report generation
- Visualization of crawl results
- Comparison reports (before/after)

## Critical Considerations

1. **Data retention**: Client content must be encrypted
2. **Performance**: Large crawls (50k pages) must complete in <24 hours
3. **Monitoring**: Real-time progress visibility is essential
4. **Resume capability**: Crawls must survive interruptions
5. **Professional polish**: This serves paying clients, not a POC
