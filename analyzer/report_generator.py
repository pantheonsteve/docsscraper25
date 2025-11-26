# analyzer/report_generator.py

import json
from datetime import datetime
from pathlib import Path
from django.template import Template, Context
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import Avg, Count, Q
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
from io import BytesIO
import base64

# Optional: PDF generation
try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False


class ReportGenerator:
    """Generate professional documentation analysis reports"""
    
    def __init__(self, job, analysis_results):
        self.job = job
        self.results = analysis_results
        self.pages = job.pages.all()
        
    def generate_html(self):
        """Generate HTML report from analysis results"""
        
        # Create charts
        charts = self._generate_charts()
        
        # Prepare context
        context = {
            'job': self.job,
            'client': self.job.client,
            'results': self.results,
            'charts': charts,
            'generation_date': timezone.now(),
            'total_pages': self.pages.count(),
            'unique_pages': self.pages.filter(is_duplicate=False).count(),
            'executive_summary': self.results.get('executive_summary', {}),
            'insights': self.results.get('insights', []),
            'detailed_metrics': self.results.get('detailed_metrics', {}),
            'recommendations': self.results.get('recommendations', []),
            'roadmap': self.results.get('roadmap', {}),
        }
        
        # Try to use Django template if available
        try:
            html = render_to_string('analyzer/report_template.html', context)
        except:
            # Fallback to inline template
            html = self._generate_html_from_template(context)
        
        return html
    
    def _generate_html_from_template(self, context):
        """Generate HTML using inline template"""
        
        template_string = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Documentation Analysis Report - {{ job.target_url }}</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                    background: #f5f5f5;
                }
                
                .header {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 40px;
                    border-radius: 10px;
                    margin-bottom: 30px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                }
                
                .header h1 {
                    margin: 0;
                    font-size: 2.5em;
                    font-weight: 700;
                }
                
                .header .subtitle {
                    margin-top: 10px;
                    opacity: 0.95;
                    font-size: 1.2em;
                }
                
                .section {
                    background: white;
                    padding: 30px;
                    margin-bottom: 30px;
                    border-radius: 10px;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.08);
                }
                
                .section h2 {
                    color: #667eea;
                    border-bottom: 2px solid #f0f0f0;
                    padding-bottom: 10px;
                    margin-bottom: 20px;
                }
                
                .metric-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin: 20px 0;
                }
                
                .metric-card {
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 8px;
                    border-left: 4px solid #667eea;
                }
                
                .metric-card .value {
                    font-size: 2em;
                    font-weight: bold;
                    color: #333;
                }
                
                .metric-card .label {
                    color: #666;
                    margin-top: 5px;
                    font-size: 0.9em;
                }
                
                .score-display {
                    text-align: center;
                    padding: 30px;
                }
                
                .score-circle {
                    display: inline-block;
                    width: 150px;
                    height: 150px;
                    border-radius: 50%;
                    line-height: 150px;
                    font-size: 3em;
                    font-weight: bold;
                    color: white;
                    margin: 20px;
                }
                
                .score-high { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
                .score-medium { background: linear-gradient(135deg, #f2994a 0%, #f2c94c 100%); }
                .score-low { background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); }
                
                .insight {
                    padding: 15px;
                    margin: 15px 0;
                    border-radius: 8px;
                    border-left: 5px solid;
                }
                
                .insight.critical {
                    background: #fef2f2;
                    border-color: #dc2626;
                }
                
                .insight.warning {
                    background: #fffbeb;
                    border-color: #f59e0b;
                }
                
                .insight.success {
                    background: #f0fdf4;
                    border-color: #10b981;
                }
                
                .insight h3 {
                    margin-top: 0;
                    color: #333;
                }
                
                .recommendation {
                    padding: 15px;
                    background: #f0f9ff;
                    border-radius: 8px;
                    margin: 15px 0;
                }
                
                .roadmap-timeline {
                    display: flex;
                    justify-content: space-between;
                    margin: 30px 0;
                }
                
                .roadmap-phase {
                    flex: 1;
                    margin: 0 10px;
                    padding: 20px;
                    background: #f8f9fa;
                    border-radius: 8px;
                    border-top: 4px solid #667eea;
                }
                
                .roadmap-phase h4 {
                    color: #667eea;
                    margin-top: 0;
                }
                
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }
                
                th {
                    background: #667eea;
                    color: white;
                    padding: 12px;
                    text-align: left;
                }
                
                td {
                    padding: 10px;
                    border-bottom: 1px solid #f0f0f0;
                }
                
                tr:hover {
                    background: #f8f9fa;
                }
                
                .footer {
                    text-align: center;
                    padding: 20px;
                    margin-top: 50px;
                    color: #666;
                    font-size: 0.9em;
                }
                
                @media print {
                    body { background: white; }
                    .section { box-shadow: none; border: 1px solid #ddd; }
                    .header { page-break-after: avoid; }
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Documentation Analysis Report</h1>
                <div class="subtitle">
                    {{ job.target_url }}<br>
                    Generated: {{ generation_date|date:"F j, Y" }}
                </div>
            </div>
            
            <!-- Executive Summary -->
            <div class="section">
                <h2>Executive Summary</h2>
                <div class="score-display">
                    {% if executive_summary.overall_score %}
                    <div class="score-circle {% if executive_summary.overall_score >= 80 %}score-high{% elif executive_summary.overall_score >= 60 %}score-medium{% else %}score-low{% endif %}">
                        {{ executive_summary.overall_score }}/100
                    </div>
                    <div>Documentation Quality Score</div>
                    {% endif %}
                </div>
                
                <div class="metric-grid">
                    <div class="metric-card">
                        <div class="value">{{ total_pages|default:"0" }}</div>
                        <div class="label">Total Pages</div>
                    </div>
                    <div class="metric-card">
                        <div class="value">{{ executive_summary.critical_issues_found|default:"0" }}</div>
                        <div class="label">Critical Issues</div>
                    </div>
                    <div class="metric-card">
                        <div class="value">{{ executive_summary.quick_wins_available|default:"0" }}</div>
                        <div class="label">Quick Wins</div>
                    </div>
                    <div class="metric-card">
                        <div class="value">${{ executive_summary.estimated_total_value|floatformat:0|default:"0" }}</div>
                        <div class="label">Potential Value</div>
                    </div>
                </div>
            </div>
            
            <!-- Top Insights -->
            {% if insights %}
            <div class="section">
                <h2>Key Insights</h2>
                {% for insight in insights|slice:":10" %}
                <div class="insight {{ insight.type }}">
                    <h3>{{ insight.title }}</h3>
                    <p><strong>Finding:</strong> {{ insight.finding }}</p>
                    <p><strong>Impact:</strong> {{ insight.impact }}</p>
                    <p><strong>Effort:</strong> {{ insight.effort }}</p>
                    {% if insight.estimated_value %}
                    <p><strong>Estimated Value:</strong> ${{ insight.estimated_value|floatformat:0 }}</p>
                    {% endif %}
                    
                    {% if insight.affected_pages %}
                    <details style="margin-top: 10px;">
                        <summary style="cursor: pointer; color: #667eea;">
                            <strong>Affected Pages (showing {{ insight.affected_pages|length }} of {{ insight.affected_pages_count|default:insight.affected_pages|length }})</strong>
                        </summary>
                        <ul style="margin-top: 10px; font-size: 0.9em;">
                        {% for page_url in insight.affected_pages %}
                            <li><a href="{{ page_url }}" target="_blank" style="color: #667eea;">{{ page_url }}</a></li>
                        {% endfor %}
                        </ul>
                        {% if insight.note %}
                        <p style="font-style: italic; color: #666; font-size: 0.9em;">Note: {{ insight.note }}</p>
                        {% endif %}
                    </details>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
            {% endif %}
            
            <!-- Detailed Metrics -->
            {% if detailed_metrics %}
            <div class="section">
                <h2>Detailed Analysis</h2>
                
                {% if detailed_metrics.content_quality %}
                <h3>Content Quality</h3>
                <table>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                        <th>Industry Benchmark</th>
                    </tr>
                    <tr>
                        <td>Average Readability Score</td>
                        <td>{{ detailed_metrics.content_quality.avg_readability|floatformat:1|default:"N/A" }}</td>
                        <td>60-70</td>
                    </tr>
                    <tr>
                        <td>Low Readability Pages</td>
                        <td>{{ detailed_metrics.content_quality.low_readability_pages|default:"0" }}</td>
                        <td>&lt; 10%</td>
                    </tr>
                    <tr>
                        <td>Stub Pages (&lt;100 words)</td>
                        <td>{{ detailed_metrics.content_quality.stub_pages|default:"0" }}</td>
                        <td>&lt; 5%</td>
                    </tr>
                    <tr>
                        <td>Pages Without Examples</td>
                        <td>{{ detailed_metrics.content_quality.pages_without_examples|default:"0" }}</td>
                        <td>&lt; 20%</td>
                    </tr>
                </table>
                {% endif %}
                
                {% if detailed_metrics.code_coverage %}
                <h3>Code Coverage</h3>
                <table>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                    </tr>
                    <tr>
                        <td>Total Code Blocks</td>
                        <td>{{ detailed_metrics.code_coverage.total_code_blocks|default:"0" }}</td>
                    </tr>
                    <tr>
                        <td>Pages with Code Examples</td>
                        <td>{{ detailed_metrics.code_coverage.pages_with_code|default:"0" }}</td>
                    </tr>
                    <tr>
                        <td>API Pages Without Examples</td>
                        <td>{{ detailed_metrics.code_coverage.api_pages_without_examples|default:"0" }}</td>
                    </tr>
                </table>
                
                {% if detailed_metrics.code_coverage.language_distribution %}
                <h4>Language Distribution</h4>
                <table>
                    <tr>
                        <th>Language</th>
                        <th>Count</th>
                    </tr>
                    {% for lang, count in detailed_metrics.code_coverage.language_distribution.items %}
                    <tr>
                        <td>{{ lang }}</td>
                        <td>{{ count }}</td>
                    </tr>
                    {% endfor %}
                </table>
                {% endif %}
                {% endif %}
                
                {% if detailed_metrics.seo_opportunities %}
                <h3>SEO Opportunities</h3>
                <table>
                    <tr>
                        <th>Issue</th>
                        <th>Count</th>
                        <th>Priority</th>
                    </tr>
                    <tr>
                        <td>Missing Page Titles</td>
                        <td>{{ detailed_metrics.seo_opportunities.missing_titles|default:"0" }}</td>
                        <td>High</td>
                    </tr>
                    <tr>
                        <td>Missing Meta Descriptions</td>
                        <td>{{ detailed_metrics.seo_opportunities.missing_meta_descriptions|default:"0" }}</td>
                        <td>High</td>
                    </tr>
                    <tr>
                        <td>Duplicate Content Pages</td>
                        <td>{{ detailed_metrics.seo_opportunities.duplicate_pages|default:"0" }}</td>
                        <td>Medium</td>
                    </tr>
                </table>
                {% if detailed_metrics.seo_opportunities.estimated_revenue_impact %}
                <p><strong>Estimated Annual Revenue Impact:</strong> ${{ detailed_metrics.seo_opportunities.estimated_revenue_impact|floatformat:0 }}</p>
                {% endif %}
                {% endif %}
            </div>
            {% endif %}
            
            <!-- Recommendations -->
            {% if recommendations %}
            <div class="section">
                <h2>Recommendations</h2>
                {% for rec in recommendations|slice:":10" %}
                <div class="recommendation">
                    <h3>{{ rec.title }}</h3>
                    <p>{{ rec.description }}</p>
                    <p>
                        <strong>Priority:</strong> {{ rec.priority }} | 
                        <strong>Effort:</strong> {{ rec.effort }} | 
                        <strong>Impact:</strong> {{ rec.impact }}
                    </p>
                </div>
                {% endfor %}
            </div>
            {% endif %}
            
            <!-- 30-60-90 Day Roadmap -->
            {% if roadmap %}
            <div class="section">
                <h2>Implementation Roadmap</h2>
                <div class="roadmap-timeline">
                    {% if roadmap.30_days %}
                    <div class="roadmap-phase">
                        <h4>30 Days</h4>
                        <ul>
                        {% for item in roadmap.30_days %}
                            <li>{{ item }}</li>
                        {% endfor %}
                        </ul>
                    </div>
                    {% endif %}
                    
                    {% if roadmap.60_days %}
                    <div class="roadmap-phase">
                        <h4>60 Days</h4>
                        <ul>
                        {% for item in roadmap.60_days %}
                            <li>{{ item }}</li>
                        {% endfor %}
                        </ul>
                    </div>
                    {% endif %}
                    
                    {% if roadmap.90_days %}
                    <div class="roadmap-phase">
                        <h4>90 Days</h4>
                        <ul>
                        {% for item in roadmap.90_days %}
                            <li>{{ item }}</li>
                        {% endfor %}
                        </ul>
                    </div>
                    {% endif %}
                </div>
            </div>
            {% endif %}
            
            <div class="footer">
                <p>Generated by DocAnalyzer - Professional Documentation Analysis</p>
                <p>© {{ generation_date|date:"Y" }} - Confidential Report</p>
            </div>
        </body>
        </html>
        """
        
        template = Template(template_string)
        html = template.render(Context(context))
        return html
    
    def _generate_charts(self):
        """Generate charts for the report"""
        charts = {}
        
        try:
            # 1. Documentation Type Distribution
            doc_type_dist = self.pages.values('doc_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            if doc_type_dist:
                fig, ax = plt.subplots(figsize=(10, 6))
                types = [item['doc_type'] for item in doc_type_dist]
                counts = [item['count'] for item in doc_type_dist]
                
                ax.bar(types, counts, color='#667eea')
                ax.set_xlabel('Document Type')
                ax.set_ylabel('Count')
                ax.set_title('Documentation Type Distribution')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                
                # Convert to base64
                buffer = BytesIO()
                plt.savefig(buffer, format='png')
                buffer.seek(0)
                image_base64 = base64.b64encode(buffer.read()).decode()
                charts['doc_type_distribution'] = f"data:image/png;base64,{image_base64}"
                plt.close()
            
            # 2. Readability Score Distribution
            readability_scores = list(self.pages.exclude(
                readability_score__isnull=True
            ).values_list('readability_score', flat=True))
            
            if readability_scores:
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.hist(readability_scores, bins=20, color='#764ba2', alpha=0.7)
                ax.axvline(x=60, color='green', linestyle='--', label='Target (60+)')
                ax.set_xlabel('Readability Score')
                ax.set_ylabel('Number of Pages')
                ax.set_title('Readability Score Distribution')
                ax.legend()
                plt.tight_layout()
                
                buffer = BytesIO()
                plt.savefig(buffer, format='png')
                buffer.seek(0)
                image_base64 = base64.b64encode(buffer.read()).decode()
                charts['readability_distribution'] = f"data:image/png;base64,{image_base64}"
                plt.close()
            
            # 3. Content Depth Distribution
            depth_dist = self.pages.values('depth').annotate(
                count=Count('id')
            ).order_by('depth')
            
            if depth_dist:
                fig, ax = plt.subplots(figsize=(10, 6))
                depths = [item['depth'] for item in depth_dist]
                counts = [item['count'] for item in depth_dist]
                
                ax.plot(depths, counts, marker='o', linewidth=2, markersize=8, color='#667eea')
                ax.fill_between(depths, counts, alpha=0.3, color='#667eea')
                ax.set_xlabel('Page Depth')
                ax.set_ylabel('Number of Pages')
                ax.set_title('Content Depth Distribution')
                ax.grid(True, alpha=0.3)
                plt.tight_layout()
                
                buffer = BytesIO()
                plt.savefig(buffer, format='png')
                buffer.seek(0)
                image_base64 = base64.b64encode(buffer.read()).decode()
                charts['depth_distribution'] = f"data:image/png;base64,{image_base64}"
                plt.close()
            
        except Exception as e:
            print(f"Error generating charts: {str(e)}")
        
        return charts
    
    def html_to_pdf(self, html_content):
        """Convert HTML to PDF using WeasyPrint"""
        
        if not WEASYPRINT_AVAILABLE:
            raise ImportError(
                "WeasyPrint is not installed. Install it with: pip install weasyprint"
            )
        
        # Create PDF
        pdf = HTML(string=html_content).write_pdf()
        
        return pdf
    
    def save_report(self, output_path, format='html'):
        """Save report to file"""
        
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == 'html':
            content = self.generate_html()
            with open(path, 'w') as f:
                f.write(content)
        
        elif format == 'pdf':
            html_content = self.generate_html()
            pdf_content = self.html_to_pdf(html_content)
            with open(path, 'wb') as f:
                f.write(pdf_content)
        
        elif format == 'json':
            with open(path, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
        
        return path
