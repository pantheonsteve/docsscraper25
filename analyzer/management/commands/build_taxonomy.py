"""
Build documentation taxonomy for a client.

This command:
1. Loads all AI-analyzed pages for a client
2. Clusters pages by embedding similarity
3. Builds prerequisite dependency graph
4. Generates cluster summaries with GPT-4o-mini
5. Exports taxonomy (JSON, Markdown, graphs)

Usage:
    # Basic usage
    python manage.py build_taxonomy --client-id 5
    
    # With options
    python manage.py build_taxonomy --client-id 5 \
        --output-dir ./taxonomies/ \
        --embedding-type lo \
        --min-cluster-size 5 \
        --visualize
    
    # Dry run (show stats without generating)
    python manage.py build_taxonomy --client-id 5 --dry-run
"""

import os
import logging
from django.core.management.base import BaseCommand
from decouple import config
from analyzer.taxonomy_builder import TaxonomyBuilder

logger = logging.getLogger('analyzer')


class Command(BaseCommand):
    help = 'Build documentation taxonomy for a client'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--client-id',
            type=int,
            required=True,
            help='Client ID to analyze'
        )
        
        parser.add_argument(
            '--output-dir',
            type=str,
            default='./taxonomies/',
            help='Output directory for taxonomy files (default: ./taxonomies/)'
        )
        
        parser.add_argument(
            '--embedding-type',
            type=str,
            choices=['lo', 'page', 'section', 'hybrid'],
            default='lo',
            help='Which embeddings to use (default: lo = learning_objective_embeddings)'
        )
        
        parser.add_argument(
            '--min-cluster-size',
            type=int,
            default=3,
            help='Minimum pages per cluster (default: 3)'
        )
        
        parser.add_argument(
            '--max-cluster-size',
            type=int,
            default=15,
            help='Maximum pages per cluster (default: 15)'
        )
        
        parser.add_argument(
            '--n-clusters',
            type=str,
            default='auto',
            help='Number of clusters or "auto" to detect automatically (default: auto)'
        )
        
        parser.add_argument(
            '--clustering-method',
            type=str,
            choices=['kmeans', 'hierarchical', 'dbscan'],
            default='kmeans',
            help='Clustering algorithm to use (default: kmeans)'
        )
        
        parser.add_argument(
            '--visualize',
            action='store_true',
            help='Generate graph visualizations (requires graphviz)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show statistics without generating files'
        )
        
        parser.add_argument(
            '--filter-doc-type',
            type=str,
            nargs='*',
            help='Filter by doc types (e.g., tutorial guide concept)'
        )
        
        parser.add_argument(
            '--filter-audience',
            type=str,
            nargs='*',
            choices=['beginner', 'intermediate', 'advanced'],
            help='Filter by audience level'
        )
        
        parser.add_argument(
            '--skip-summaries',
            action='store_true',
            help='Skip GPT-4o-mini cluster summarization (faster, cheaper)'
        )
    
    def handle(self, *args, **options):
        client_id = options['client_id']
        output_dir = options['output_dir']
        embedding_type = options['embedding_type']
        min_cluster_size = options['min_cluster_size']
        max_cluster_size = options['max_cluster_size']
        n_clusters = options['n_clusters']
        clustering_method = options['clustering_method']
        visualize = options['visualize']
        dry_run = options['dry_run']
        skip_summaries = options['skip_summaries']
        
        # Map embedding type shorthand
        embedding_field_map = {
            'lo': 'learning_objective_embeddings',
            'page': 'page_embedding',
            'section': 'section_embeddings',
            'hybrid': 'learning_objective_embeddings',  # Default to LO for now
        }
        embedding_field = embedding_field_map.get(embedding_type, 'learning_objective_embeddings')
        
        # Get OpenAI API key
        openai_api_key = None
        if not skip_summaries:
            openai_api_key = config('OPENAI_API_KEY', default=None)
            if not openai_api_key:
                self.stdout.write(
                    self.style.WARNING(
                        "No OPENAI_API_KEY found. Cluster summaries will be skipped. "
                        "Use --skip-summaries to suppress this warning."
                    )
                )
        
        # Convert n_clusters
        if n_clusters != 'auto':
            try:
                n_clusters = int(n_clusters)
            except ValueError:
                self.stdout.write(self.style.ERROR(f"Invalid n_clusters: {n_clusters}"))
                return
        
        # Build filters
        filters = {}
        if options.get('filter_doc_type'):
            filters['doc_type'] = options['filter_doc_type']
        if options.get('filter_audience'):
            filters['audience_level'] = options['filter_audience']
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'='*60}\n"
                f"TAXONOMY BUILDER\n"
                f"{'='*60}\n"
            )
        )
        
        self.stdout.write(f"Client ID: {client_id}")
        self.stdout.write(f"Embedding Type: {embedding_type} ({embedding_field})")
        self.stdout.write(f"Clustering Method: {clustering_method}")
        self.stdout.write(f"Cluster Size: {min_cluster_size}-{max_cluster_size} pages")
        self.stdout.write(f"Output Directory: {output_dir}")
        if filters:
            self.stdout.write(f"Filters: {filters}")
        self.stdout.write(f"Dry Run: {dry_run}\n")
        
        # Initialize builder
        try:
            builder = TaxonomyBuilder(
                client_id=client_id,
                embedding_field=embedding_field,
                openai_api_key=openai_api_key
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error initializing builder: {e}"))
            return
        
        # Step 1: Load pages
        self.stdout.write(self.style.SUCCESS("\n[1/5] Loading pages..."))
        try:
            pages = builder.load_pages(filters=filters if filters else None)
            
            if not pages:
                self.stdout.write(self.style.ERROR("No pages found for this client."))
                return
            
            self.stdout.write(f"  ✓ Loaded {len(pages)} pages")
            
            if len(builder.embeddings) == 0:
                self.stdout.write(
                    self.style.ERROR(
                        f"No embeddings found. Make sure pages have {embedding_field}.\n"
                        f"Run: python manage.py generate_embeddings --client-id {client_id}"
                    )
                )
                return
            
            self.stdout.write(f"  ✓ Prepared {len(builder.embeddings)} embeddings")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error loading pages: {e}"))
            import traceback
            traceback.print_exc()
            return
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n{'='*60}\n"
                    f"DRY RUN - Statistics\n"
                    f"{'='*60}\n"
                )
            )
            self.stdout.write(f"Total pages: {len(pages)}")
            self.stdout.write(f"Total embeddings: {len(builder.embeddings)}")
            self.stdout.write(f"Embedding dimension: {builder.embeddings.shape[1]}")
            
            # Show page type distribution
            from collections import Counter
            doc_types = Counter(p.doc_type for p in pages)
            self.stdout.write(f"\nDoc type distribution:")
            for doc_type, count in doc_types.most_common():
                self.stdout.write(f"  - {doc_type}: {count}")
            
            audience_levels = Counter(p.ai_audience_level for p in pages if p.ai_audience_level)
            if audience_levels:
                self.stdout.write(f"\nAudience level distribution:")
                for level, count in audience_levels.most_common():
                    self.stdout.write(f"  - {level}: {count}")
            
            return
        
        # Step 2: Cluster
        self.stdout.write(self.style.SUCCESS("\n[2/5] Clustering pages..."))
        try:
            clusters = builder.cluster_by_embeddings(
                n_clusters=n_clusters,
                method=clustering_method,
                min_cluster_size=min_cluster_size,
                max_cluster_size=max_cluster_size
            )
            
            self.stdout.write(f"  ✓ Created {len(clusters)} clusters")
            
            # Show cluster sizes
            for cluster in clusters[:10]:  # Show first 10
                self.stdout.write(
                    f"    - Cluster {cluster['cluster_id']}: "
                    f"{cluster['size']} pages "
                    f"(cohesion: {cluster['cohesion']:.2f}, "
                    f"topic: {cluster['primary_topic']})"
                )
            
            if len(clusters) > 10:
                self.stdout.write(f"    ... and {len(clusters) - 10} more clusters")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error clustering: {e}"))
            import traceback
            traceback.print_exc()
            return
        
        # Step 3: Build prerequisite graph
        self.stdout.write(self.style.SUCCESS("\n[3/5] Building prerequisite graph..."))
        try:
            graph = builder.build_prerequisite_graph()
            
            self.stdout.write(
                f"  ✓ Graph built: {graph.number_of_nodes()} nodes, "
                f"{graph.number_of_edges()} edges"
            )
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error building graph: {e}"))
            import traceback
            traceback.print_exc()
            return
        
        # Step 4: Generate cluster summaries
        self.stdout.write(self.style.SUCCESS("\n[4/5] Generating cluster summaries..."))
        
        if skip_summaries or not openai_api_key:
            self.stdout.write("  ⊘ Skipped (no OpenAI API key or --skip-summaries)")
            builder.cluster_summaries = {}
        else:
            try:
                summaries = builder.generate_cluster_summaries()
                self.stdout.write(f"  ✓ Generated {len(summaries)} summaries")
                
                # Show sample summaries
                for cluster_id, summary in list(summaries.items())[:3]:
                    self.stdout.write(
                        f"    - Cluster {cluster_id}: {summary.get('name', 'Unknown')}"
                    )
                
                if len(summaries) > 3:
                    self.stdout.write(f"    ... and {len(summaries) - 3} more")
                
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error generating summaries: {e}"))
                self.stdout.write("  → Continuing without summaries")
                builder.cluster_summaries = {}
        
        # Step 5: Generate taxonomy
        self.stdout.write(self.style.SUCCESS("\n[5/5] Generating taxonomy..."))
        try:
            taxonomy = builder.generate_taxonomy()
            
            self.stdout.write(
                f"  ✓ Taxonomy generated: "
                f"{taxonomy['statistics']['total_topics']} topics, "
                f"{taxonomy['statistics']['total_clusters']} clusters"
            )
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error generating taxonomy: {e}"))
            import traceback
            traceback.print_exc()
            return
        
        # Export
        self.stdout.write(self.style.SUCCESS(f"\n[Export] Saving to {output_dir}..."))
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            output_files = builder.export_all(output_dir)
            
            self.stdout.write("  ✓ Exported files:")
            for file_type, filepath in output_files.items():
                self.stdout.write(f"    - {file_type}: {filepath}")
            
            # Optionally generate PNG visualization
            if visualize:
                self.stdout.write("\n  [Visualization] Attempting to render graph...")
                try:
                    png_path = output_files['dot'].replace('.dot', '.png')
                    builder.visualize_graph(png_path, format='png')
                    self.stdout.write(f"    ✓ Graph PNG: {png_path}")
                except Exception as viz_error:
                    self.stdout.write(
                        self.style.WARNING(
                            f"    ⊘ PNG rendering failed: {viz_error}\n"
                            f"    Install graphviz: brew install graphviz (macOS) or apt install graphviz (Linux)"
                        )
                    )
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error exporting: {e}"))
            import traceback
            traceback.print_exc()
            return
        
        # Final summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'='*60}\n"
                f"✓ TAXONOMY BUILD COMPLETE\n"
                f"{'='*60}\n"
            )
        )
        
        # Show statistics report
        report = builder.generate_statistics_report()
        self.stdout.write("\n" + report)
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'='*60}\n"
                f"Next steps:\n"
                f"  1. Review: {output_files['markdown']}\n"
                f"  2. Visualize: {output_files['mermaid']}\n"
                f"  3. Analyze: {output_files['report']}\n"
                f"{'='*60}\n"
            )
        )

