# crawler/spiders/doc_spider.py

import scrapy
from scrapy.linkextractors import LinkExtractor
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
try:
    import textstat  # type: ignore
except Exception:
    textstat = None  # type: ignore
from crawler.models import CrawledPage, CrawlJob
from crawler.language_detector import detect_language, is_english

class DocSpider(scrapy.Spider):
    name = 'doc_spider'
    
    # Patterns that indicate a site likely needs JavaScript rendering
    JS_INDICATORS = [
        'react', 'vue', 'angular', 'next.js', 'gatsby', 'docusaurus',
        'vuepress', 'vitepress', 'spa'
    ]
    
    def __init__(self, job_id=None, use_playwright=None, capture_html='False', screenshots='False', crawl_config_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job_id = job_id
        self.job = CrawlJob.objects.get(id=job_id)
        self.start_urls = [self.job.target_url]
        self.allowed_domains = [urlparse(self.job.target_url).netloc]
        
        # Load crawl configuration if provided
        self.crawl_config = None
        if crawl_config_id:
            from crawler.models import CrawlConfiguration
            try:
                self.crawl_config = CrawlConfiguration.objects.get(id=crawl_config_id)
                self.logger.info(f"Using crawl configuration: {self.crawl_config.name}")
            except CrawlConfiguration.DoesNotExist:
                self.logger.warning(f"Crawl configuration {crawl_config_id} not found. Using defaults.")
        
        # Auto-detect or use explicit setting
        self.use_playwright = use_playwright
        if self.use_playwright is None:
            # Auto-detect based on config or initial request
            self.use_playwright = self.job.config.get('use_playwright', 'auto')
        
        # Feature flags
        self.capture_html = capture_html.lower() in ('true', '1', 'yes')
        self.screenshots = screenshots.lower() in ('true', '1', 'yes')
        
        # If screenshots are enabled, force Playwright usage
        if self.screenshots and self.use_playwright == 'never':
            self.logger.warning("Screenshots require Playwright. Enabling Playwright.")
            self.use_playwright = 'always'
        elif self.screenshots and self.use_playwright == 'auto':
            self.use_playwright = 'always'
        
        # Track if we've detected JS requirement
        self.needs_js = None  # Will be set after first page
        
        # Screenshot counter for unique filenames
        self.screenshot_count = 0
        
    def start_requests(self):
        """Generate initial requests with optional Playwright"""
        for url in self.start_urls:
            # For now we use standard Scrapy requests; Playwright is handled separately
            yield scrapy.Request(url, callback=self.parse, dont_filter=True)
    
    def parse(self, response):
        """Enhanced parsing with documentation-specific extraction"""
        
        # Detect if JavaScript rendering is needed (first page only)
        if self.needs_js is None and self.use_playwright == 'auto':
            self.needs_js = self._detect_javascript_requirement(response)
            if self.needs_js:
                self.logger.info(f"Detected JavaScript requirement. Using Playwright for all pages.")
            else:
                self.logger.info(f"No JavaScript requirement detected. Using standard requests.")
        
        # Create BeautifulSoup object for advanced extraction
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract main content ONCE (extract_main_content modifies soup via decompose())
        # Store it to avoid calling multiple times on destroyed soup
        main_content = self.extract_main_content(soup)
        
        # Extract all the enhanced fields
        extracted_data = {
            'job_id': self.job_id,
            'url': response.url,
            'depth': response.meta.get('depth', 0),
            'status_code': response.status,
            'response_time': response.meta.get('download_latency', 0),
            'page_size': len(response.body),
            
            # Basic content
            'title': self.extract_title(soup, response),
            'meta_description': self.extract_meta_description(soup),
            'main_content': main_content,
            
            # Raw HTML capture (if enabled)
            'raw_html': response.text if self.capture_html else None,
            
            # Documentation classification (pass main_content to avoid re-extracting from destroyed soup)
            'doc_type': self.classify_doc_type(soup, response.url, main_content),
            'version_info': self.extract_version_info(soup, response.url),
            
            # Navigation context
            'breadcrumb': self.extract_breadcrumb(soup),
            'navigation_title': self.extract_nav_title(soup),
            
            # Structured content
            'headers': self.extract_headers_hierarchy(soup),
            'internal_links': self.extract_internal_links(soup, response.url),
            'external_links': self.extract_external_links(soup),
            'code_blocks': self.extract_code_blocks(soup),
            'tables': self.extract_tables(soup),
            'images': self.extract_images(soup),
            
            # Sections and TOC
            'sections': self.extract_sections(soup),
            'table_of_contents': self.extract_toc(soup),
            
            # Special content
            'api_endpoints': self.extract_api_endpoints(soup),
            'warnings': self.extract_callouts(soup, 'warning'),
            'tips': self.extract_callouts(soup, 'tip'),
            'questions': self.extract_questions(soup),
            
            # SEO
            'og_tags': self.extract_og_tags(soup),
            'schema_markup': self.extract_schema_markup(soup),
            'canonical_url': self.extract_canonical_url(soup),
            
            # Quality metrics (reuse main_content instead of calling extract_main_content again)
            'word_count': len(main_content.split()),
            'readability_score': self.calculate_readability(main_content),
            'estimated_reading_time': self.estimate_reading_time(main_content),
            
            # Feature detection (pass main_content where needed to avoid re-extracting)
            'has_table_of_contents': self.detect_toc(soup),
            'has_search': self.detect_search(soup),
            'has_examples': self.detect_examples(soup, main_content),
            'has_videos': self.detect_videos(soup),
            'has_copy_buttons': self.detect_copy_buttons(soup),
            
            # Content hash for deduplication
            'content_hash': self.generate_content_hash(main_content),
            
            # Language detection
            'detected_language': detect_language(main_content),
        }
        
        # ========================================
        # AI-ERA SEO FIELDS
        # ========================================
        
        # E-E-A-T signals
        author_freshness = self.extract_author_and_freshness(soup)
        extracted_data.update(author_freshness)
        
        # Self-contained context (RAG optimization)
        prereq_context = self.extract_prerequisites_and_context(soup)
        extracted_data.update(prereq_context)
        
        # Q&A pairs
        qa_pairs = self.extract_qa_pairs(soup)
        extracted_data['qa_pairs'] = qa_pairs
        extracted_data['qa_count'] = len(qa_pairs)
        
        # External references
        ref_data = self.extract_external_references(soup)
        extracted_data.update(ref_data)
        
        # Version compatibility
        version_data = self.extract_version_compatibility(soup)
        extracted_data.update(version_data)
        
        # Accessibility signals
        accessibility_data = self.extract_accessibility_signals(soup)
        extracted_data.update(accessibility_data)
        
        # Interactive features
        interactive_data = self.extract_interactive_features(soup)
        extracted_data.update(interactive_data)
        
        # Comprehensiveness metrics
        comprehensiveness_data = self.extract_comprehensiveness_metrics(soup)
        extracted_data.update(comprehensiveness_data)
        
        # Content quality signals
        quality_data = self.extract_content_quality_signals(soup)
        extracted_data.update(quality_data)
        
        # Performance & resources
        performance_data = self.extract_performance_resources(soup)
        extracted_data.update(performance_data)
        
        # Technical SEO details
        tech_seo_data = self.extract_technical_seo_details(soup)
        extracted_data.update(tech_seo_data)
        
        # NOTE: Screenshot capture is now handled asynchronously via Celery
        # to avoid blocking the spider or dealing with async Playwright here.
        # The pipeline will enqueue screenshot tasks when job.config['screenshots'] is True.
        extracted_data['screenshot_path'] = None
        
        # Yield the item instead of saving directly - let the pipeline handle it
        yield extracted_data
        
        # Follow links
        for link in self.extract_links_to_follow(soup, response):
            yield response.follow(link, self.parse)
    
    def extract_title(self, soup, response):
        """Extract page title with fallbacks"""
        # Try multiple sources
        title = None
        
        # 1. Try <title> tag
        if soup.title:
            title = soup.title.string
        
        # 2. Try h1
        if not title and soup.h1:
            title = soup.h1.get_text(strip=True)
        
        # 3. Try meta og:title
        if not title:
            og_title = soup.find('meta', property='og:title')
            if og_title:
                title = og_title.get('content')
        
        return title or ''
    
    def extract_main_content(self, soup):
        """Extract main content, removing navigation and boilerplate"""
        # Use crawl configuration if available
        if self.crawl_config:
            # First, remove excluded elements
            if self.crawl_config.exclude_selectors:
                for selector in self.crawl_config.exclude_selectors:
                    try:
                        for elem in soup.select(selector):
                            elem.decompose()
                    except Exception as e:
                        self.logger.warning(f"Error removing selector '{selector}': {e}")
            
            # Then extract main content using the configured selector
            if self.crawl_config.main_content_selector:
                try:
                    main = soup.select_one(self.crawl_config.main_content_selector)
                    if main:
                        text = main.get_text(separator=' ', strip=True)
                        text = ' '.join(text.split())
                        return text
                    else:
                        self.logger.warning(f"Main content selector '{self.crawl_config.main_content_selector}' found no matches")
                except Exception as e:
                    self.logger.warning(f"Error using main content selector: {e}")
        
        # Fallback to default extraction
        # Remove script and style elements
        for script in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            script.decompose()
        
        # Try to find main content area - prioritize semantic tags, then IDs, then classes
        # IDs are more specific than classes, so check them first
        main = soup.find('main') or \
               soup.find('article') or \
               soup.find('div', id=re.compile('mainContent|main-content|article|content', re.I)) or \
               soup.find('div', class_=re.compile('^(main|article|post-content|entry-content|markdown-body)$', re.I))
        
        if main:
            text = main.get_text(separator=' ', strip=True)
        else:
            text = soup.get_text(separator=' ', strip=True)
        
        # Clean up whitespace
        text = ' '.join(text.split())
        return text
    
    def extract_headers_hierarchy(self, soup):
        """Extract all headers with hierarchy"""
        headers = {}
        for level in range(1, 7):
            headers[f'h{level}'] = []
            for header in soup.find_all(f'h{level}'):
                text = header.get_text(strip=True)
                header_id = header.get('id', '')
                headers[f'h{level}'].append({
                    'text': text,
                    'id': header_id,
                    'level': level
                })
        return headers
    
    def extract_code_blocks(self, soup):
        """Extract code blocks with language detection"""
        code_blocks = []
        
        # Find <pre><code> blocks
        for pre in soup.find_all('pre'):
            code = pre.find('code')
            if code:
                # Try to detect language
                language = ''
                if 'class' in code.attrs:
                    classes = code['class']
                    for cls in classes:
                        if 'language-' in cls:
                            language = cls.replace('language-', '')
                            break
                
                code_text = code.get_text()
                
                code_blocks.append({
                    'language': language or 'plaintext',
                    'content': code_text,
                    'line_count': len(code_text.splitlines()),
                    'has_copy_button': pre.find('button', class_=re.compile('copy')) is not None,
                })
        
        # Also find inline code
        inline_count = len([
            tag for tag in soup.find_all('code') 
            if tag.parent and tag.parent.name != 'pre'
        ])
        
        return {
            'blocks': code_blocks,
            'inline_count': inline_count,
            'total_blocks': len(code_blocks)
        }
    
    def classify_doc_type(self, soup, url, main_content=None):
        """Classify the type of documentation page"""
        url_lower = url.lower()
        title_lower = (soup.title.string if soup.title else '').lower()
        
        # URL patterns
        if '/api/' in url_lower or '/reference/' in url_lower:
            return 'api_reference'
        elif '/tutorial' in url_lower or '/getting-started' in url_lower:
            return 'tutorial'
        elif '/guide' in url_lower:
            return 'guide'
        elif '/changelog' in url_lower or '/release/' in url_lower:
            return 'changelog'
        elif '/faq' in url_lower:
            return 'faq'
        elif '/example' in url_lower or '/demo' in url_lower:
            return 'example'
        
        # Content patterns (use passed main_content instead of extracting again)
        content = (main_content or '').lower()
        if 'endpoint' in content and 'request' in content and 'response' in content:
            return 'api_reference'
        elif 'step 1' in content or 'first,' in content:
            return 'tutorial'
        
        return 'unknown'
    
    def extract_internal_links(self, soup, current_url):
        """Extract internal links with context"""
        internal_links = []
        domain = urlparse(current_url).netloc
        
        for link in soup.find_all('a', href=True):
            href = urljoin(current_url, link['href'])
            
            if domain in urlparse(href).netloc:
                # Get surrounding context
                parent = link.parent
                context = parent.get_text(strip=True)[:200] if parent else ''
                
                internal_links.append({
                    'url': href,
                    'anchor_text': link.get_text(strip=True),
                    'title': link.get('title', ''),
                    'context': context,
                    'is_navigation': link.find_parent('nav') is not None,
                })
        
        return internal_links
    
    def extract_sections(self, soup):
        """Extract logical sections based on headers"""
        sections = []
        current_section = None
        
        for element in soup.find_all(['h1', 'h2', 'h3', 'p', 'pre', 'ul', 'ol']):
            if element.name in ['h1', 'h2', 'h3']:
                # Start new section
                if current_section:
                    sections.append(current_section)
                
                current_section = {
                    'heading': element.get_text(strip=True),
                    'level': element.name,
                    'content': '',
                    'word_count': 0,
                    'has_code': False,
                    'has_list': False,
                }
            elif current_section:
                # Add to current section
                if element.name == 'pre':
                    current_section['has_code'] = True
                elif element.name in ['ul', 'ol']:
                    current_section['has_list'] = True
                
                text = element.get_text(strip=True)
                current_section['content'] += text + ' '
                current_section['word_count'] = len(current_section['content'].split())
        
        if current_section:
            sections.append(current_section)
        
        return sections
    
    def extract_api_endpoints(self, soup):
        """Extract API endpoint definitions"""
        endpoints = []
        
        # Look for common API documentation patterns
        # Pattern 1: <code>GET /api/users</code>
        for code in soup.find_all('code'):
            text = code.get_text(strip=True)
            if re.match(r'^(GET|POST|PUT|DELETE|PATCH)\s+/', text):
                endpoints.append({
                    'method_and_path': text,
                    'context': code.parent.get_text(strip=True)[:200]
                })
        
        # Pattern 2: In tables
        for table in soup.find_all('table'):
            headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
            if 'endpoint' in headers or 'method' in headers:
                for row in table.find_all('tr')[1:]:  # Skip header row
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        endpoints.append({
                            'method': cells[0].get_text(strip=True),
                            'path': cells[1].get_text(strip=True)
                        })
        
        return endpoints
    
    def calculate_readability(self, text):
        """Calculate Flesch Reading Ease score"""
        if not text or len(text) < 100:
            return None
        
        try:
            return textstat.flesch_reading_ease(text)
        except:
            return None
    
    def estimate_reading_time(self, text):
        """Estimate reading time in minutes"""
        words = len(text.split())
        # Average reading speed: 200-250 words per minute
        return max(1, round(words / 225))
    
    def extract_callouts(self, soup, callout_type):
        """Extract warning/tip/note callouts"""
        callouts = []
        
        # Common patterns for callouts
        patterns = {
            'warning': ['warning', 'danger', 'caution', 'alert'],
            'tip': ['tip', 'hint', 'info', 'note'],
        }
        
        for pattern in patterns.get(callout_type, []):
            # Check divs with classes
            for div in soup.find_all('div', class_=re.compile(pattern, re.I)):
                callouts.append({
                    'type': callout_type,
                    'content': div.get_text(strip=True)[:500]
                })
            
            # Check blockquotes
            for blockquote in soup.find_all('blockquote'):
                text = blockquote.get_text(strip=True)
                if pattern.lower() in text.lower()[:50]:
                    callouts.append({
                        'type': callout_type,
                        'content': text[:500]
                    })
        
        return callouts
    
    def detect_examples(self, soup, main_content=None):
        """Detect if page has examples"""
        content = (main_content or '').lower()
        indicators = ['example', 'sample', 'demo', 'try it', 'playground']
        return any(indicator in content for indicator in indicators)
    
    def extract_meta_description(self, soup):
        """Extract meta description"""
        meta = soup.find('meta', attrs={'name': 'description'}) or \
               soup.find('meta', attrs={'property': 'og:description'})
        return meta.get('content', '') if meta else ''
    
    def extract_version_info(self, soup, url):
        """Extract version information"""
        # Look for version in URL or content
        import re
        version_match = re.search(r'v?(\d+\.\d+(?:\.\d+)?)', url)
        if version_match:
            return version_match.group(1)
        return ''
    
    def extract_breadcrumb(self, soup):
        """Extract breadcrumb navigation"""
        breadcrumbs = []
        # Look for common breadcrumb patterns
        nav = soup.find('nav', attrs={'aria-label': re.compile('breadcrumb', re.I)}) or \
              soup.find('ol', class_=re.compile('breadcrumb', re.I))
        if nav:
            for link in nav.find_all('a'):
                breadcrumbs.append(link.get_text(strip=True))
        return breadcrumbs
    
    def extract_nav_title(self, soup):
        """Extract navigation title"""
        # Try to find a navigation-specific title
        nav_link = soup.find('a', class_=re.compile('active|current', re.I))
        if nav_link:
            return nav_link.get_text(strip=True)
        return ''
    
    def extract_external_links(self, soup):
        """Extract external links"""
        external_links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('http') and urlparse(href).netloc not in self.allowed_domains:
                external_links.append({
                    'url': href,
                    'anchor_text': link.get_text(strip=True)
                })
        return external_links
    
    def extract_tables(self, soup):
        """Extract tables"""
        tables = []
        for table in soup.find_all('table'):
            headers = [th.get_text(strip=True) for th in table.find_all('th')]
            rows = []
            for tr in table.find_all('tr')[1:]:  # Skip header row
                cells = [td.get_text(strip=True) for td in tr.find_all('td')]
                if cells:
                    rows.append(cells)
            if headers or rows:
                tables.append({'headers': headers, 'rows': rows[:10]})  # Limit rows
        return tables
    
    def extract_images(self, soup):
        """Extract images"""
        images = []
        for img in soup.find_all('img'):
            images.append({
                'src': img.get('src', ''),
                'alt': img.get('alt', ''),
                'title': img.get('title', '')
            })
        return images[:20]  # Limit to 20 images
    
    def extract_toc(self, soup):
        """Extract table of contents"""
        toc = []
        # Look for TOC nav or aside
        toc_nav = soup.find('nav', id=re.compile('toc', re.I)) or \
                  soup.find('aside', class_=re.compile('toc', re.I))
        if toc_nav:
            for link in toc_nav.find_all('a'):
                toc.append({
                    'text': link.get_text(strip=True),
                    'href': link.get('href', '')
                })
        return toc
    
    def extract_questions(self, soup):
        """Extract questions from content"""
        questions = []
        text = soup.get_text()
        # Simple question detection
        import re
        question_pattern = r'([A-Z][^.!?]*\?)'
        matches = re.findall(question_pattern, text)
        return matches[:10]  # Limit to 10 questions
    
    def extract_og_tags(self, soup):
        """Extract Open Graph tags"""
        og_tags = {}
        for meta in soup.find_all('meta', property=re.compile('^og:')):
            prop = meta.get('property', '')
            content = meta.get('content', '')
            if prop and content:
                og_tags[prop] = content
        return og_tags
    
    def extract_schema_markup(self, soup):
        """Extract JSON-LD schema markup"""
        schemas = []
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                schemas.append(json.loads(script.string))
            except:
                pass
        return schemas
    
    def extract_canonical_url(self, soup):
        """Extract canonical URL"""
        link = soup.find('link', rel='canonical')
        return link.get('href', '') if link else ''
    
    def detect_toc(self, soup):
        """Detect if page has table of contents"""
        return soup.find('nav', id=re.compile('toc', re.I)) is not None or \
               soup.find('aside', class_=re.compile('toc', re.I)) is not None
    
    def detect_search(self, soup):
        """Detect if page has search"""
        return soup.find('input', type='search') is not None or \
               soup.find('input', attrs={'role': 'search'}) is not None
    
    def detect_videos(self, soup):
        """Detect if page has videos"""
        return soup.find('video') is not None or \
               soup.find('iframe', src=re.compile('youtube|vimeo', re.I)) is not None
    
    def detect_copy_buttons(self, soup):
        """Detect copy buttons for code blocks"""
        return soup.find('button', class_=re.compile('copy', re.I)) is not None
    
    def generate_content_hash(self, content):
        """Generate SHA256 hash of content"""
        import hashlib
        return hashlib.sha256(content.encode()).hexdigest()
    
    def capture_screenshot(self, response):
        """Capture screenshot using Playwright and save to disk with URL-based directory structure"""
        import os
        import asyncio
        from django.conf import settings
        
        # Debug logging to file
        def debug_log(msg):
            with open('/Users/steve.bresnick/Projects/docsscraper/screenshot_debug.log', 'a') as f:
                from datetime import datetime
                f.write(f"{datetime.now()}: {msg}\n")
        
        # Get the Playwright page from response meta
        page = response.meta.get('playwright_page')
        if not page:
            debug_log(f"No Playwright page available for: {response.url}")
            return None
        
        try:
            debug_log(f"Starting capture for: {response.url}")
            debug_log(f"Page object type: {type(page)}")
            
            # Parse URL to create hierarchical directory structure
            parsed_url = urlparse(response.url)
            domain = parsed_url.netloc.replace('www.', '')  # Remove www prefix
            url_path = parsed_url.path.strip('/')
            
            # Build directory structure: screenshots/<domain>/<path>/
            if url_path:
                screenshot_dir = os.path.join(settings.BASE_DIR, 'screenshots', domain, url_path)
            else:
                # Root path
                screenshot_dir = os.path.join(settings.BASE_DIR, 'screenshots', domain)
            
            os.makedirs(screenshot_dir, exist_ok=True)
            debug_log(f"Created directory: {screenshot_dir}")
            
            # Always use 'screenshot.png' as filename
            filename = 'screenshot.png'
            filepath = os.path.join(screenshot_dir, filename)
            
            # Take screenshot - handle async page properly
            debug_log(f"About to call page.screenshot() to: {filepath}")
            
            # Check if page is async (has _impl attribute)
            if hasattr(page, '_impl'):
                # It's an async page, we need to await it
                debug_log("Detected async page, using asyncio.run()")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(page.screenshot(path=filepath, full_page=True))
                finally:
                    loop.close()
            else:
                # Sync page
                debug_log("Using sync page.screenshot()")
                page.screenshot(path=filepath, full_page=True)
            
            debug_log(f"page.screenshot() call completed")
            
            # Verify file exists
            if os.path.exists(filepath):
                size = os.path.getsize(filepath)
                debug_log(f"SUCCESS: File exists with size {size} bytes: {filepath}")
            else:
                debug_log(f"ERROR: File doesn't exist after screenshot call!")
            
            # Return relative path for storage in DB
            if url_path:
                relative_path = os.path.join('screenshots', domain, url_path, filename)
            else:
                relative_path = os.path.join('screenshots', domain, filename)
            
            return relative_path
            
        except Exception as e:
            debug_log(f"EXCEPTION for {response.url}: {str(e)}")
            import traceback
            debug_log(f"Traceback: {traceback.format_exc()}")
            return None
    
    def extract_links_to_follow(self, soup, response):
        """Extract links to follow for crawling (simple, config-free version)."""
        links = []

        for link in soup.find_all('a', href=True):
            href = link['href']

            # Convert relative URLs to absolute
            absolute_url = urljoin(response.url, href)
            parsed = urlparse(absolute_url)

            # Only follow links within allowed domains
            if parsed.netloc in self.allowed_domains:
                # Skip anchors, downloads, and non-HTML
                if not href.startswith('#') and not any(
                    href.endswith(ext) for ext in ['.pdf', '.zip', '.png', '.jpg', '.gif']
                ):
                    links.append(absolute_url)

        # Remove duplicates
        return list(set(links))
    
    def _detect_javascript_requirement(self, response):
        """
        Detect if a page requires JavaScript rendering.
        Returns True if JS is likely needed, False otherwise.
        """
        html = response.text.lower()
        
        # Check 1: Look for JS framework indicators
        for indicator in self.JS_INDICATORS:
            if indicator in html:
                self.logger.debug(f"Found JS framework indicator: {indicator}")
                return True
        
        # Check 2: Check if there's minimal content but lots of script tags
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style tags for content analysis
        for script in soup(['script', 'style']):
            script.decompose()
        
        text_content = soup.get_text(strip=True)
        script_tags = len(soup.find_all('script'))
        
        # If there are many scripts but little visible content, likely needs JS
        if script_tags > 5 and len(text_content) < 500:
            self.logger.debug(f"Found {script_tags} scripts but only {len(text_content)} chars of content")
            return True
        
        # Check 3: Look for common SPA root elements with minimal content
        root_ids = ['root', 'app', 'app-root', '__next', '__nuxt']
        for root_id in root_ids:
            root_element = soup.find(id=root_id)
            if root_element and len(root_element.get_text(strip=True)) < 100:
                self.logger.debug(f"Found SPA root element: #{root_id} with minimal content")
                return True
        
        # Check 4: Look for data attributes that indicate client-side rendering
        if soup.find_all(attrs={'data-reactroot': True}) or \
           soup.find_all(attrs={'data-react-helmet': True}) or \
           soup.find_all(attrs={'data-vue-ssr': True}):
            self.logger.debug("Found client-side rendering data attributes")
            return True
        
        # Default: doesn't appear to need JS
        return False
    
    # ========================================
    # AI-ERA SEO EXTRACTION METHODS
    # ========================================
    
    def extract_author_and_freshness(self, soup):
        """Extract E-E-A-T signals: author info and content freshness"""
        data = {
            'author': '',
            'author_bio': '',
            'published_date': '',
            'last_updated_text': '',
            'reviewed_by': '',
        }
        
        # Extract author
        author_meta = soup.find('meta', attrs={'name': 'author'})
        if author_meta:
            data['author'] = author_meta.get('content', '')
        
        # Look for author links
        author_link = soup.find('a', rel='author')
        if author_link and not data['author']:
            data['author'] = author_link.get_text(strip=True)
        
        # Look for author bio/byline
        author_bio = soup.find(class_=re.compile('author-bio|byline', re.I))
        if author_bio:
            data['author_bio'] = author_bio.get_text(strip=True)[:500]
        
        # Extract dates
        for time_tag in soup.find_all('time'):
            datetime_val = time_tag.get('datetime', '')
            if datetime_val:
                if 'published' in time_tag.get('class', []) or 'published' in time_tag.get('itemprop', ''):
                    data['published_date'] = datetime_val
                elif 'updated' in time_tag.get('class', []) or 'modified' in time_tag.get('itemprop', ''):
                    data['last_updated_text'] = datetime_val
        
        # Text patterns for dates
        content_text = soup.get_text()
        
        # "Last updated: January 15, 2024"
        updated_match = re.search(r'(?:last updated|updated on|modified):\s*([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})', content_text, re.I)
        if updated_match and not data['last_updated_text']:
            data['last_updated_text'] = updated_match.group(1)
        
        # "Published: January 15, 2024"
        published_match = re.search(r'(?:published|written):\s*([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})', content_text, re.I)
        if published_match and not data['published_date']:
            data['published_date'] = published_match.group(1)
        
        # "Reviewed by [name]"
        reviewed_match = re.search(r'reviewed by:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', content_text, re.I)
        if reviewed_match:
            data['reviewed_by'] = reviewed_match.group(1)
        
        return data
    
    def extract_prerequisites_and_context(self, soup):
        """Extract self-contained context for RAG optimization - IMPROVED VERSION"""
        prerequisites = []
        learning_objectives = []
        next_steps = []
        
        # Get all text content for broad searching
        full_text = soup.get_text().lower()
        
        # More comprehensive patterns
        prereq_patterns = [
            'before you begin', 'prerequisites', 'requirements', 'what you need',
            'you will need', 'you\'ll need', 'assumes you have', 'required',
            'things you need', 'before starting'
        ]
        
        learning_patterns = [
            'learning objectives', 'you will learn', 'you\'ll learn',
            'what you\'ll learn', 'what you will learn', 'objectives',
            'in this guide', 'this guide covers', 'this tutorial covers',
            'by the end', 'after completing'
        ]
        
        next_steps_patterns = [
            'next steps', 'what\'s next', 'where to go', 'continue learning',
            'further reading', 'what to do next'
        ]
        
        # Strategy 1: Look for headings (original approach)
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5']):
            heading_text = heading.get_text(strip=True).lower()
            
            # Prerequisites
            if any(pattern in heading_text for pattern in prereq_patterns):
                content = self._extract_content_after_element(heading, soup)
                if content:
                    prerequisites.append(content[:1000])
            
            # Learning objectives
            if any(pattern in heading_text for pattern in learning_patterns):
                content = self._extract_content_after_element(heading, soup)
                if content:
                    learning_objectives.append(content[:1000])
            
            # Next steps
            if any(pattern in heading_text for pattern in next_steps_patterns):
                content = self._extract_content_after_element(heading, soup)
                if content:
                    next_steps.append(content[:1000])
        
        # Strategy 2: Look for bold/strong text followed by patterns
        for strong in soup.find_all(['strong', 'b']):
            strong_text = strong.get_text(strip=True).lower()
            
            if any(pattern in strong_text for pattern in learning_patterns):
                # Get the next sibling content (could be list, paragraph, etc.)
                content = self._extract_content_after_element(strong, soup)
                if content and content not in learning_objectives:
                    learning_objectives.append(content[:1000])
            
            if any(pattern in strong_text for pattern in prereq_patterns):
                content = self._extract_content_after_element(strong, soup)
                if content and content not in prerequisites:
                    prerequisites.append(content[:1000])
        
        # Strategy 3: Look for lists that might contain learning objectives/prerequisites
        # Find paragraphs or text containing these patterns, then check for lists nearby
        for p in soup.find_all(['p', 'div']):
            p_text = p.get_text(strip=True).lower()
            
            # Check for learning objective patterns in paragraph
            if any(pattern in p_text for pattern in learning_patterns):
                # Look for a list immediately after this paragraph
                next_list = p.find_next_sibling(['ul', 'ol'])
                if next_list:
                    list_content = next_list.get_text(strip=True)
                    if list_content and list_content not in learning_objectives:
                        learning_objectives.append(list_content[:1000])
            
            # Check for prerequisite patterns
            if any(pattern in p_text for pattern in prereq_patterns):
                next_list = p.find_next_sibling(['ul', 'ol'])
                if next_list:
                    list_content = next_list.get_text(strip=True)
                    if list_content and list_content not in prerequisites:
                        prerequisites.append(list_content[:1000])
        
        # Strategy 4: Look directly in list items for objective-like content
        # Sometimes objectives are just in a list at the top without any label
        if not learning_objectives:
            # Look for lists near the top of the content that might be objectives
            main = soup.find('main') or soup.find('article') or soup
            early_lists = main.find_all(['ul', 'ol'], limit=3)  # Check first 3 lists
            
            for ul in early_lists:
                items = ul.find_all('li')
                if 2 <= len(items) <= 10:  # Reasonable number of objectives
                    # Check if items look like learning objectives
                    items_text = [li.get_text(strip=True).lower() for li in items]
                    
                    # Look for objective-like language in list items
                    objective_indicators = [
                        'understand', 'learn', 'describe', 'explain', 'identify',
                        'demonstrate', 'apply', 'configure', 'create', 'use'
                    ]
                    
                    matching_items = sum(
                        1 for item in items_text
                        if any(indicator in item for indicator in objective_indicators)
                    )
                    
                    # If >50% of items have objective language, it's probably objectives
                    if matching_items / len(items) > 0.5:
                        list_content = ul.get_text(strip=True)
                        if list_content not in learning_objectives:
                            learning_objectives.append(list_content[:1000])
                            break  # Found it, don't keep looking
        
        return {
            'prerequisites': prerequisites,
            'learning_objectives': learning_objectives,
            'next_steps': next_steps,
            'has_prerequisites': len(prerequisites) > 0,
            'has_learning_objectives': len(learning_objectives) > 0,
            'has_next_steps': len(next_steps) > 0,
        }
    
    def _extract_content_after_element(self, element, soup):
        """Helper method to extract content after a given element"""
        content_parts = []
        
        # Get parent if this is an inline element (like strong)
        if element.name in ['strong', 'b', 'em', 'i']:
            parent = element.parent
            if parent:
                # Get text after the strong tag in the same paragraph
                remaining_text = ''.join([str(s) for s in element.next_siblings if isinstance(s, str) or s.name != 'script'])
                if remaining_text.strip():
                    content_parts.append(remaining_text.strip())
                
                # Also check next siblings of the parent
                start_element = parent
            else:
                start_element = element
        else:
            start_element = element
        
        # Get content from next siblings
        for sibling in start_element.find_next_siblings():
            # Stop at next heading of same or higher level
            if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                if sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    sibling_level = int(sibling.name[1])
                    element_level = int(element.name[1])
                    if sibling_level <= element_level:
                        break
            elif sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                # For non-heading elements, stop at any heading
                break
            
            # Collect text from appropriate elements
            if sibling.name in ['p', 'ul', 'ol', 'div']:
                text = sibling.get_text(strip=True)
                if text:
                    content_parts.append(text)
            
            # Don't collect too much
            if len(content_parts) >= 5:
                break
        
        return ' '.join(content_parts).strip()
    
    def extract_qa_pairs(self, soup):
        """Extract explicit question-answer pairs for AI training"""
        qa_pairs = []
        
        # Pattern 1: FAQ sections
        faq_section = soup.find(['section', 'div'], class_=re.compile('faq', re.I))
        if faq_section:
            # Look for dt/dd pairs (definition lists)
            for dt, dd in zip(faq_section.find_all('dt'), faq_section.find_all('dd')):
                qa_pairs.append({
                    'question': dt.get_text(strip=True),
                    'answer': dd.get_text(strip=True)[:500],
                    'format': 'faq'
                })
            
            # Look for h3/h4 followed by paragraphs
            for heading in faq_section.find_all(['h3', 'h4']):
                question = heading.get_text(strip=True)
                if '?' in question:
                    # Get following paragraph as answer
                    answer_elem = heading.find_next_sibling(['p', 'div'])
                    if answer_elem:
                        qa_pairs.append({
                            'question': question,
                            'answer': answer_elem.get_text(strip=True)[:500],
                            'format': 'faq'
                        })
        
        # Pattern 2: Questions in headings with answers below
        for heading in soup.find_all(['h2', 'h3', 'h4']):
            heading_text = heading.get_text(strip=True)
            if '?' in heading_text:
                # Collect content until next heading of same level
                answer_parts = []
                for sibling in heading.find_next_siblings():
                    if sibling.name == heading.name:  # Same heading level
                        break
                    if sibling.name in ['p', 'ul', 'ol', 'pre']:
                        answer_parts.append(sibling.get_text(strip=True))
                
                if answer_parts:
                    qa_pairs.append({
                        'question': heading_text,
                        'answer': ' '.join(answer_parts[:3])[:500],
                        'format': 'heading'
                    })
        
        return qa_pairs[:20]  # Limit to 20 Q&A pairs
    
    def extract_external_references(self, soup):
        """Extract citations and references to authoritative sources"""
        references = []
        
        # Find "References", "Sources", "See also" sections
        ref_patterns = ['references', 'sources', 'see also', 'further reading', 'learn more']
        
        for heading in soup.find_all(['h2', 'h3', 'h4']):
            heading_text = heading.get_text(strip=True).lower()
            
            if any(pattern in heading_text for pattern in ref_patterns):
                # Get links in this section
                ref_section = heading.find_next_sibling(['ul', 'ol', 'div'])
                if ref_section:
                    for link in ref_section.find_all('a', href=True):
                        href = link['href']
                        if href.startswith('http'):  # External links only
                            references.append({
                                'url': href,
                                'title': link.get_text(strip=True),
                                'type': 'explicit_reference'
                            })
        
        return {
            'external_references': references[:20],
            'reference_count': len(references),
            'has_references': len(references) > 0,
        }
    
    def extract_version_compatibility(self, soup):
        """Extract version and compatibility information"""
        compatibility = {
            'product_versions': [],
            'language_versions': [],
            'platform_requirements': [],
            'deprecation_warnings': [],
        }
        
        content_text = soup.get_text()
        
        # Find version compatibility patterns
        # "Python 3.8+", "Node.js 16 or higher"
        version_patterns = [
            r'(Python|Node\.?js|Ruby|Java|Go|PHP)\s+(\d+(?:\.\d+)*)\+?',
            r'(requires?|needs?)\s+([A-Z][a-z]+)\s+(\d+(?:\.\d+)*)',
        ]
        
        for pattern in version_patterns:
            matches = re.findall(pattern, content_text, re.I)
            for match in matches[:10]:  # Limit matches
                if len(match) >= 2:
                    compatibility['language_versions'].append(' '.join(match))
        
        # Find deprecation warnings
        deprecation_patterns = [
            r'deprecated in (\d+\.\d+)',
            r'will be removed in (\d+\.\d+)',
            r'⚠️.*deprecated',
        ]
        
        for pattern in deprecation_patterns:
            matches = re.findall(pattern, content_text, re.I)
            compatibility['deprecation_warnings'].extend(matches[:5])
        
        # Find version badges or indicators
        for elem in soup.find_all(['span', 'div'], class_=re.compile('version|badge', re.I)):
            text = elem.get_text(strip=True)
            if re.match(r'v?\d+\.\d+', text):
                compatibility['product_versions'].append(text)
        
        return {
            'version_compatibility': compatibility,
            'product_versions': compatibility['product_versions'][:10],
            'language_versions': compatibility['language_versions'][:10],
            'deprecation_warnings': compatibility['deprecation_warnings'][:10],
            'has_deprecation_warning': len(compatibility['deprecation_warnings']) > 0,
        }
    
    def extract_accessibility_signals(self, soup):
        """Extract accessibility and UX quality signals"""
        
        # Count ARIA labels
        aria_elements = soup.find_all(attrs={'aria-label': True})
        aria_labelledby = soup.find_all(attrs={'aria-labelledby': True})
        
        # Check alt text quality
        images = soup.find_all('img')
        images_with_alt = [img for img in images if img.get('alt')]
        meaningful_alt = [img for img in images_with_alt if len(img.get('alt', '').strip()) > 5]
        
        alt_text_quality = len(meaningful_alt) / len(images) if images else 0
        
        # Check heading hierarchy
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        heading_levels = [int(h.name[1]) for h in headings]
        
        # Valid hierarchy: levels should not skip (e.g., h1 -> h3 is invalid)
        valid_hierarchy = True
        for i in range(len(heading_levels) - 1):
            if heading_levels[i + 1] - heading_levels[i] > 1:
                valid_hierarchy = False
                break
        
        # Check for skip links
        skip_links = soup.find_all('a', href='#main') or soup.find_all('a', class_=re.compile('skip', re.I))
        
        # Check viewport meta tag
        viewport_meta = soup.find('meta', attrs={'name': 'viewport'})
        
        return {
            'aria_labels_count': len(aria_elements) + len(aria_labelledby),
            'alt_text_quality_score': round(alt_text_quality, 2),
            'heading_structure_valid': valid_hierarchy,
            'has_skip_links': len(skip_links) > 0,
            'mobile_viewport_meta': viewport_meta is not None,
        }
    
    def extract_interactive_features(self, soup):
        """Detect interactive and dynamic content features"""
        
        features = {
            'has_code_playground': False,
            'has_api_explorer': False,
            'has_feedback_mechanism': False,
            'has_version_switcher': False,
            'has_community_comments': False,
        }
        
        # Code playgrounds: CodePen, JSFiddle, CodeSandbox embeds
        playground_domains = ['codepen.io', 'jsfiddle.net', 'codesandbox.io', 'replit.com']
        for iframe in soup.find_all('iframe', src=True):
            if any(domain in iframe['src'] for domain in playground_domains):
                features['has_code_playground'] = True
                break
        
        # API Explorer: Swagger UI, interactive API docs
        if soup.find(class_=re.compile('swagger|api-explorer|try-it', re.I)):
            features['has_api_explorer'] = True
        
        # Feedback mechanisms: "Was this helpful?" buttons
        feedback_patterns = ['helpful', 'feedback', 'rate this', 'thumbs']
        for elem in soup.find_all(['button', 'div'], class_=True):
            classes = ' '.join(elem.get('class', [])).lower()
            if any(pattern in classes for pattern in feedback_patterns):
                features['has_feedback_mechanism'] = True
                break
        
        # Version switcher
        if soup.find(class_=re.compile('version-switch|version-select', re.I)) or \
           soup.find('select', id=re.compile('version', re.I)):
            features['has_version_switcher'] = True
        
        # Community comments: Disqus, Discourse embeds
        if soup.find(id='disqus_thread') or soup.find(class_=re.compile('discourse|comments', re.I)):
            features['has_community_comments'] = True
        
        return features
    
    def extract_comprehensiveness_metrics(self, soup):
        """Calculate content comprehensiveness scores"""
        
        sections = self.extract_sections(soup)
        
        # Count different content types
        diagrams = soup.find_all('img', alt=re.compile('diagram|flow|architecture', re.I))
        videos = soup.find_all('video') or soup.find_all('iframe', src=re.compile('youtube|vimeo', re.I))
        interactive_demos = soup.find_all(class_=re.compile('demo|interactive|playground', re.I))
        
        # Check for troubleshooting
        troubleshooting = any(
            pattern in heading.get_text().lower()
            for heading in soup.find_all(['h2', 'h3'])
            for pattern in ['troubleshoot', 'common issues', 'debugging', 'problems', 'errors']
        )
        
        # Calculate example to explanation ratio
        code_blocks = len(soup.find_all('pre'))
        paragraphs = len(soup.find_all('p'))
        example_ratio = code_blocks / paragraphs if paragraphs > 0 else 0
        
        return {
            'sections_count': len(sections),
            'has_diagrams': len(diagrams) > 0,
            'has_videos': len(videos) > 0,
            'has_troubleshooting': troubleshooting,
            'example_to_explanation_ratio': round(example_ratio, 2),
            'content_type_diversity': sum([
                len(diagrams) > 0,
                len(videos) > 0,
                len(interactive_demos) > 0,
                code_blocks > 0,
                len(soup.find_all('table')) > 0,
            ]),
        }
    
    def extract_content_quality_signals(self, soup):
        """Extract content quality and structure signals"""
        
        # Check for TL;DR
        has_tldr = bool(soup.find(text=re.compile('tl;?dr', re.I)))
        
        # Count paragraphs and lists
        paragraphs = soup.find_all('p')
        lists = soup.find_all(['ul', 'ol'])
        
        # Calculate average paragraph length
        para_lengths = [len(p.get_text().split()) for p in paragraphs]
        avg_para_length = sum(para_lengths) // len(para_lengths) if para_lengths else 0
        
        # Check for step-by-step instructions
        content_text = soup.get_text().lower()
        has_steps = bool(re.search(r'step \d+|first,|then,|finally,|\d+\.\s+[A-Z]', content_text))
        
        # Count imperative sentences (command verbs)
        imperative_verbs = ['click', 'run', 'install', 'type', 'enter', 'select', 'choose', 'open', 'create', 'add']
        imperative_count = sum(1 for verb in imperative_verbs if verb in content_text)
        
        return {
            'has_tldr': has_tldr,
            'paragraph_count': len(paragraphs),
            'list_count': len(lists),
            'average_paragraph_length': avg_para_length,
            'has_step_by_step': has_steps,
            'imperative_sentence_count': min(imperative_count, 100),  # Cap at 100
        }
    
    def extract_performance_resources(self, soup):
        """Extract performance and resource information"""
        
        # Count scripts and stylesheets
        scripts = soup.find_all('script', src=True)
        stylesheets = soup.find_all('link', rel='stylesheet')
        
        # Identify third-party scripts
        third_party = []
        for script in scripts:
            src = script.get('src', '')
            if src.startswith('http'):
                domain = urlparse(src).netloc
                if domain and domain not in third_party:
                    third_party.append(domain)
        
        return {
            'script_count': len(scripts),
            'stylesheet_count': len(stylesheets),
            'third_party_scripts': third_party[:20],  # Limit to 20
        }
    
    def extract_technical_seo_details(self, soup):
        """Extract additional technical SEO signals"""
        
        # Extract hreflang tags
        hreflang = {}
        for link in soup.find_all('link', rel='alternate', hreflang=True):
            hreflang[link.get('hreflang')] = link.get('href', '')
        
        # Detect schema types
        schema_types = []
        schemas = self.extract_schema_markup(soup)
        for schema in schemas:
            if isinstance(schema, dict) and '@type' in schema:
                schema_type = schema['@type']
                if isinstance(schema_type, str):
                    schema_types.append(schema_type)
                elif isinstance(schema_type, list):
                    schema_types.extend(schema_type)
        
        return {
            'hreflang_tags': hreflang,
            'structured_data_types': schema_types[:10],
            'has_breadcrumb_schema': 'BreadcrumbList' in schema_types,
            'has_article_schema': any(t in schema_types for t in ['Article', 'TechArticle', 'BlogPosting']),
            'has_howto_schema': 'HowTo' in schema_types,
            'has_faq_schema': any(t in schema_types for t in ['FAQPage', 'Question']),
        }