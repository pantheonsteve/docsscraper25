# analyzer/documentation_analyzer.py

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from django.db.models import Count, Avg, Q, F, Sum, Min, Max
from django.db.models.functions import Length
from django.utils import timezone
from datetime import timedelta
from collections import Counter, defaultdict
import json
import re
from ddtrace import tracer

from core.models import CrawlJob
from crawler.models import CrawledPage, PageRelationship

@tracer.wrap()
@dataclass
class Insight:
    """Represents a single actionable insight"""
    type: str  # 'critical', 'warning', 'opportunity', 'quick_win'
    category: str  # 'content', 'navigation', 'seo', 'code', 'performance'
    title: str
    finding: str
    impact: str
    effort: str  # 'low', 'medium', 'high'
    priority: int  # 1-10
    affected_pages: List[str]
    estimated_value: Optional[float] = None  # Dollar value if applicable
    
    def to_dict(self):
        return {
            'type': self.type,
            'category': self.category,
            'title': self.title,
            'finding': self.finding,
            'impact': self.impact,
            'effort': self.effort,
            'priority': self.priority,
            'affected_pages_count': len(self.affected_pages),
            'affected_pages_sample': self.affected_pages[:5],  # First 5 URLs
            'estimated_value': self.estimated_value
        }

@tracer.wrap()
class DocumentationAnalyzer:
    """
    Main analyzer class that generates insights from crawled documentation.
    This is your money-making engine - it turns raw data into client value.
    """
    
    def __init__(self, job_id: int):
        self.job = CrawlJob.objects.get(id=job_id)
        self.pages = self.job.pages.all()
        self.insights = []
        
        # Cache frequently used querysets
        self._api_pages = None
        self._tutorial_pages = None
        self._guide_pages = None
        
        # Configuration (could move to settings)
        self.config = {
            'min_readability_score': 50,
            'min_word_count': 100,
            'max_response_time': 2.0,
            'support_ticket_cost': 50,  # Average cost per support ticket
            'developer_hour_cost': 150,  # Cost of developer time per hour
        }
    
    # ==========================================
    # Main Analysis Methods
    # ==========================================
    
    def generate_comprehensive_analysis(self) -> Dict[str, Any]:
        """
        Generate a complete analysis report worth $5k-10k.
        This is your primary deliverable generator.
        """
        self.insights = []  # Reset insights
        
        # Run all analyzers
        content_quality = self.analyze_content_quality()
        navigation_structure = self.analyze_navigation_structure()
        code_coverage = self.analyze_code_coverage()
        seo_opportunities = self.analyze_seo_opportunities()
        api_completeness = self.analyze_api_completeness()
        performance_issues = self.analyze_performance_issues()
        
        # Generate insights from analysis
        self._generate_content_insights(content_quality)
        self._generate_navigation_insights(navigation_structure)
        self._generate_code_insights(code_coverage)
        self._generate_seo_insights(seo_opportunities)
        self._generate_api_insights(api_completeness)
        self._generate_performance_insights(performance_issues)
        
        # Sort insights by priority
        self.insights.sort(key=lambda x: x.priority, reverse=True)
        
        # Calculate overall score
        overall_score = self._calculate_overall_score()
        
        # Generate executive summary
        executive_summary = self._generate_executive_summary()
        
        return {
            'job_id': self.job.id,
            'site_url': self.job.target_url,
            'analysis_date': timezone.now().isoformat(),
            'overall_score': overall_score,
            'executive_summary': executive_summary,
            'insights': [insight.to_dict() for insight in self.insights],
            'detailed_metrics': {
                'content_quality': content_quality,
                'navigation_structure': navigation_structure,
                'code_coverage': code_coverage,
                'seo_opportunities': seo_opportunities,
                'api_completeness': api_completeness,
                'performance': performance_issues,
            },
            'recommendations': self._generate_recommendations(),
            'roadmap': self._generate_30_60_90_day_plan(),
        }
    
    # ==========================================
    # Content Quality Analysis
    # ==========================================
    
    def analyze_content_quality(self) -> Dict[str, Any]:
        """Analyze the quality of documentation content"""
        
        # Readability analysis
        readability_stats = self.pages.aggregate(
            avg_readability=Avg('readability_score'),
            min_readability=Min('readability_score'),
            max_readability=Max('readability_score')
        )
        
        # Find problem pages
        low_readability = self.pages.filter(
            readability_score__lt=self.config['min_readability_score']
        )
        
        stub_pages = self.pages.filter(
            word_count__lt=self.config['min_word_count']
        )
        
        # Pages without examples
        pages_without_examples = self.pages.filter(
            has_examples=False,
            doc_type__in=['tutorial', 'guide', 'api_reference']
        )
        
        # Calculate quality distribution
        quality_distribution = {
            'excellent': self.pages.filter(readability_score__gte=70, word_count__gte=300).count(),
            'good': self.pages.filter(readability_score__gte=50, word_count__gte=200).count(),
            'needs_work': self.pages.filter(
                Q(readability_score__lt=50) | Q(word_count__lt=200)
            ).count(),
            'critical': self.pages.filter(
                readability_score__lt=30, word_count__lt=100
            ).count(),
        }
        
        return {
            'readability_stats': readability_stats,
            'low_readability_pages': low_readability.count(),
            'stub_pages': stub_pages.count(),
            'pages_without_examples': pages_without_examples.count(),
            'quality_distribution': quality_distribution,
            'estimated_support_impact': self._calculate_support_impact(low_readability),
        }
    
    def analyze_navigation_structure(self) -> Dict[str, Any]:
        """Analyze the navigation and information architecture"""
        
        # Find orphaned pages (no incoming links)
        pages_with_incoming = PageRelationship.objects.filter(
            to_page__job=self.job
        ).values_list('to_page_id', flat=True).distinct()
        
        orphaned_pages = self.pages.exclude(
            id__in=pages_with_incoming
        ).exclude(
            url=self.job.target_url  # Exclude the home page
        )
        
        # Find dead ends (no outgoing links)
        dead_ends = self.pages.filter(
            internal_links__exact=[]
        ).exclude(
            doc_type='api_reference'  # API refs often don't have links
        )
        
        # Analyze depth distribution
        depth_distribution = self.pages.values('depth').annotate(
            count=Count('id')
        ).order_by('depth')
        
        # Find circular references
        circular_refs = self._find_circular_references()
        
        # Calculate navigation health score
        nav_health_score = self._calculate_navigation_health()
        
        return {
            'orphaned_pages': orphaned_pages.count(),
            'dead_ends': dead_ends.count(),
            'depth_distribution': list(depth_distribution),
            'circular_references': len(circular_refs),
            'navigation_health_score': nav_health_score,
            'max_depth': self.pages.aggregate(Max('depth'))['depth__max'],
            # Calculate average links manually since internal_links is a JSON field
            'avg_links_per_page': sum(
                len(page.internal_links) if page.internal_links else 0 
                for page in self.pages.all()
            ) / self.pages.count() if self.pages.count() > 0 else 0,
        }
    
    def analyze_code_coverage(self) -> Dict[str, Any]:
        """Analyze code examples and their quality"""
        
        # Collect all code blocks
        all_code_blocks = []
        pages_with_code = 0
        
        for page in self.pages:
            if page.code_blocks and len(page.code_blocks) > 0:
                pages_with_code += 1
                if isinstance(page.code_blocks, list):
                    all_code_blocks.extend(page.code_blocks)
                elif isinstance(page.code_blocks, dict) and 'blocks' in page.code_blocks:
                    all_code_blocks.extend(page.code_blocks['blocks'])
        
        # Language distribution
        language_counter = Counter()
        for block in all_code_blocks:
            if isinstance(block, dict):
                lang = block.get('language', 'unknown')
                language_counter[lang] += 1
        
        # Find API pages without code examples
        api_pages = self.get_api_pages()
        api_without_examples = api_pages.filter(
            Q(code_blocks__exact=[]) | Q(code_blocks__exact={})
        )
        
        # Find tutorials without code
        tutorials = self.get_tutorial_pages()
        tutorials_without_code = tutorials.filter(
            Q(code_blocks__exact=[]) | Q(code_blocks__exact={})
        )
        
        # Calculate code quality metrics
        code_quality = {
            'total_code_blocks': len(all_code_blocks),
            'pages_with_code': pages_with_code,
            'pages_without_code': self.pages.count() - pages_with_code,
            'language_distribution': dict(language_counter),
            'api_pages_without_examples': api_without_examples.count(),
            'tutorials_without_code': tutorials_without_code.count(),
            'code_coverage_percentage': (pages_with_code / self.pages.count() * 100) if self.pages.count() > 0 else 0,
        }
        
        # Identify missing languages based on common requirements
        common_languages = ['python', 'javascript', 'java', 'go', 'ruby', 'php']
        missing_languages = set(common_languages) - set(language_counter.keys())
        code_quality['missing_language_support'] = list(missing_languages)
        
        return code_quality
    
    def analyze_seo_opportunities(self) -> Dict[str, Any]:
        """Analyze SEO and discoverability issues"""
        
        # Pages missing critical SEO elements
        missing_title = self.pages.filter(Q(title='') | Q(title__isnull=True))
        missing_meta = self.pages.filter(Q(meta_description='') | Q(meta_description__isnull=True))
        
        # Duplicate titles
        duplicate_titles = self.pages.values('title').annotate(
            count=Count('id')
        ).filter(count__gt=1).exclude(title='')
        
        # Pages with very short meta descriptions
        short_meta = self.pages.filter(
            meta_description__isnull=False
        ).exclude(
            meta_description=''
        ).annotate(
            meta_length=Length('meta_description')
        ).filter(meta_length__lt=50)
        
        # Find keyword opportunities
        keyword_gaps = self._analyze_keyword_gaps()
        
        # Calculate potential traffic impact
        seo_impact = self._calculate_seo_impact(missing_meta.count() + missing_title.count())
        
        return {
            'missing_titles': missing_title.count(),
            'missing_meta_descriptions': missing_meta.count(),
            'duplicate_titles': len(duplicate_titles),
            'short_meta_descriptions': short_meta.count(),
            'keyword_gaps': keyword_gaps,
            'estimated_traffic_loss': seo_impact['traffic_loss'],
            'estimated_revenue_impact': seo_impact['revenue_impact'],
            'pages_without_og_tags': self.pages.filter(og_tags__exact={}).count(),
        }
    
    def analyze_api_completeness(self) -> Dict[str, Any]:
        """Analyze API documentation completeness"""
        
        api_pages = self.get_api_pages()
        
        # Check for API essentials
        has_auth_docs = api_pages.filter(
            Q(url__icontains='auth') | 
            Q(title__icontains='authentication') |
            Q(main_content__icontains='authentication')
        ).exists()
        
        has_error_docs = api_pages.filter(
            Q(url__icontains='error') | 
            Q(title__icontains='error') |
            Q(main_content__icontains='error handling')
        ).exists()
        
        has_rate_limit_docs = api_pages.filter(
            Q(main_content__icontains='rate limit') |
            Q(main_content__icontains='throttl')
        ).exists()
        
        # Find endpoints
        endpoints_found = []
        for page in api_pages:
            if page.api_endpoints:
                endpoints_found.extend(page.api_endpoints)
        
        # Check endpoint documentation quality
        endpoints_without_examples = 0
        endpoints_without_parameters = 0
        
        for page in api_pages:
            if page.api_endpoints and not page.has_examples:
                endpoints_without_examples += len(page.api_endpoints)
            if page.api_endpoints and not page.parameters:
                endpoints_without_parameters += len(page.api_endpoints)
        
        return {
            'total_api_pages': api_pages.count(),
            'has_authentication_docs': has_auth_docs,
            'has_error_handling_docs': has_error_docs,
            'has_rate_limiting_docs': has_rate_limit_docs,
            'total_endpoints_documented': len(endpoints_found),
            'endpoints_without_examples': endpoints_without_examples,
            'endpoints_without_parameters': endpoints_without_parameters,
            'api_completeness_score': self._calculate_api_completeness_score(api_pages),
        }
    
    def analyze_performance_issues(self) -> Dict[str, Any]:
        """Analyze page performance and technical issues"""
        
        # Slow pages
        slow_pages = self.pages.filter(
            response_time__gt=self.config['max_response_time']
        )
        
        # Large pages
        large_pages = self.pages.filter(
            page_size__gt=500000  # > 500KB
        )
        
        # JavaScript-rendered pages (potential performance issue)
        js_rendered = self.pages.filter(render_method='javascript')
        
        # Failed pages from crawl errors
        crawl_errors = self.job.errors.all() if hasattr(self.job, 'errors') else []
        
        # Response time statistics
        response_stats = self.pages.aggregate(
            avg_response=Avg('response_time'),
            max_response=Max('response_time'),
            min_response=Min('response_time')
        )
        
        return {
            'slow_pages': slow_pages.count(),
            'large_pages': large_pages.count(),
            'javascript_rendered_pages': js_rendered.count(),
            'crawl_errors': len(crawl_errors),
            'response_time_stats': response_stats,
            'performance_impact': self._calculate_performance_impact(slow_pages),
        }
    
    # ==========================================
    # Insight Generation Methods
    # ==========================================
    
    def _generate_content_insights(self, content_quality: Dict):
        """Generate insights from content quality analysis"""
        
        # Critical: High number of low readability pages
        if content_quality['low_readability_pages'] > 20:
            self.insights.append(Insight(
                type='critical',
                category='content',
                title='Poor Content Readability Impacting User Experience',
                finding=f"{content_quality['low_readability_pages']} pages have readability scores below {self.config['min_readability_score']}",
                impact=f"Estimated ${content_quality['estimated_support_impact']:,.0f} annual support cost",
                effort='medium',
                priority=9,
                affected_pages=list(self.pages.filter(
                    readability_score__lt=self.config['min_readability_score']
                ).values_list('url', flat=True)[:10]),
                estimated_value=content_quality['estimated_support_impact']
            ))
        
        # Warning: Stub pages
        if content_quality['stub_pages'] > 10:
            self.insights.append(Insight(
                type='warning',
                category='content',
                title='Incomplete Documentation Pages',
                finding=f"{content_quality['stub_pages']} pages have less than {self.config['min_word_count']} words",
                impact="Poor user experience and increased bounce rate",
                effort='low',
                priority=7,
                affected_pages=list(self.pages.filter(
                    word_count__lt=self.config['min_word_count']
                ).values_list('url', flat=True)[:10])
            ))
        
        # Opportunity: Add examples
        if content_quality['pages_without_examples'] > 15:
            affected = self.pages.filter(
                has_examples=False,
                doc_type__in=['tutorial', 'guide', 'api_reference']
            )
            self.insights.append(Insight(
                type='opportunity',
                category='content',
                title='Increase Developer Adoption with Examples',
                finding=f"{content_quality['pages_without_examples']} technical pages lack examples",
                impact="60% faster integration time for developers",
                effort='medium',
                priority=8,
                affected_pages=list(affected.values_list('url', flat=True)[:10]),
                estimated_value=affected.count() * 500  # $500 value per improved page
            ))
    
    def _generate_navigation_insights(self, nav_structure: Dict):
        """Generate insights from navigation analysis"""
        
        # Critical: Orphaned pages
        if nav_structure['orphaned_pages'] > 5:
            self.insights.append(Insight(
                type='critical',
                category='navigation',
                title='Undiscoverable Content (Orphaned Pages)',
                finding=f"{nav_structure['orphaned_pages']} pages have no incoming links",
                impact="Content investment wasted - users can't find these pages",
                effort='low',
                priority=8,
                affected_pages=list(self.pages.filter(
                    internal_links__exact=[]
                ).values_list('url', flat=True)[:10])
            ))
        
        # Warning: Dead ends
        if nav_structure['dead_ends'] > 20:
            self.insights.append(Insight(
                type='warning',
                category='navigation',
                title='Navigation Dead Ends',
                finding=f"{nav_structure['dead_ends']} pages don't link to any other content",
                impact="Users get stuck and abandon documentation",
                effort='low',
                priority=6,
                affected_pages=list(self.pages.filter(
                    internal_links__exact=[]
                ).exclude(
                    doc_type='api_reference'
                ).values_list('url', flat=True)[:10])
            ))
    
    def _generate_code_insights(self, code_coverage: Dict):
        """Generate insights from code coverage analysis"""
        
        # Critical: API pages without examples
        if code_coverage['api_pages_without_examples'] > 10:
            api_pages_affected = self.get_api_pages().filter(
                Q(code_blocks__exact=[]) | Q(code_blocks__exact={})
            )
            
            self.insights.append(Insight(
                type='critical',
                category='code',
                title='API Documentation Lacks Code Examples',
                finding=f"{code_coverage['api_pages_without_examples']} API pages have no code examples",
                impact="3x longer integration time, 70% higher support burden",
                effort='medium',
                priority=10,
                affected_pages=list(api_pages_affected.values_list('url', flat=True)[:10]),
                estimated_value=code_coverage['api_pages_without_examples'] * 1000
            ))
        
        # Opportunity: Missing language support
        if code_coverage['missing_language_support']:
            self.insights.append(Insight(
                type='opportunity',
                category='code',
                title='Expand Developer Reach with More Languages',
                finding=f"No examples in: {', '.join(code_coverage['missing_language_support'])}",
                impact="Missing 40% of potential developer audience",
                effort='high',
                priority=6,
                affected_pages=[],
                estimated_value=len(code_coverage['missing_language_support']) * 5000
            ))
    
    def _generate_seo_insights(self, seo_data: Dict):
        """Generate insights from SEO analysis"""
        
        # Critical: Missing meta descriptions
        if seo_data['missing_meta_descriptions'] > 50:
            self.insights.append(Insight(
                type='critical',
                category='seo',
                title='Massive SEO Opportunity - Missing Meta Descriptions',
                finding=f"{seo_data['missing_meta_descriptions']} pages lack meta descriptions",
                impact=f"${seo_data['estimated_revenue_impact']:,.0f} annual revenue opportunity",
                effort='low',
                priority=9,
                affected_pages=list(self.pages.filter(
                    Q(meta_description='') | Q(meta_description__isnull=True)
                ).values_list('url', flat=True)[:10]),
                estimated_value=seo_data['estimated_revenue_impact']
            ))
        
        # Quick win: Duplicate titles
        if seo_data['duplicate_titles'] > 5:
            self.insights.append(Insight(
                type='quick_win',
                category='seo',
                title='Fix Duplicate Page Titles',
                finding=f"{seo_data['duplicate_titles']} sets of duplicate titles found",
                impact="Improved search rankings and click-through rates",
                effort='low',
                priority=7,
                affected_pages=[]
            ))
    
    def _generate_api_insights(self, api_data: Dict):
        """Generate insights from API completeness analysis"""
        
        # Critical: Missing authentication docs
        if not api_data['has_authentication_docs'] and api_data['total_api_pages'] > 0:
            self.insights.append(Insight(
                type='critical',
                category='api',
                title='Missing API Authentication Documentation',
                finding="No authentication documentation found",
                impact="Developers can't integrate without auth docs",
                effort='medium',
                priority=10,
                affected_pages=[],
                estimated_value=25000  # High value for missing auth docs
            ))
        
        # Warning: Missing error handling docs
        if not api_data['has_error_handling_docs'] and api_data['total_api_pages'] > 0:
            self.insights.append(Insight(
                type='warning',
                category='api',
                title='No Error Handling Documentation',
                finding="API error responses and handling not documented",
                impact="Poor developer experience, increased support tickets",
                effort='low',
                priority=7,
                affected_pages=[]
            ))
    
    def _generate_performance_insights(self, perf_data: Dict):
        """Generate insights from performance analysis"""
        
        # Warning: Slow pages
        if perf_data['slow_pages'] > 10:
            self.insights.append(Insight(
                type='warning',
                category='performance',
                title='Slow Page Load Times',
                finding=f"{perf_data['slow_pages']} pages take over {self.config['max_response_time']}s to load",
                impact="40% of users abandon slow pages",
                effort='medium',
                priority=6,
                affected_pages=list(self.pages.filter(
                    response_time__gt=self.config['max_response_time']
                ).values_list('url', flat=True)[:10])
            ))
    
    # ==========================================
    # Summary and Recommendation Methods
    # ==========================================
    
    def _generate_executive_summary(self) -> Dict[str, Any]:
        """Generate executive summary of findings"""
        
        critical_issues = [i for i in self.insights if i.type == 'critical']
        quick_wins = [i for i in self.insights if i.type == 'quick_win' or i.effort == 'low']
        total_value = sum(i.estimated_value for i in self.insights if i.estimated_value)
        
        return {
            'total_pages_analyzed': self.pages.count(),
            'critical_issues_found': len(critical_issues),
            'quick_wins_available': len(quick_wins),
            'total_insights': len(self.insights),
            'estimated_total_value': total_value,
            'top_3_priorities': [i.title for i in self.insights[:3]],
            'biggest_opportunity': self.insights[0].title if self.insights else None,
        }
    
    def _generate_recommendations(self) -> List[Dict[str, Any]]:
        """Generate prioritized recommendations"""
        
        recommendations = []
        
        # Group insights by effort
        low_effort = [i for i in self.insights if i.effort == 'low']
        medium_effort = [i for i in self.insights if i.effort == 'medium']
        high_effort = [i for i in self.insights if i.effort == 'high']
        
        # Quick wins (high impact, low effort)
        for insight in low_effort[:5]:
            recommendations.append({
                'title': insight.title,
                'priority': 'immediate',
                'effort': '1-2 days',
                'impact': insight.impact,
                'category': insight.category,
            })
        
        # Strategic improvements (high impact, medium effort)
        for insight in medium_effort[:5]:
            recommendations.append({
                'title': insight.title,
                'priority': 'short-term',
                'effort': '1-2 weeks',
                'impact': insight.impact,
                'category': insight.category,
            })
        
        # Long-term initiatives
        for insight in high_effort[:3]:
            recommendations.append({
                'title': insight.title,
                'priority': 'long-term',
                'effort': '1-3 months',
                'impact': insight.impact,
                'category': insight.category,
            })
        
        return recommendations
    
    def _generate_30_60_90_day_plan(self) -> Dict[str, List[str]]:
        """Generate a phased improvement plan"""
        
        return {
            '30_days': [
                i.title for i in self.insights 
                if i.effort == 'low' and i.priority >= 7
            ][:5],
            '60_days': [
                i.title for i in self.insights 
                if i.effort in ['low', 'medium'] and i.priority >= 5
            ][5:10],
            '90_days': [
                i.title for i in self.insights 
                if i.priority >= 3
            ][10:15],
        }
    
    # ==========================================
    # Helper Methods
    # ==========================================
    
    def get_api_pages(self):
        """Get cached API pages queryset"""
        if self._api_pages is None:
            self._api_pages = self.pages.filter(doc_type='api_reference')
        return self._api_pages
    
    def get_tutorial_pages(self):
        """Get cached tutorial pages queryset"""
        if self._tutorial_pages is None:
            self._tutorial_pages = self.pages.filter(doc_type='tutorial')
        return self._tutorial_pages
    
    def get_guide_pages(self):
        """Get cached guide pages queryset"""
        if self._guide_pages is None:
            self._guide_pages = self.pages.filter(doc_type='guide')
        return self._guide_pages
    
    def _calculate_overall_score(self) -> int:
        """Calculate overall documentation health score (0-100)"""
        
        score = 100
        
        # Deduct points for issues
        critical_issues = len([i for i in self.insights if i.type == 'critical'])
        warnings = len([i for i in self.insights if i.type == 'warning'])
        
        score -= (critical_issues * 10)
        score -= (warnings * 3)
        
        # Ensure score stays in bounds
        return max(0, min(100, score))
    
    def _calculate_support_impact(self, problematic_pages) -> float:
        """Calculate estimated support cost impact"""
        
        # Estimate: Each problematic page generates 2 support tickets per month
        # Each ticket costs $50 to resolve
        monthly_tickets = problematic_pages.count() * 2
        annual_cost = monthly_tickets * 12 * self.config['support_ticket_cost']
        
        return annual_cost
    
    def _calculate_seo_impact(self, missing_seo_pages: int) -> Dict[str, float]:
        """Calculate SEO and traffic impact"""
        
        # Estimates based on industry averages
        avg_monthly_traffic_per_page = 100
        conversion_rate = 0.02
        average_deal_size = 5000
        
        traffic_loss = missing_seo_pages * avg_monthly_traffic_per_page
        revenue_impact = traffic_loss * conversion_rate * average_deal_size * 12
        
        return {
            'traffic_loss': traffic_loss,
            'revenue_impact': revenue_impact
        }
    
    def _calculate_performance_impact(self, slow_pages) -> str:
        """Calculate the impact of slow pages"""
        
        # 40% of users abandon pages that take > 3 seconds
        affected_pages = slow_pages.count()
        estimated_abandonment = affected_pages * 100 * 0.4  # 100 visits per page per month
        
        return f"{estimated_abandonment:.0f} users/month abandoning due to slow load times"
    
    def _calculate_navigation_health(self) -> int:
        """Calculate navigation health score"""
        
        total_pages = self.pages.count()
        if total_pages == 0:
            return 0
        
        orphaned = self.pages.filter(internal_links__exact=[]).count()
        orphaned_percentage = (orphaned / total_pages) * 100
        
        # Score from 0-100, lower percentage of orphans = higher score
        score = max(0, 100 - int(orphaned_percentage * 2))
        
        return score
    
    def _calculate_api_completeness_score(self, api_pages) -> int:
        """Calculate API documentation completeness score"""
        
        if api_pages.count() == 0:
            return 0
        
        score = 100
        
        # Check for essential documentation
        has_auth = api_pages.filter(
            Q(url__icontains='auth') | Q(main_content__icontains='authentication')
        ).exists()
        
        has_errors = api_pages.filter(
            Q(main_content__icontains='error') | Q(main_content__icontains='status code')
        ).exists()
        
        has_examples = api_pages.filter(has_examples=True).count() / api_pages.count()
        
        if not has_auth:
            score -= 30
        if not has_errors:
            score -= 20
        
        # Deduct based on pages without examples
        score -= int((1 - has_examples) * 30)
        
        return max(0, score)
    
    def _find_circular_references(self) -> List[Tuple[str, str]]:
        """Find pages that link to each other in circles"""
        # Simplified implementation - in production you'd want graph traversal
        circular_refs = []
        
        relationships = PageRelationship.objects.filter(
            from_page__job=self.job,
            to_page__job=self.job
        )
        
        for rel in relationships[:100]:  # Limit to prevent long processing
            # Check if there's a reverse relationship
            reverse_exists = PageRelationship.objects.filter(
                from_page=rel.to_page,
                to_page=rel.from_page
            ).exists()
            
            if reverse_exists:
                circular_refs.append((rel.from_page.url, rel.to_page.url))
        
        return circular_refs[:10]  # Return first 10 circular references
    
    def _analyze_keyword_gaps(self) -> Dict[str, Any]:
        """Analyze keyword gaps (simplified version)"""
        
        # This would integrate with competitor analysis in production
        # For now, check for common important keywords
        
        important_keywords = [
            'api', 'authentication', 'tutorial', 'getting started',
            'quickstart', 'examples', 'reference', 'sdk', 'library',
            'integration', 'webhook', 'security', 'rate limit'
        ]
        
        found_keywords = set()
        missing_keywords = []
        
        # Sample first 100 pages for performance
        sample_pages = self.pages[:100]
        
        for page in sample_pages:
            content = (page.main_content or '').lower()
            for keyword in important_keywords:
                if keyword in content:
                    found_keywords.add(keyword)
        
        missing_keywords = list(set(important_keywords) - found_keywords)
        
        return {
            'found': list(found_keywords),
            'missing': missing_keywords,
            'coverage_percentage': (len(found_keywords) / len(important_keywords) * 100)
        }
