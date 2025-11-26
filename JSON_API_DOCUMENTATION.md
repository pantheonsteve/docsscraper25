# JSON API Documentation

## Overview

Each crawled page has a comprehensive JSON view that exposes all metadata, content, and analysis data stored in the database.

## Access Methods

### 1. HTML View (Human-Readable)

**URL Format:** `http://localhost:8000/page/<page_id>/json/`

**Example:** http://localhost:8000/page/1161/json/

This provides a web interface with:
- Pretty-printed, syntax-highlighted JSON
- Copy to clipboard button
- Download raw JSON button
- Back navigation to page detail

### 2. API Endpoint (Machine-Readable)

**URL Format:** `http://localhost:8000/page/<page_id>/json/?format=raw`

**Example:** http://localhost:8000/page/1161/json/?format=raw

Returns pure JSON response with `Content-Type: application/json`, suitable for:
- API integration
- Programmatic access
- Data export
- RAG system ingestion

## JSON Structure

The JSON response includes the following top-level sections:

### Basic Information
```json
{
  "id": 1161,
  "url": "https://developer.dynatrace.com/",
  "title": "Home | Dynatrace Developer",
  "meta_description": "...",
  "status_code": 200,
  "depth": 0,
  "content_hash": "abc123..."
}
```

### Job & Client
```json
{
  "job": {
    "id": 42,
    "name": "Dynatrace Docs Crawl",
    "target_url": "https://developer.dynatrace.com",
    "status": "completed",
    "created_at": "2025-11-25T12:00:00Z"
  },
  "client": {
    "id": 1,
    "name": "Dynatrace",
    "domain": "dynatrace.com"
  }
}
```

### Classification
```json
{
  "classification": {
    "doc_type": "landing",
    "doc_category": "",
    "version_info": "latest",
    "language": "en"
  }
}
```

### Timestamps
```json
{
  "timestamps": {
    "crawled_at": "2025-11-25T12:00:00Z",
    "last_modified": "2025-11-24T10:30:00Z",
    "published_date": "2024-01-15",
    "last_updated_text": "Updated 2 days ago"
  }
}
```

### E-E-A-T (Expertise, Authoritativeness, Trust)
```json
{
  "eeat": {
    "author": "John Doe",
    "author_bio": "Senior Developer Advocate",
    "reviewed_by": "Technical Review Team",
    "external_references": [...],
    "reference_count": 5,
    "has_references": true
  }
}
```

### Navigation
```json
{
  "navigation": {
    "breadcrumb": ["Home", "API", "Authentication"],
    "sidebar_position": 3,
    "navigation_title": "Auth Guide",
    "table_of_contents": [...]
  }
}
```

### Content Structure
```json
{
  "structure": {
    "headers": {
      "h1": ["Main Title"],
      "h2": ["Section 1", "Section 2"],
      "h3": ["Subsection"]
    },
    "sections": [...],
    "internal_links": [...],
    "external_links": [...],
    "code_blocks": [...],
    "tables": [...],
    "images": [...]
  }
}
```

### Special Content
```json
{
  "special_content": {
    "api_endpoints": [
      {
        "method": "GET",
        "path": "/api/v1/users",
        "description": "Get all users"
      }
    ],
    "parameters": [...],
    "warnings": ["Important: This feature is deprecated"],
    "tips": ["Pro tip: Use caching for better performance"],
    "questions": ["How do I authenticate?"]
  }
}
```

### RAG Context (for LLM/AI systems)
```json
{
  "rag_context": {
    "prerequisites": ["Node.js installed", "API key required"],
    "learning_objectives": ["Learn how to authenticate", "Understand API basics"],
    "next_steps": ["Try the advanced tutorial", "Explore API reference"],
    "has_prerequisites": true,
    "has_learning_objectives": true,
    "has_next_steps": true,
    "related_topics": ["OAuth", "API Keys", "Security"]
  }
}
```

### Content Metrics
```json
{
  "metrics": {
    "word_count": 1250,
    "estimated_reading_time": 6,
    "paragraph_count": 15,
    "list_count": 4,
    "sections_count": 8,
    "header_count": 12,
    "code_block_count": 5,
    "internal_link_count": 23,
    "external_link_count": 7,
    "image_count": 3,
    "table_count": 2,
    "reference_count": 5,
    "qa_count": 3,
    "imperative_sentence_count": 12,
    "script_count": 8,
    "stylesheet_count": 3,
    "aria_labels_count": 5
  }
}
```

### Content Quality
```json
{
  "quality": {
    "has_code_examples": true,
    "has_images": true,
    "has_tables": true,
    "has_warnings": true,
    "has_tips": true,
    "has_examples": true,
    "has_tldr": false,
    "has_step_by_step": true,
    "readability_score": 65.5,
    "code_to_text_ratio": 0.15,
    "average_paragraph_length": 45
  }
}
```

### Accessibility
```json
{
  "accessibility": {
    "alt_text_coverage": 0.95,
    "alt_text_quality_score": 0.88,
    "aria_labels_count": 5,
    "has_skip_links": true
  }
}
```

### Interactive Features
```json
{
  "interactive": {
    "has_table_of_contents": true,
    "has_search": true,
    "has_interactive_elements": true,
    "has_videos": false,
    "has_copy_buttons": true,
    "has_code_playground": true,
    "has_api_explorer": true,
    "has_feedback_mechanism": true,
    "has_version_switcher": true,
    "has_community_comments": false
  }
}
```

### SEO
```json
{
  "seo": {
    "og_tags": {
      "og:title": "Developer Guide",
      "og:description": "...",
      "og:image": "..."
    },
    "schema_markup": {...},
    "canonical_url": "https://example.com/guide",
    "meta_keywords": "api, guide, tutorial",
    "hreflang_tags": {
      "en": "https://example.com/en/guide",
      "es": "https://example.com/es/guide"
    },
    "structured_data_types": ["Article", "BreadcrumbList"],
    "has_breadcrumb_schema": true,
    "has_article_schema": true,
    "has_howto_schema": false,
    "has_faq_schema": false
  }
}
```

### Performance
```json
{
  "performance": {
    "response_time": 0.523,
    "page_size": 245678,
    "render_method": "javascript",
    "javascript_render_time": 1.234,
    "script_count": 8,
    "stylesheet_count": 3,
    "third_party_scripts": ["google-analytics.com", "cdn.example.com"]
  }
}
```

### Q&A Pairs
```json
{
  "qa": {
    "qa_pairs": [
      {
        "question": "How do I authenticate?",
        "answer": "Use the API key in the Authorization header..."
      }
    ],
    "qa_count": 3,
    "questions": ["How do I...?", "What is...?", "Why does...?"]
  }
}
```

### Files
```json
{
  "files": {
    "screenshot_path": "screenshots/developer.dynatrace.com/screenshot.png",
    "has_screenshot": true,
    "has_raw_html": false
  }
}
```

### Content (Full Text)
```json
{
  "content": {
    "main_content": "Full cleaned text content of the page...",
    "raw_html": "<html>...</html>"  // null if not captured
  }
}
```

## Use Cases

### 1. RAG (Retrieval-Augmented Generation)
The JSON includes all context needed for LLM ingestion:
- Self-contained content with prerequisites
- Learning objectives and next steps
- Related topics and references
- Q&A pairs
- Structured sections

### 2. Data Export
Export all crawled data for:
- Analytics
- Search indexing
- Data warehousing
- Backup

### 3. API Integration
Integrate crawled documentation into:
- Internal knowledge bases
- Search systems
- AI assistants
- Documentation portals

### 4. Quality Analysis
Analyze documentation quality:
- Readability scores
- Content completeness
- Accessibility metrics
- SEO optimization

## Example Usage

### Python
```python
import requests

page_id = 1161
response = requests.get(f'http://localhost:8000/page/{page_id}/json/?format=raw')
data = response.json()

print(f"Title: {data['title']}")
print(f"Word count: {data['metrics']['word_count']}")
print(f"Code blocks: {data['metrics']['code_block_count']}")
```

### cURL
```bash
curl -s "http://localhost:8000/page/1161/json/?format=raw" | jq .
```

### JavaScript/Node.js
```javascript
const fetch = require('node-fetch');

async function getPageData(pageId) {
  const response = await fetch(
    `http://localhost:8000/page/${pageId}/json/?format=raw`
  );
  const data = await response.json();
  return data;
}

getPageData(1161).then(data => {
  console.log(`Title: ${data.title}`);
  console.log(`Word count: ${data.metrics.word_count}`);
});
```

## Dashboard Integration

The JSON view is accessible from any page detail page via the **"📋 View JSON"** button in the action bar.

### Navigation Flow
1. Go to any page detail: `http://localhost:8000/page/<page_id>/`
2. Click **"📋 View JSON"** button
3. View formatted JSON in browser
4. Use **"Copy to Clipboard"** to copy all data
5. Use **"Download Raw JSON"** to get API response

## Response Format

### HTML View Response
- **Content-Type:** `text/html`
- **Format:** HTML page with pretty-printed JSON in `<pre><code>` block
- **Features:** Copy button, download button, syntax highlighting

### API Response (with `?format=raw`)
- **Content-Type:** `application/json`
- **Format:** Pure JSON
- **Indentation:** 2 spaces
- **Encoding:** UTF-8

## Performance Considerations

- **Response size:** Varies by page content (typically 50KB - 500KB)
- **Generation time:** ~50-200ms per request
- **Caching:** Not currently cached (consider adding for production)
- **Rate limiting:** Not implemented (consider for public API)

## Future Enhancements

Potential improvements:
1. **Pagination** - For very large content sections
2. **Field filtering** - Request only specific sections (e.g., `?fields=metrics,quality`)
3. **Bulk export** - Export multiple pages at once
4. **Webhook integration** - Push JSON to external systems on page update
5. **GraphQL endpoint** - Query specific fields dynamically
6. **Compression** - Gzip compression for large responses
7. **API versioning** - `/api/v1/page/<id>/json/`

## Security Notes

- Currently requires no authentication (dashboard access)
- Consider adding API key authentication for production use
- Rate limiting recommended for public deployments
- Sensitive data should be filtered if exposing publicly

## Related Documentation

- `SCREENSHOT_IMPLEMENTATION.md` - Screenshot feature details
- `DASHBOARD_IMPLEMENTATION_SUMMARY.md` - Dashboard overview
- `README.md` - Project setup and configuration

