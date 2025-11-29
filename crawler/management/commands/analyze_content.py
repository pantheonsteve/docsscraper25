"""
Management command to analyze crawled pages with AI for rich metadata extraction.

Usage:
    python manage.py analyze_content --job-id 57
    python manage.py analyze_content --job-id 57 --limit 10  # test first
    python manage.py analyze_content --client-id 3 --force
    python manage.py analyze_content --page-id 123
    python manage.py analyze_content --dry-run --job-id 57  # cost estimation
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from decouple import config

from crawler.models import CrawledPage
from crawler.content_analyzer import ContentAnalyzer


class Command(BaseCommand):
    help = "Analyze crawled pages with AI to extract topics, learning objectives, and prerequisites."

    def add_arguments(self, parser):
        parser.add_argument(
            "--page-id",
            type=int,
            help="Analyze a single page ID",
        )
        parser.add_argument(
            "--job-id",
            type=int,
            help="Analyze all pages in a given job",
        )
        parser.add_argument(
            "--client-id",
            type=int,
            help="Analyze all pages for a given client",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Maximum number of pages to process (useful for testing)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-analyze pages even if they already have AI analysis",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be analyzed and estimate costs without processing",
        )

    def handle(self, *args, **options):
        # Get API key
        api_key = config("OPENAI_API_KEY", default=None) or config("OPENAI_KEY", default=None)
        if not api_key:
            raise CommandError(
                "OPENAI_API_KEY is not set. Please add it to your .env file."
            )

        page_id = options.get("page_id")
        job_id = options.get("job_id")
        client_id = options.get("client_id")
        limit = options.get("limit")
        force = options.get("force")
        dry_run = options.get("dry_run")

        # Build queryset
        queryset = CrawledPage.objects.all()
        
        if page_id:
            queryset = queryset.filter(id=page_id)
        if job_id:
            queryset = queryset.filter(job_id=job_id)
        if client_id:
            queryset = queryset.filter(client_id=client_id)

        # Only analyze pages with content
        queryset = queryset.exclude(main_content__isnull=True).exclude(main_content="")

        # Skip pages that already have AI analysis (unless --force)
        if not force:
            queryset = queryset.filter(
                Q(ai_topics__isnull=True) | Q(ai_topics=[])
            )
        
        # Skip certain doc types to save costs
        # Note: 'unknown' is NOT skipped because AI analysis reclassifies pages
        skip_types = ['navigation', 'landing', 'changelog']
        queryset = queryset.exclude(doc_type__in=skip_types)

        if limit:
            queryset = queryset.order_by("id")[:limit]

        total = queryset.count()
        if total == 0:
            self.stdout.write("No pages to analyze (check filters or use --force).")
            return

        # Dry run: estimate costs
        if dry_run:
            self._dry_run(queryset, total)
            return

        self.stdout.write(
            self.style.SUCCESS(f"Starting AI analysis for {total} page(s)...")
        )
        self.stdout.write(f"Using GPT-4o-mini (estimated cost: ${total * 0.00015:.4f})")

        # Initialize analyzer
        analyzer = ContentAnalyzer(openai_api_key=api_key)

        # Process pages
        success_count = 0
        error_count = 0
        
        for idx, page in enumerate(queryset.iterator(), 1):
            try:
                self.stdout.write(
                    f"\n[{idx}/{total}] Analyzing page {page.id}: {page.url[:80]}..."
                )
                
                result = analyzer.analyze_page(
                    page_id=page.id,
                    url=page.url,
                    title=page.title,
                    main_content=page.main_content,
                    sections=page.sections or [],
                    doc_type=page.doc_type,
                    existing_prerequisites=page.prerequisites or [],
                    existing_learning_objectives=page.learning_objectives or [],
                    has_code_examples=page.has_examples,
                    has_images=bool(page.images),
                    has_videos=page.has_videos,
                    word_count=page.word_count or 0,
                )
                
                # Save results - core fields
                page.ai_topics = result["ai_topics"]
                page.ai_learning_objectives = result["ai_learning_objectives"]
                page.ai_prerequisite_chain = result["ai_prerequisite_chain"]
                page.ai_analysis_metadata = result["ai_analysis_metadata"]
                
                # Save results - enhanced fields
                page.ai_summary = result.get("ai_summary", "")
                page.ai_audience_level = result.get("ai_audience_level", "")
                page.ai_key_concepts = result.get("ai_key_concepts", [])
                page.ai_doc_type = result.get("ai_doc_type", "")
                page.ai_quality_indicators = result.get("ai_quality_indicators", {})
                page.ai_related_topics = result.get("ai_related_topics", [])
                
                # Update original doc_type with AI classification if available
                # This makes the AI classification visible in the main doc_type field
                if page.ai_doc_type:
                    # Map AI doc types to model choices (handle both formats)
                    doc_type_mapping = {
                        'api-reference': 'api_reference',
                        'how-to': 'guide',  # Map how-to to guide
                        'tutorial': 'tutorial',
                        'reference': 'api_reference',
                        'guide': 'guide',
                        'concept': 'concept',
                        'troubleshooting': 'troubleshooting',
                        'quickstart': 'quickstart',
                        'example': 'example',
                        'faq': 'faq',
                        'changelog': 'changelog',
                    }
                    mapped_type = doc_type_mapping.get(page.ai_doc_type.lower(), page.doc_type)
                    if mapped_type != page.doc_type:
                        page.doc_type = mapped_type
                
                # Merge with existing fields (optional enhancement)
                enhanced_prereqs, enhanced_los = analyzer.merge_with_existing(
                    ai_result=result,
                    existing_prerequisites=page.prerequisites or [],
                    existing_learning_objectives=page.learning_objectives or [],
                )
                page.prerequisites = enhanced_prereqs
                page.learning_objectives = enhanced_los
                page.has_prerequisites = len(enhanced_prereqs) > 0
                page.has_learning_objectives = len(enhanced_los) > 0
                
                # Generate learning objective embeddings
                if result["ai_learning_objectives"]:
                    page_context = f"{page.title}"
                    lo_embeddings = analyzer.generate_learning_objective_embeddings(
                        learning_objectives=result["ai_learning_objectives"],
                        page_context=page_context
                    )
                    page.learning_objective_embeddings = lo_embeddings
                else:
                    page.learning_objective_embeddings = []
                
                page.save(update_fields=[
                    # Core AI fields
                    'ai_topics',
                    'ai_learning_objectives',
                    'ai_prerequisite_chain',
                    'ai_analysis_metadata',
                    # Enhanced AI fields
                    'ai_summary',
                    'ai_audience_level',
                    'ai_key_concepts',
                    'ai_doc_type',
                    'ai_quality_indicators',
                    'ai_related_topics',
                    # Merged fields
                    'prerequisites',
                    'learning_objectives',
                    'has_prerequisites',
                    'has_learning_objectives',
                    # Learning objective embeddings
                    'learning_objective_embeddings',
                    # Update original doc_type with AI classification
                    'doc_type',
                ])
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ {len(result['ai_topics'])} topics, "
                        f"{len(result['ai_learning_objectives'])} LOs, "
                        f"{len(result['ai_prerequisite_chain'])} prereqs, "
                        f"{len(result.get('ai_key_concepts', []))} concepts "
                        f"[{result.get('ai_audience_level', 'unknown')}]"
                    )
                )
                success_count += 1
                
            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(f"  ✗ Error analyzing page {page.id}: {exc}")
                )
                error_count += 1
                continue

        # Summary
        self.stdout.write("\n" + "="*60)
        self.stdout.write(
            self.style.SUCCESS(
                f"Analysis completed: {success_count} successful, {error_count} errors"
            )
        )
        if success_count > 0:
            estimated_cost = success_count * 0.00015
            self.stdout.write(f"Estimated cost: ${estimated_cost:.4f}")

    def _dry_run(self, queryset, total):
        """Show what would be analyzed and estimate costs."""
        self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))
        self.stdout.write(f"\nPages to analyze: {total}")
        
        # Show sample pages
        self.stdout.write("\nSample pages:")
        for page in queryset[:5]:
            self.stdout.write(
                f"  - Page {page.id}: {page.title[:60]} ({page.doc_type})"
            )
        
        if total > 5:
            self.stdout.write(f"  ... and {total - 5} more")
        
        # Cost estimation
        estimated_cost = total * 0.00015
        self.stdout.write(f"\nEstimated cost: ${estimated_cost:.4f} (at $0.00015/page)")
        self.stdout.write(f"Estimated time: {total * 2:.0f} seconds ({total * 2 / 60:.1f} minutes)")
        
        self.stdout.write(
            self.style.SUCCESS(
                "\nTo proceed with analysis, run without --dry-run flag."
            )
        )

