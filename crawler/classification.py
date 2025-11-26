# crawler/classification.py

"""
Improved document classification for documentation sites.
This provides more accurate categorization than simple URL matching.
"""

import re


class DocumentClassifier:
    """Classify documentation pages into meaningful categories"""
    
    # Keywords that strongly indicate each doc type
    API_KEYWORDS = [
        'endpoint', 'request', 'response', 'authentication', 'authorization',
        'api key', 'bearer token', 'oauth', 'webhook', 'rest api', 'graphql',
        'rate limit', 'status code', 'http method', 'payload', 'schema',
        'curl', 'postman', 'api reference'
    ]
    
    TUTORIAL_KEYWORDS = [
        'tutorial', 'getting started', 'quick start', 'step by step',
        'how to', 'walkthrough', 'learn', 'first steps', 'beginner',
        'follow along', 'exercise', 'hands-on', 'workshop'
    ]
    
    GUIDE_KEYWORDS = [
        'guide', 'best practices', 'overview', 'introduction', 'concepts',
        'architecture', 'workflow', 'process', 'methodology', 'approach',
        'strategy', 'planning', 'design', 'implementation'
    ]
    
    TROUBLESHOOTING_KEYWORDS = [
        'troubleshoot', 'debug', 'error', 'problem', 'issue', 'fix',
        'solve', 'resolution', 'workaround', 'common problems', 'faq',
        'known issues', 'diagnostics'
    ]
    
    CONFIGURATION_KEYWORDS = [
        'configuration', 'settings', 'options', 'parameters', 'environment',
        'variables', 'config file', 'setup', 'installation', 'deployment',
        'yaml', 'json config', 'ini file'
    ]
    
    @classmethod
    def classify(cls, url, title, content, headers=None, code_blocks=None):
        """
        Classify a documentation page based on multiple signals.
        
        Returns: doc_type string and confidence score (0-1)
        """
        url_lower = url.lower()
        title_lower = (title or '').lower()
        content_lower = (content or '').lower()[:5000]  # First 5000 chars for performance
        
        scores = {
            'api_reference': 0,
            'tutorial': 0,
            'guide': 0,
            'troubleshooting': 0,
            'configuration': 0,
            'changelog': 0,
            'example': 0,
            'landing': 0,
            'unknown': 0
        }
        
        # URL-based scoring (weight: 0.4)
        url_weight = 0.4
        if any(x in url_lower for x in ['/api/', '/reference/', '/endpoints/']):
            scores['api_reference'] += url_weight
        elif any(x in url_lower for x in ['/tutorial', '/getting-started', '/quickstart']):
            scores['tutorial'] += url_weight
        elif any(x in url_lower for x in ['/guide', '/guides/', '/how-to']):
            scores['guide'] += url_weight
        elif any(x in url_lower for x in ['/troubleshoot', '/debug', '/errors', '/faq']):
            scores['troubleshooting'] += url_weight
        elif any(x in url_lower for x in ['/config', '/settings', '/setup', '/install']):
            scores['configuration'] += url_weight
        elif any(x in url_lower for x in ['/changelog', '/release', '/updates']):
            scores['changelog'] += url_weight
        elif any(x in url_lower for x in ['/example', '/demo', '/sample']):
            scores['example'] += url_weight
        
        # Title-based scoring (weight: 0.3)
        title_weight = 0.3
        if any(x in title_lower for x in ['api', 'endpoint', 'reference']):
            scores['api_reference'] += title_weight
        elif any(x in title_lower for x in ['tutorial', 'getting started', 'quickstart']):
            scores['tutorial'] += title_weight
        elif any(x in title_lower for x in ['guide', 'how to', 'overview']):
            scores['guide'] += title_weight
        elif any(x in title_lower for x in ['troubleshoot', 'debug', 'error', 'fix']):
            scores['troubleshooting'] += title_weight
        elif any(x in title_lower for x in ['config', 'setting', 'setup', 'install']):
            scores['configuration'] += title_weight
        elif any(x in title_lower for x in ['changelog', 'release', 'update', 'version']):
            scores['changelog'] += title_weight
        
        # Content-based scoring (weight: 0.3)
        content_weight = 0.3
        
        # Count keyword occurrences
        api_score = sum(1 for kw in cls.API_KEYWORDS if kw in content_lower) / len(cls.API_KEYWORDS)
        tutorial_score = sum(1 for kw in cls.TUTORIAL_KEYWORDS if kw in content_lower) / len(cls.TUTORIAL_KEYWORDS)
        guide_score = sum(1 for kw in cls.GUIDE_KEYWORDS if kw in content_lower) / len(cls.GUIDE_KEYWORDS)
        troubleshooting_score = sum(1 for kw in cls.TROUBLESHOOTING_KEYWORDS if kw in content_lower) / len(cls.TROUBLESHOOTING_KEYWORDS)
        config_score = sum(1 for kw in cls.CONFIGURATION_KEYWORDS if kw in content_lower) / len(cls.CONFIGURATION_KEYWORDS)
        
        scores['api_reference'] += api_score * content_weight
        scores['tutorial'] += tutorial_score * content_weight
        scores['guide'] += guide_score * content_weight
        scores['troubleshooting'] += troubleshooting_score * content_weight
        scores['configuration'] += config_score * content_weight
        
        # Special patterns
        if re.search(r'(GET|POST|PUT|DELETE|PATCH)\s+/', content):
            scores['api_reference'] += 0.2
        
        if re.search(r'step\s+\d+|first\s+step|next\s+step', content_lower):
            scores['tutorial'] += 0.2
        
        if 'table of contents' in content_lower and len(content) > 2000:
            scores['guide'] += 0.1
        
        # Code block analysis
        if code_blocks:
            if isinstance(code_blocks, dict) and code_blocks.get('total_blocks', 0) > 3:
                scores['example'] += 0.1
                if any('curl' in str(block).lower() for block in code_blocks.get('blocks', [])):
                    scores['api_reference'] += 0.1
        
        # Determine the winning category
        max_score = max(scores.values())
        if max_score < 0.2:  # No strong signal
            return 'unknown', max_score
        
        doc_type = max(scores, key=scores.get)
        confidence = scores[doc_type]
        
        # Special cases
        if url == '/' or url.endswith('/index.html'):
            return 'landing', 1.0
        
        if len(content) < 200:
            return 'navigation', 0.8
        
        return doc_type, confidence
