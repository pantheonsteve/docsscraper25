# analyzer/management/commands/analyze.py

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from analyzer.documentation_analyzer import DocumentationAnalyzer
from analyzer.quick_analyzer import QuickAnalyzer
try:
    from analyzer.report_generator import ReportGenerator
except ImportError:
    ReportGenerator = None
from core.models import CrawlJob
import json
from pathlib import Path


class Command(BaseCommand):
    help = 'Analyze a completed crawl and generate insights'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--job',
            type=int,
            required=True,
            help='CrawlJob ID to analyze'
        )
        parser.add_argument(
            '--format',
            choices=['json', 'html', 'pdf', 'terminal'],
            default='terminal',
            help='Output format for the report'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path (if not specified, prints to stdout)'
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email address to send the report to'
        )
        parser.add_argument(
            '--quick',
            action='store_true',
            help='Run quick analysis (skip detailed checks)'
        )
    
    def handle(self, *args, **options):
        job_id = options['job']
        output_format = options['format']
        output_path = options.get('output')
        email = options.get('email')
        quick_mode = options.get('quick', False)
        
        # Verify job exists and is complete
        try:
            job = CrawlJob.objects.get(id=job_id)
        except CrawlJob.DoesNotExist:
            raise CommandError(f'CrawlJob with ID {job_id} does not exist')
        
        if job.status != 'completed':
            self.stdout.write(
                self.style.WARNING(
                    f'Warning: Job {job_id} status is {job.status}, not completed'
                )
            )
        
        # Check if we have pages to analyze
        page_count = job.pages.count()
        if page_count == 0:
            raise CommandError(f'No pages found for job {job_id}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Analyzing {page_count} pages from {job.target_url}...'
            )
        )
        
        # Run analysis
        start_time = timezone.now()
        analyzer = DocumentationAnalyzer(job_id)
        
        try:
            if quick_mode:
                # Use the optimized quick analyzer
                quick_analyzer = QuickAnalyzer(job_id)
                analysis_results = quick_analyzer.analyze()
                self.stdout.write('Quick analysis completed')
            else:
                # Full analysis - WARNING: Can be slow for large sites
                self.stdout.write(
                    self.style.WARNING(
                        'Running full analysis. This may take several minutes for large sites...'
                    )
                )
                analysis_results = analyzer.generate_comprehensive_analysis()
                
                # Mark job as analyzed
                job.is_analyzed = True
                job.analysis_started_at = start_time
                job.save(update_fields=['is_analyzed', 'analysis_started_at'])
            
            duration = (timezone.now() - start_time).total_seconds()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Analysis completed in {duration:.1f} seconds'
                )
            )
            
            # Generate report in requested format
            if output_format == 'terminal':
                self._print_terminal_report(analysis_results)
            elif output_format == 'json':
                self._save_json_report(analysis_results, output_path)
            elif output_format == 'html':
                self._generate_html_report(analysis_results, output_path, job)
            elif output_format == 'pdf':
                self._generate_pdf_report(analysis_results, output_path, job)
            
            # Send email if requested
            if email:
                self._send_email_report(analysis_results, email, job)
            
            # Print summary
            if 'executive_summary' in analysis_results:
                summary = analysis_results['executive_summary']
                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS('=== Executive Summary ==='))
                self.stdout.write(f"Critical Issues: {summary.get('critical_issues_found', 0)}")
                self.stdout.write(f"Quick Wins: {summary.get('quick_wins_available', 0)}")
                self.stdout.write(f"Total Insights: {summary.get('total_insights', 0)}")
                
                if summary.get('estimated_total_value'):
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Estimated Value: ${summary['estimated_total_value']:,.0f}"
                        )
                    )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Analysis failed: {str(e)}')
            )
            raise CommandError(f'Analysis failed: {str(e)}')
    
    def _print_terminal_report(self, results):
        """Print a formatted report to the terminal"""
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS('DOCUMENTATION ANALYSIS REPORT'))
        self.stdout.write(self.style.SUCCESS('='*60))
        
        # Handle quick analysis format
        if 'quick_insights' in results:
            self._print_quick_report(results)
            return
        
        # Overall score
        if 'overall_score' in results:
            score = results['overall_score']
            if score >= 80:
                score_style = self.style.SUCCESS
            elif score >= 60:
                score_style = self.style.WARNING
            else:
                score_style = self.style.ERROR
            
            self.stdout.write(f"\nOverall Score: {score_style(f'{score}/100')}")
        
        # Top insights
        if 'insights' in results and results['insights']:
            self.stdout.write('\n' + self.style.SUCCESS('TOP INSIGHTS:'))
            self.stdout.write('-' * 40)
            
            for i, insight in enumerate(results['insights'][:5], 1):
                # Color code by type
                if insight['type'] == 'critical':
                    style = self.style.ERROR
                elif insight['type'] == 'warning':
                    style = self.style.WARNING
                else:
                    style = self.style.SUCCESS
                
                self.stdout.write(f"\n{i}. {style(insight['title'])}")
                self.stdout.write(f"   Finding: {insight['finding']}")
                self.stdout.write(f"   Impact: {insight['impact']}")
                self.stdout.write(f"   Effort: {insight['effort']}")
                if insight.get('estimated_value'):
                    self.stdout.write(
                        f"   Value: ${insight['estimated_value']:,.0f}"
                    )
                
                # Show affected pages if available
                if 'affected_pages' in insight and insight['affected_pages']:
                    affected = insight['affected_pages']
                    total = insight.get('affected_pages_count', len(affected))
                    self.stdout.write(f"   Affected Pages ({len(affected)} of {total}):")
                    for url in affected[:3]:  # Show first 3
                        self.stdout.write(f"      → {url}")
                    if len(affected) > 3:
                        self.stdout.write(f"      ... and {len(affected)-3} more examples")
        
        # Detailed metrics
        if 'detailed_metrics' in results:
            metrics = results['detailed_metrics']
            
            self.stdout.write('\n' + self.style.SUCCESS('DETAILED METRICS:'))
            self.stdout.write('-' * 40)
            
            # Content Quality
            if 'content_quality' in metrics:
                cq = metrics['content_quality']
                self.stdout.write('\nContent Quality:')
                self.stdout.write(f"  Low readability pages: {cq.get('low_readability_pages', 0)}")
                self.stdout.write(f"  Stub pages: {cq.get('stub_pages', 0)}")
                self.stdout.write(f"  Pages without examples: {cq.get('pages_without_examples', 0)}")
            
            # Code Coverage
            if 'code_coverage' in metrics:
                cc = metrics['code_coverage']
                self.stdout.write('\nCode Coverage:')
                self.stdout.write(f"  Total code blocks: {cc.get('total_code_blocks', 0)}")
                self.stdout.write(f"  Pages with code: {cc.get('pages_with_code', 0)}")
                self.stdout.write(f"  API pages without examples: {cc.get('api_pages_without_examples', 0)}")
                
                if cc.get('language_distribution'):
                    self.stdout.write('  Languages found:')
                    for lang, count in cc['language_distribution'].items():
                        self.stdout.write(f"    - {lang}: {count}")
            
            # SEO
            if 'seo_opportunities' in metrics:
                seo = metrics['seo_opportunities']
                self.stdout.write('\nSEO Issues:')
                self.stdout.write(f"  Missing titles: {seo.get('missing_titles', 0)}")
                self.stdout.write(f"  Missing meta descriptions: {seo.get('missing_meta_descriptions', 0)}")
                
                if seo.get('estimated_revenue_impact'):
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Revenue impact: ${seo['estimated_revenue_impact']:,.0f}/year"
                        )
                    )
        
        # Recommendations
        if 'recommendations' in results and results['recommendations']:
            self.stdout.write('\n' + self.style.SUCCESS('RECOMMENDATIONS:'))
            self.stdout.write('-' * 40)
            
            for rec in results['recommendations'][:5]:
                self.stdout.write(f"\n• {rec['title']}")
                self.stdout.write(f"  Priority: {rec['priority']}")
                self.stdout.write(f"  Effort: {rec['effort']}")
        
        # 30-60-90 day plan
        if 'roadmap' in results:
            roadmap = results['roadmap']
            self.stdout.write('\n' + self.style.SUCCESS('30-60-90 DAY PLAN:'))
            self.stdout.write('-' * 40)
            
            if roadmap.get('30_days'):
                self.stdout.write('\n30 Days:')
                for item in roadmap['30_days']:
                    self.stdout.write(f"  • {item}")
            
            if roadmap.get('60_days'):
                self.stdout.write('\n60 Days:')
                for item in roadmap['60_days']:
                    self.stdout.write(f"  • {item}")
            
            if roadmap.get('90_days'):
                self.stdout.write('\n90 Days:')
                for item in roadmap['90_days']:
                    self.stdout.write(f"  • {item}")
        
        self.stdout.write('')
        self.stdout.write('='*60)
    
    def _print_quick_report(self, results):
        """Print quick analysis report"""
        
        # Basic metrics
        self.stdout.write(f"\nSite: {results.get('site_url', 'Unknown')}")
        self.stdout.write(f"Total Pages: {results.get('total_pages', 0)}")
        
        # Content metrics
        if 'content_metrics' in results:
            cm = results['content_metrics']
            self.stdout.write('\n' + self.style.SUCCESS('CONTENT QUALITY:'))
            self.stdout.write('-' * 40)
            
            avg_readability = cm.get('avg_readability')
            if avg_readability:
                if avg_readability >= 60:
                    style = self.style.SUCCESS
                elif avg_readability >= 40:
                    style = self.style.WARNING
                else:
                    style = self.style.ERROR
                self.stdout.write(f"Average Readability: {style(f'{avg_readability:.1f}/100')}")
            
            self.stdout.write(f"Average Word Count: {cm.get('avg_word_count', 0):.0f} words")
            
            if cm.get('low_readability', 0) > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"Low Readability Pages: {cm['low_readability']}"
                    )
                )
            
            if cm.get('stub_pages', 0) > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"Stub Pages (<100 words): {cm['stub_pages']}"
                    )
                )
            
            if cm.get('pages_without_examples', 0) > 0:
                self.stdout.write(
                    f"Pages Without Examples: {cm['pages_without_examples']}"
                )
        
        # SEO metrics
        if 'seo_metrics' in results:
            seo = results['seo_metrics']
            self.stdout.write('\n' + self.style.SUCCESS('SEO ISSUES:'))
            self.stdout.write('-' * 40)
            
            if seo.get('missing_titles', 0) > 0:
                self.stdout.write(
                    self.style.ERROR(
                        f"Missing Titles: {seo['missing_titles']}"
                    )
                )
            
            if seo.get('missing_meta', 0) > 0:
                self.stdout.write(
                    self.style.ERROR(
                        f"Missing Meta Descriptions: {seo['missing_meta']}"
                    )
                )
            
            if seo.get('duplicate_pages', 0) > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"Duplicate Pages: {seo['duplicate_pages']}"
                    )
                )
        
        # Performance metrics
        if 'performance_metrics' in results:
            perf = results['performance_metrics']
            self.stdout.write('\n' + self.style.SUCCESS('PERFORMANCE:'))
            self.stdout.write('-' * 40)
            
            avg_response = perf.get('avg_response_time')
            if avg_response:
                if avg_response < 1.0:
                    style = self.style.SUCCESS
                elif avg_response < 2.0:
                    style = self.style.WARNING
                else:
                    style = self.style.ERROR
                self.stdout.write(
                    f"Average Response Time: {style(f'{avg_response:.2f}s')}"
                )
            
            if perf.get('slow_pages', 0) > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"Slow Pages (>2s): {perf['slow_pages']}"
                    )
                )
            
            if perf.get('large_pages', 0) > 0:
                self.stdout.write(
                    f"Large Pages (>500KB): {perf['large_pages']}"
                )
        
        # Quick insights
        if 'quick_insights' in results and results['quick_insights']:
            self.stdout.write('\n' + self.style.SUCCESS('TOP INSIGHTS:'))
            self.stdout.write('-' * 40)
            
            for i, insight in enumerate(results['quick_insights'][:5], 1):
                # Color code by type
                if insight['type'] == 'critical':
                    style = self.style.ERROR
                elif insight['type'] == 'warning':
                    style = self.style.WARNING
                else:
                    style = self.style.SUCCESS
                
                self.stdout.write(f"\n{i}. {style(insight['title'])}")
                if insight.get('finding'):
                    self.stdout.write(f"   Finding: {insight['finding']}")
                self.stdout.write(f"   Impact: {insight['impact']}")
                self.stdout.write(f"   Effort: {insight['effort']}")
                
                # Show affected pages
                if insight.get('affected_pages'):
                    pages = insight['affected_pages']
                    total = insight.get('affected_pages_count', len(pages))
                    self.stdout.write(f"   Affected: {total} pages (showing first {len(pages)}):")
                    for page in pages[:5]:  # Show first 5
                        self.stdout.write(f"     • {page}")
                    if len(pages) > 5:
                        self.stdout.write(f"     ... and {len(pages)-5} more")
        
        self.stdout.write('')
        self.stdout.write('='*60)
    
    def _save_json_report(self, results, output_path):
        """Save analysis results as JSON"""
        
        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            self.stdout.write(
                self.style.SUCCESS(f'JSON report saved to {path}')
            )
        else:
            # Print to stdout
            self.stdout.write(json.dumps(results, indent=2, default=str))
    
    def _generate_html_report(self, results, output_path, job):
        """Generate HTML report"""
        
        try:
            from analyzer.report_generator import ReportGenerator
            
            generator = ReportGenerator(job, results)
            html_content = generator.generate_html()
            
            if output_path:
                path = Path(output_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(path, 'w') as f:
                    f.write(html_content)
                
                self.stdout.write(
                    self.style.SUCCESS(f'HTML report saved to {path}')
                )
            else:
                self.stdout.write(html_content)
                
        except ImportError:
            self.stdout.write(
                self.style.ERROR(
                    'ReportGenerator not available. Please implement analyzer/report_generator.py'
                )
            )
    
    def _generate_pdf_report(self, results, output_path, job):
        """Generate PDF report"""
        
        try:
            from analyzer.report_generator import ReportGenerator
            
            generator = ReportGenerator(job, results)
            
            # First generate HTML
            html_content = generator.generate_html()
            
            # Convert to PDF
            pdf_content = generator.html_to_pdf(html_content)
            
            if output_path:
                path = Path(output_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(path, 'wb') as f:
                    f.write(pdf_content)
                
                self.stdout.write(
                    self.style.SUCCESS(f'PDF report saved to {path}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('PDF content cannot be printed to terminal')
                )
                
        except ImportError:
            self.stdout.write(
                self.style.ERROR(
                    'PDF generation requires WeasyPrint. Install with: pip install weasyprint'
                )
            )
    
    def _send_email_report(self, results, email, job):
        """Send email with analysis report"""
        
        try:
            from django.core.mail import EmailMessage
            from analyzer.report_generator import ReportGenerator
            
            generator = ReportGenerator(job, results)
            html_content = generator.generate_html()
            
            subject = f'Documentation Analysis Report - {job.client.name if job.client else job.target_url}'
            
            msg = EmailMessage(
                subject=subject,
                body='Please find attached your documentation analysis report.',
                to=[email],
            )
            msg.content_subtype = 'html'
            msg.body = html_content
            
            # Attach JSON data
            msg.attach(
                'analysis_data.json',
                json.dumps(results, indent=2, default=str),
                'application/json'
            )
            
            msg.send()
            
            self.stdout.write(
                self.style.SUCCESS(f'Report emailed to {email}')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to send email: {str(e)}')
            )