# analyzer/quick_analyzer.py

"""
Quick analysis that completes in seconds, not minutes.
For full analysis, use DocumentationAnalyzer.
"""

from django.db.models import Count, Avg, Q, F, Sum, Max, Min
from core.models import CrawlJob
from crawler.models import CrawledPage


class QuickAnalyzer:
    """Fast analysis for immediate results"""
    
    def __init__(self, job_id):
        self.job = CrawlJob.objects.get(id=job_id)
        # Use count() instead of loading all pages
        self.page_count = self.job.pages.count()
        
    def analyze(self):
        """Run quick analysis - completes in seconds"""
        
        # Don't print, let the command handle output
        
        # Use aggregation queries only - no iteration!
        insights = self._generate_quick_insights()
        
        # Calculate executive summary
        executive_summary = {
            'total_pages_analyzed': self.page_count,
            'critical_issues_found': len([i for i in insights if i['type'] == 'critical']),
            'quick_wins_available': len([i for i in insights if i['effort'] == 'low']),
            'total_insights': len(insights),
            'estimated_total_value': sum(i.get('estimated_value', 0) for i in insights),
        }
        
        # Generate metrics
        content_metrics = self._quick_content_metrics()
        seo_metrics = self._quick_seo_metrics()
        performance_metrics = self._quick_performance_metrics()
        
        results = {
            'job_id': self.job.id,
            'site_url': self.job.target_url,
            'total_pages': self.page_count,
            'executive_summary': executive_summary,
            'insights': insights,
            'detailed_metrics': {
                'content_quality': content_metrics,
                'seo_opportunities': seo_metrics,
                'performance': performance_metrics,
            },
            'recommendations': self._generate_recommendations(insights),
            'roadmap': self._generate_roadmap(insights),
            # Keep these for backward compatibility
            'content_metrics': content_metrics,
            'seo_metrics': seo_metrics,
            'performance_metrics': performance_metrics,
            'quick_insights': insights,
        }
        
        return results
    
    def _quick_content_metrics(self):
        """Get content metrics without iteration"""
        
        # Single aggregation query
        metrics = self.job.pages.aggregate(
            avg_readability=Avg('readability_score'),
            avg_word_count=Avg('word_count'),
            total_words=Sum('word_count'),
        )
        
        # Count queries (fast with indexes)
        low_readability = self.job.pages.filter(
            readability_score__lt=30
        ).count()
        
        stub_pages = self.job.pages.filter(
            word_count__lt=100
        ).count()
        
        pages_without_examples = self.job.pages.filter(
            has_examples=False
        ).count()
        
        # Add both individual fields and aggregated for compatibility
        metrics['low_readability'] = low_readability
        metrics['low_readability_pages'] = low_readability
        metrics['stub_pages'] = stub_pages
        metrics['pages_without_examples'] = pages_without_examples
        
        return metrics
    
    def _quick_seo_metrics(self):
        """Get SEO metrics without iteration"""
        
        missing_meta_count = self.job.pages.filter(
            Q(meta_description='') | Q(meta_description__isnull=True)
        ).count()
        
        return {
            'missing_titles': self.job.pages.filter(
                Q(title='') | Q(title__isnull=True)
            ).count(),
            
            'missing_meta': missing_meta_count,
            'missing_meta_descriptions': missing_meta_count,  # For report compatibility
            
            'duplicate_pages': self.job.pages.filter(
                is_duplicate=True
            ).count(),
        }
    
    def _quick_performance_metrics(self):
        """Get performance metrics without iteration"""
        
        return self.job.pages.aggregate(
            avg_response_time=Avg('response_time'),
            max_response_time=Max('response_time'),
            avg_page_size=Avg('page_size'),
            slow_pages=Count('id', filter=Q(response_time__gt=2.0)),
            large_pages=Count('id', filter=Q(page_size__gt=500000)),
        )
    
    def _generate_quick_insights(self):
        """Generate top insights quickly with affected pages"""
        
        insights = []
        
        # 1. Missing meta descriptions (SEO)
        missing_meta_qs = self.job.pages.filter(
            Q(meta_description='') | Q(meta_description__isnull=True)
        ).exclude(
            Q(url__icontains='/api/') |  # API docs often don't need meta
            Q(url__endswith='.json') |   # Data files
            Q(url__endswith='.xml')      # Sitemaps, etc
        )
        missing_meta = missing_meta_qs.count()
        
        if missing_meta > 30:  # Lower threshold
            affected_pages = list(missing_meta_qs.values_list('url', flat=True)[:10])
            
            insights.append({
                'type': 'critical',
                'title': f'{missing_meta} pages missing meta descriptions',
                'finding': f'{missing_meta} content pages have no meta description, severely impacting SEO and click-through rates',
                'impact': f'${missing_meta * 100:,.0f} potential SEO value lost annually',
                'effort': 'low',
                'estimated_value': missing_meta * 100,
                'affected_pages': affected_pages,
                'affected_pages_count': missing_meta
            })
        
        # 2. Check for actual API documentation (better detection)
        # Look for pages that have API-related content patterns
        potential_api_pages = self.job.pages.filter(
            Q(url__icontains='/api') | 
            Q(url__icontains='/reference') |
            Q(url__icontains='/endpoint') |
            Q(title__icontains='API') |
            Q(title__icontains='endpoint') |
            Q(main_content__icontains='endpoint') |
            Q(main_content__icontains='POST ') |
            Q(main_content__icontains='GET ') |
            Q(main_content__icontains='PUT ') |
            Q(main_content__icontains='DELETE ')
        ).distinct()
        
        api_count = potential_api_pages.count()
        
        if api_count > 0:
            # Check if any mention authentication
            auth_pages = potential_api_pages.filter(
                Q(main_content__icontains='authentication') |
                Q(main_content__icontains='authorization') |
                Q(main_content__icontains='api key') |
                Q(main_content__icontains='bearer token') |
                Q(main_content__icontains='oauth')
            )
            
            if not auth_pages.exists():
                sample_api_pages = list(potential_api_pages.values_list('url', flat=True)[:5])
                
                insights.append({
                    'type': 'critical',
                    'title': 'API Documentation Missing Authentication Details',
                    'finding': f'Found {api_count} API-related pages, but none explain authentication',
                    'impact': 'Developers cannot integrate without authentication documentation',
                    'effort': 'medium',
                    'estimated_value': 25000,
                    'affected_pages': sample_api_pages,
                    'affected_pages_count': api_count,
                    'note': 'These API pages need authentication documentation or links to it'
                })
            
            # Check for API pages without code examples
            api_without_examples = potential_api_pages.filter(
                has_examples=False
            ).exclude(
                Q(url__icontains='overview') |  # Overview pages might not need examples
                Q(url__icontains='intro')
            )
            api_no_examples_count = api_without_examples.count()
            
            if api_no_examples_count > 5:
                affected_pages = list(api_without_examples.values_list('url', flat=True)[:10])
                
                insights.append({
                    'type': 'critical', 
                    'title': f'{api_no_examples_count} API pages lack code examples',
                    'finding': 'API documentation without code examples makes integration 3x harder',
                    'impact': 'Increased support tickets and longer integration time',
                    'effort': 'medium',
                    'estimated_value': api_no_examples_count * 500,
                    'affected_pages': affected_pages,
                    'affected_pages_count': api_no_examples_count
                })
        
        # 3. Tutorial/Guide pages without code
        tutorial_pages = self.job.pages.filter(
            Q(url__icontains='tutorial') |
            Q(url__icontains='guide') |
            Q(url__icontains='how-to') |
            Q(url__icontains='getting-started') |
            Q(title__icontains='tutorial') |
            Q(title__icontains='guide') |
            Q(title__icontains='how to')
        ).distinct()
        
        tutorials_without_code = tutorial_pages.filter(
            Q(code_blocks__exact={}) | Q(code_blocks__exact=[])
        )
        tutorial_no_code_count = tutorials_without_code.count()
        
        if tutorial_no_code_count > 5:
            affected_pages = list(tutorials_without_code.values_list('url', flat=True)[:10])
            
            insights.append({
                'type': 'warning',
                'title': f'{tutorial_no_code_count} tutorials/guides lack code examples',
                'finding': 'Tutorial pages without code examples fail to provide practical guidance',
                'impact': 'Users cannot follow along, leading to poor adoption',
                'effort': 'medium',
                'estimated_value': tutorial_no_code_count * 400,
                'affected_pages': affected_pages,
                'affected_pages_count': tutorial_no_code_count
            })
        
        # 4. Low readability pages (exclude code-heavy pages)
        low_readability_qs = self.job.pages.filter(
            readability_score__lt=30,
            word_count__gte=200  # Only check substantial pages
        ).exclude(
            Q(url__icontains='/api/') |  # API docs are naturally complex
            Q(url__icontains='/reference/')
        )
        low_readability = low_readability_qs.count()
        
        if low_readability > 10:
            affected_pages = list(low_readability_qs.values_list('url', flat=True)[:10])
            
            insights.append({
                'type': 'warning',
                'title': f'{low_readability} pages are too complex to read',
                'finding': 'Pages with readability scores below 30 frustrate users and increase support burden',
                'impact': f'${low_readability * 50 * 12:,.0f}/year in support costs',
                'effort': 'medium',
                'estimated_value': low_readability * 50 * 12,
                'affected_pages': affected_pages,
                'affected_pages_count': low_readability
            })
        
        # 5. Stub pages (very short content)
        stub_pages_qs = self.job.pages.filter(
            word_count__lt=100
        ).exclude(
            Q(url__endswith='/') |  # Index pages might be short
            Q(url__icontains='index') |
            Q(doc_type='navigation')
        )
        stub_count = stub_pages_qs.count()
        
        if stub_count > 10:
            affected_pages = list(stub_pages_qs.values_list('url', flat=True)[:10])
            
            insights.append({
                'type': 'warning',
                'title': f'{stub_count} stub pages with minimal content',
                'finding': 'Pages with less than 100 words provide little value and hurt SEO',
                'impact': 'Poor user experience and potential Google penalties',
                'effort': 'low',
                'estimated_value': stub_count * 200,
                'affected_pages': affected_pages,
                'affected_pages_count': stub_count
            })
        
        # 6. Dead-end pages (no outgoing links)
        dead_end_pages = self.job.pages.filter(
            depth__gt=0,  # Not the root page
            internal_links__exact=[],
            word_count__gte=300  # Substantial pages that should link somewhere
        ).exclude(
            Q(url__icontains='/changelog') |  # Changelogs might not link
            Q(url__icontains='/release-notes')
        )
        dead_end_count = dead_end_pages.count()
        
        if dead_end_count > 10:
            affected_pages = list(dead_end_pages.values_list('url', flat=True)[:10])
            
            insights.append({
                'type': 'warning',
                'title': f'{dead_end_count} pages are navigation dead-ends',
                'finding': 'Content pages with no links leave users stranded',
                'impact': 'Users abandon documentation when they can\'t navigate further',
                'effort': 'low',
                'estimated_value': dead_end_count * 150,
                'affected_pages': affected_pages,
                'affected_pages_count': dead_end_count
            })
        
        # 7. Missing titles
        missing_titles = self.job.pages.filter(
            Q(title='') | Q(title__isnull=True)
        ).exclude(
            Q(url__endswith='.json') |   # Data files
            Q(url__endswith='.xml'))      # Sitemaps
        
        missing_title_count = missing_titles.count()
        if missing_title_count > 5:
            affected_pages = list(missing_titles.values_list('url', flat=True)[:10])
            
            insights.append({
                'type': 'critical',
                'title': f'{missing_title_count} pages missing page titles',
                'finding': 'Pages without titles cannot be properly indexed or bookmarked',
                'impact': 'Severely reduced discoverability and user navigation',
                'effort': 'low',
                'estimated_value': missing_title_count * 150,
                'affected_pages': affected_pages,
                'affected_pages_count': missing_title_count
            })
        
        # 8. Slow pages
        slow_pages = self.job.pages.filter(
            response_time__gt=2.0  # Over 2 seconds
        )
        slow_count = slow_pages.count()
        
        if slow_count > 10:
            affected_pages = list(slow_pages.values_list('url', flat=True)[:10])
            avg_time = slow_pages.aggregate(Avg('response_time'))['response_time__avg']
            
            insights.append({
                'type': 'warning',
                'title': f'{slow_count} pages load slowly (>{avg_time:.1f}s average)',
                'finding': '40% of users abandon pages that take over 3 seconds to load',
                'impact': 'Lost traffic and poor user experience',
                'effort': 'high',
                'estimated_value': slow_count * 100,
                'affected_pages': affected_pages,
                'affected_pages_count': slow_count
            })
        
        return insights[:10]  # Top 10 insights only
    
    def _generate_recommendations(self, insights):
        """Generate recommendations from insights"""
        recommendations = []
        
        for insight in insights[:5]:  # Top 5 insights as recommendations
            recommendations.append({
                'title': insight['title'],
                'description': insight['impact'],
                'priority': 'high' if insight['type'] == 'critical' else 'medium',
                'effort': insight['effort'],
                'impact': insight['impact']
            })
        
        return recommendations
    
    def _generate_roadmap(self, insights):
        """Generate 30-60-90 day roadmap"""
        
        # Sort insights by effort
        low_effort = [i for i in insights if i['effort'] == 'low']
        medium_effort = [i for i in insights if i['effort'] == 'medium']
        high_effort = [i for i in insights if i.get('effort') == 'high']
        
        return {
            '30_days': [i['title'] for i in low_effort[:3]],
            '60_days': [i['title'] for i in medium_effort[:3]],
            '90_days': [i['title'] for i in high_effort[:2]]
        }

