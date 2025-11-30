"""
Documentation Taxonomy Builder

Analyzes AI-processed documentation pages to:
1. Cluster pages by semantic similarity (using embeddings)
2. Build prerequisite graphs (using ai_prerequisite_chain)
3. Generate cluster summaries (using GPT-4o-mini)
4. Export hierarchical taxonomy (JSON + Markdown)

Usage:
    from analyzer.taxonomy_builder import TaxonomyBuilder
    
    builder = TaxonomyBuilder(client_id=5)
    builder.load_pages()
    builder.cluster_by_embeddings(n_clusters='auto')
    builder.build_prerequisite_graph()
    builder.generate_cluster_summaries()
    taxonomy = builder.generate_taxonomy()
    builder.export_json('output.json')
    builder.export_markdown('output.md')
"""

import logging
import json
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
from collections import defaultdict, Counter
from sklearn.cluster import KMeans, AgglomerativeClustering, DBSCAN
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_similarity
import networkx as nx

logger = logging.getLogger('analyzer')


class TaxonomyBuilder:
    """
    Build documentation taxonomy from AI-analyzed pages.
    
    Multi-level approach:
    1. Cluster pages by embedding similarity
    2. Build prerequisite dependency graph
    3. Generate cluster summaries with GPT-4o-mini
    4. Assemble hierarchical taxonomy
    """
    
    def __init__(
        self, 
        client_id: int,
        embedding_field: str = 'learning_objective_embeddings',
        openai_api_key: Optional[str] = None
    ):
        """
        Initialize taxonomy builder.
        
        Args:
            client_id: Client ID to analyze
            embedding_field: Which embeddings to use (learning_objective_embeddings, page_embedding, section_embeddings)
            openai_api_key: OpenAI API key for cluster summarization
        """
        self.client_id = client_id
        self.embedding_field = embedding_field
        self.openai_api_key = openai_api_key
        
        # Data storage
        self.client = None
        self.pages = []
        self.embeddings = None
        self.page_metadata = []
        
        # Analysis results
        self.clusters = []
        self.cluster_labels = None
        self.cluster_summaries = {}
        self.prerequisite_graph = None
        self.taxonomy = {}
        
        logger.info(f"[TaxonomyBuilder] Initialized for client {client_id}, using {embedding_field}")
    
    def load_pages(
        self,
        filters: Optional[Dict] = None,
        min_quality_score: float = 0.0
    ) -> List:
        """
        Load analyzed pages from database.
        
        Args:
            filters: Optional filters (doc_type, audience_level, etc.)
            min_quality_score: Minimum AI quality score (0.0-1.0)
            
        Returns:
            List of CrawledPage objects
        """
        from crawler.models import CrawledPage
        from core.models import Client
        from django.db.models import Q
        
        logger.info(f"[TaxonomyBuilder] Loading pages for client {self.client_id}")
        
        # Get client
        self.client = Client.objects.get(id=self.client_id)
        
        # Base query: pages with AI analysis and embeddings
        queryset = CrawledPage.objects.filter(client_id=self.client_id)
        
        # Must have AI analysis
        queryset = queryset.exclude(Q(ai_topics__isnull=True) | Q(ai_topics=[]))
        
        # Apply filters
        if filters:
            if 'doc_type' in filters:
                queryset = queryset.filter(doc_type__in=filters['doc_type'])
            if 'audience_level' in filters:
                queryset = queryset.filter(ai_audience_level__in=filters['audience_level'])
            if 'ai_doc_type' in filters:
                queryset = queryset.filter(ai_doc_type__in=filters['ai_doc_type'])
        
        # Quality filter
        if min_quality_score > 0:
            # Filter by completeness score from quality indicators
            # This requires iterating, so we'll do it in Python
            pass
        
        # Fetch pages
        self.pages = list(queryset.select_related('job', 'client'))
        
        logger.info(f"[TaxonomyBuilder] Loaded {len(self.pages)} pages")
        
        # Build embeddings matrix and metadata
        self._prepare_embeddings()
        
        return self.pages
    
    def _prepare_embeddings(self):
        """
        Extract and prepare embeddings for clustering.
        
        Handles different embedding types (LO, page, section).
        For LO embeddings, aggregates multiple LOs per page into a single page-level embedding.
        """
        embeddings_list = []
        metadata_list = []
        
        for page in self.pages:
            if self.embedding_field == 'learning_objective_embeddings':
                # Aggregate learning objective embeddings to page level
                # Strategy: average all LO embeddings for the page
                lo_embeddings = page.learning_objective_embeddings or []
                lo_vectors = [lo.get('embedding', []) for lo in lo_embeddings if lo.get('embedding')]
                
                if lo_vectors:
                    # Average all LO embeddings for this page
                    avg_embedding = np.mean(lo_vectors, axis=0)
                    embeddings_list.append(avg_embedding)
                    metadata_list.append({
                        'page_id': page.id,
                        'page_title': page.title,
                        'page_url': page.url,
                        'doc_type': page.doc_type,
                        'ai_doc_type': page.ai_doc_type,
                        'audience_level': page.ai_audience_level,
                        'topics': page.ai_topics or [],
                        'learning_objectives': [lo.get('objective', '') for lo in lo_embeddings],
                        'num_los': len(lo_vectors),
                        'type': 'page_from_lo'
                    })
            
            elif self.embedding_field == 'page_embedding':
                # Use full-page embeddings (one per page)
                embedding = page.page_embedding or []
                if embedding:
                    embeddings_list.append(embedding)
                    metadata_list.append({
                        'page_id': page.id,
                        'page_title': page.title,
                        'page_url': page.url,
                        'doc_type': page.doc_type,
                        'ai_doc_type': page.ai_doc_type,
                        'audience_level': page.ai_audience_level,
                        'topics': page.ai_topics or [],
                        'learning_objectives': page.ai_learning_objectives or [],
                        'type': 'page'
                    })
            
            elif self.embedding_field == 'section_embeddings':
                # Use section embeddings (multiple per page)
                section_embeds = page.section_embeddings or []
                for section in section_embeds:
                    embedding = section.get('embedding', [])
                    if embedding:
                        embeddings_list.append(embedding)
                        metadata_list.append({
                            'page_id': page.id,
                            'page_title': page.title,
                            'page_url': page.url,
                            'section_heading': section.get('heading', ''),
                            'section_index': section.get('index', 0),
                            'doc_type': page.doc_type,
                            'topics': page.ai_topics or [],
                            'type': 'section'
                        })
        
        if not embeddings_list:
            logger.warning(f"[TaxonomyBuilder] No embeddings found for client {self.client_id}")
            self.embeddings = np.array([])
            self.page_metadata = []
            return
        
        self.embeddings = np.array(embeddings_list)
        self.page_metadata = metadata_list
        
        logger.info(
            f"[TaxonomyBuilder] Prepared {len(embeddings_list)} embeddings "
            f"(dim: {self.embeddings.shape[1]})"
        )
    
    def cluster_by_embeddings(
        self,
        n_clusters: Any = 'auto',
        method: str = 'kmeans',
        min_cluster_size: int = 3,
        max_cluster_size: int = 15
    ) -> List[Dict]:
        """
        Cluster pages by embedding similarity.
        
        Args:
            n_clusters: Number of clusters or 'auto' to determine automatically
            method: 'kmeans', 'hierarchical', or 'dbscan'
            min_cluster_size: Minimum pages per cluster
            max_cluster_size: Maximum pages per cluster
            
        Returns:
            List of cluster dictionaries
        """
        if len(self.embeddings) == 0:
            logger.warning("[TaxonomyBuilder] No embeddings to cluster")
            return []
        
        logger.info(f"[TaxonomyBuilder] Clustering {len(self.embeddings)} embeddings using {method}")
        
        # Determine optimal number of clusters if auto
        if n_clusters == 'auto':
            n_clusters = self._find_optimal_clusters(
                min_k=max(2, len(self.embeddings) // max_cluster_size),
                max_k=min(20, len(self.embeddings) // min_cluster_size)
            )
            logger.info(f"[TaxonomyBuilder] Auto-detected optimal clusters: {n_clusters}")
        
        # Cluster using selected method
        if method == 'kmeans':
            clusterer = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            self.cluster_labels = clusterer.fit_predict(self.embeddings)
        
        elif method == 'hierarchical':
            clusterer = AgglomerativeClustering(n_clusters=n_clusters, linkage='ward')
            self.cluster_labels = clusterer.fit_predict(self.embeddings)
        
        elif method == 'dbscan':
            # DBSCAN auto-determines clusters based on density
            clusterer = DBSCAN(eps=0.3, min_samples=min_cluster_size, metric='cosine')
            self.cluster_labels = clusterer.fit_predict(self.embeddings)
            n_clusters = len(set(self.cluster_labels)) - (1 if -1 in self.cluster_labels else 0)
            logger.info(f"[TaxonomyBuilder] DBSCAN found {n_clusters} clusters")
        
        else:
            raise ValueError(f"Unknown clustering method: {method}")
        
        # Calculate silhouette score
        if len(set(self.cluster_labels)) > 1:
            score = silhouette_score(self.embeddings, self.cluster_labels)
            logger.info(f"[TaxonomyBuilder] Silhouette score: {score:.3f}")
        
        # Build cluster objects
        self.clusters = self._build_cluster_objects()
        
        logger.info(f"[TaxonomyBuilder] Created {len(self.clusters)} clusters")
        
        return self.clusters
    
    def _find_optimal_clusters(self, min_k: int = 2, max_k: int = 20) -> int:
        """
        Find optimal number of clusters using elbow method + silhouette score.
        
        Args:
            min_k: Minimum clusters to try
            max_k: Maximum clusters to try
            
        Returns:
            Optimal number of clusters
        """
        inertias = []
        silhouettes = []
        k_range = range(max(2, min_k), min(max_k + 1, len(self.embeddings) // 2))
        
        for k in k_range:
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(self.embeddings)
            inertias.append(kmeans.inertia_)
            
            if len(set(labels)) > 1:
                score = silhouette_score(self.embeddings, labels)
                silhouettes.append(score)
            else:
                silhouettes.append(0)
        
        # Find elbow point (max second derivative)
        if len(k_range) == 0 or len(silhouettes) == 0:
            # Fallback to reasonable default
            logger.warning("[TaxonomyBuilder] Could not determine optimal clusters, using default: 10")
            return min(10, len(self.embeddings) // 15)
        
        if len(inertias) >= 3 and len(second_derivatives) > 0:
            second_derivatives = []
            for i in range(1, len(inertias) - 1):
                second_deriv = inertias[i-1] - 2*inertias[i] + inertias[i+1]
                second_derivatives.append(second_deriv)
            
            if second_derivatives:
                # Combine elbow and silhouette
                # Weight: 60% silhouette, 40% elbow
                best_idx = 0
                best_score = -1
                for i, (sil, k) in enumerate(zip(silhouettes, k_range)):
                    if i < len(second_derivatives):
                        normalized_elbow = second_derivatives[i] / max(second_derivatives)
                        combined_score = 0.6 * sil + 0.4 * normalized_elbow
                        if combined_score > best_score:
                            best_score = combined_score
                            best_idx = i
                
                optimal_k = list(k_range)[best_idx]
            else:
                optimal_k = list(k_range)[silhouettes.index(max(silhouettes))]
        else:
            # Fallback: use silhouette only
            if silhouettes:
                optimal_k = list(k_range)[silhouettes.index(max(silhouettes))]
            else:
                optimal_k = list(k_range)[0] if k_range else 10
        
        return optimal_k
    
    def _build_cluster_objects(self) -> List[Dict]:
        """
        Build cluster objects with metadata.
        
        Returns:
            List of cluster dictionaries
        """
        clusters = []
        
        # Convert cluster_labels to list of ints to handle numpy types
        unique_labels = set(int(label) for label in self.cluster_labels)
        
        logger.debug(f"[_build_cluster_objects] Processing {len(unique_labels)} unique labels")
        
        for cluster_id in unique_labels:
            if cluster_id == -1:  # DBSCAN noise
                continue
            
            try:
                # Get items in this cluster - need to compare with int
                cluster_indices = [i for i, label in enumerate(self.cluster_labels) if int(label) == cluster_id]
                cluster_metadata = [self.page_metadata[i] for i in cluster_indices]
                
                # Get unique pages in cluster
                page_ids = list(set(item['page_id'] for item in cluster_metadata))
                cluster_pages = [p for p in self.pages if p.id in page_ids]
                
                logger.debug(f"[_build_cluster_objects] Cluster {cluster_id}: {len(cluster_pages)} pages")
                
                # Extract cluster characteristics
                topics = []
                learning_objectives = []
                doc_types = []
                audience_levels = []
                
                for item in cluster_metadata:
                    item_topics = item.get('topics', [])
                    if item_topics:
                        topics.extend(item_topics)
                    doc_types.append(item.get('doc_type', 'unknown'))
                    if item.get('audience_level'):
                        audience_levels.append(item['audience_level'])
                    # Handle both old (objective) and new (learning_objectives) formats
                    if item.get('objective'):
                        learning_objectives.append(item['objective'])
                    elif item.get('learning_objectives'):
                        learning_objectives.extend(item['learning_objectives'])
                
                # Find most common topic
                topic_names = [t.get('name', '') for t in topics if isinstance(t, dict)]
                topic_counter = Counter(topic_names)
                primary_topic = topic_counter.most_common(1)[0][0] if topic_counter else "Unknown"
                
                # Most common doc type
                doc_type_counter = Counter(doc_types)
                primary_doc_type = doc_type_counter.most_common(1)[0][0] if doc_type_counter else "unknown"
                
                # Most common audience level
                audience_counter = Counter(audience_levels)
                primary_audience = audience_counter.most_common(1)[0][0] if audience_counter else "intermediate"
                
                # Calculate cluster cohesion (avg intra-cluster similarity)
                cluster_embeddings = self.embeddings[cluster_indices]
                if len(cluster_embeddings) > 1:
                    similarities = cosine_similarity(cluster_embeddings)
                    # Get upper triangle (exclude diagonal and duplicates)
                    triu_indices = np.triu_indices_from(similarities, k=1)
                    cohesion = similarities[triu_indices].mean()
                else:
                    cohesion = 1.0
                
                cluster_obj = {
                    'cluster_id': cluster_id,
                    'size': len(page_ids),
                    'pages': cluster_pages,
                    'page_ids': page_ids,
                    'primary_topic': primary_topic,
                    'primary_doc_type': primary_doc_type,
                    'primary_audience': primary_audience,
                    'learning_objectives': learning_objectives,
                    'topics': topics,
                    'cohesion': float(cohesion),
                    'metadata_items': cluster_metadata,
                }
                
                clusters.append(cluster_obj)
                logger.debug(f"[_build_cluster_objects] Added cluster {cluster_id}")
                
            except Exception as e:
                logger.error(f"[_build_cluster_objects] Error building cluster {cluster_id}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Sort by size (largest first)
        clusters.sort(key=lambda x: x['size'], reverse=True)
        
        return clusters
    
    def build_prerequisite_graph(self) -> nx.DiGraph:
        """
        Build prerequisite dependency graph from ai_prerequisite_chain.
        
        Creates a directed graph where:
        - Nodes: pages and concepts
        - Edges: prerequisite relationships
        
        Returns:
            NetworkX DiGraph
        """
        logger.info("[TaxonomyBuilder] Building prerequisite graph")
        
        G = nx.DiGraph()
        
        # Add all pages as nodes
        for page in self.pages:
            G.add_node(
                f"page_{page.id}",
                type='page',
                page_id=page.id,
                title=page.title,
                url=page.url,
                doc_type=page.doc_type,
                ai_doc_type=page.ai_doc_type,
                audience_level=page.ai_audience_level,
            )
        
        # Add prerequisite edges
        for page in self.pages:
            prereq_chain = page.ai_prerequisite_chain or []
            
            for prereq in prereq_chain:
                concept = prereq.get('concept', '')
                prereq_type = prereq.get('type', 'knowledge')
                importance = prereq.get('importance', 'recommended')
                
                if not concept:
                    continue
                
                # Add concept node if not exists
                concept_node_id = f"concept_{concept.lower().replace(' ', '_')[:50]}"
                if not G.has_node(concept_node_id):
                    G.add_node(
                        concept_node_id,
                        type='concept',
                        name=concept,
                        prereq_type=prereq_type,
                    )
                
                # Add edge: page requires concept
                weight = {'essential': 3, 'recommended': 2, 'optional': 1}.get(importance, 2)
                G.add_edge(
                    concept_node_id,
                    f"page_{page.id}",
                    weight=weight,
                    importance=importance,
                    prereq_type=prereq_type
                )
        
        # Add inter-page relationships based on shared concepts
        # If page A introduces concept X (is_new=true) and page B uses X, A -> B
        concept_to_introducing_page = {}
        
        for page in self.pages:
            key_concepts = page.ai_key_concepts or []
            for concept_obj in key_concepts:
                if concept_obj.get('is_new', False):
                    term = concept_obj.get('term', '')
                    if term:
                        concept_to_introducing_page[term.lower()] = page.id
        
        # Now create edges where pages use concepts introduced elsewhere
        for page in self.pages:
            key_concepts = page.ai_key_concepts or []
            for concept_obj in key_concepts:
                if not concept_obj.get('is_new', True):  # Assumed known
                    term = concept_obj.get('term', '').lower()
                    if term in concept_to_introducing_page:
                        source_page_id = concept_to_introducing_page[term]
                        if source_page_id != page.id:
                            # Add edge: source page -> current page
                            G.add_edge(
                                f"page_{source_page_id}",
                                f"page_{page.id}",
                                weight=2,
                                relationship='introduces_concept',
                                concept=term
                            )
        
        self.prerequisite_graph = G
        
        # Check for cycles
        try:
            cycles = list(nx.simple_cycles(G))
            if cycles:
                logger.warning(f"[TaxonomyBuilder] Found {len(cycles)} cycles in prerequisite graph")
                # Break cycles by removing lowest-weight edges
                for cycle in cycles[:10]:  # Handle first 10 cycles
                    if len(cycle) >= 2:
                        # Find weakest edge in cycle
                        min_weight = float('inf')
                        min_edge = None
                        for i in range(len(cycle)):
                            u, v = cycle[i], cycle[(i + 1) % len(cycle)]
                            if G.has_edge(u, v):
                                weight = G[u][v].get('weight', 1)
                                if weight < min_weight:
                                    min_weight = weight
                                    min_edge = (u, v)
                        if min_edge:
                            G.remove_edge(*min_edge)
                            logger.info(f"[TaxonomyBuilder] Removed edge {min_edge} to break cycle")
        except nx.NetworkXError:
            pass
        
        logger.info(
            f"[TaxonomyBuilder] Graph built: {G.number_of_nodes()} nodes, "
            f"{G.number_of_edges()} edges"
        )
        
        return G
    
    def generate_cluster_summaries(self) -> Dict[int, Dict]:
        """
        Generate summaries for each cluster using GPT-4o-mini.
        
        Returns:
            Dict mapping cluster_id to summary metadata
        """
        if not self.openai_api_key:
            logger.warning("[TaxonomyBuilder] No OpenAI API key, skipping cluster summaries")
            return {}
        
        from openai import OpenAI
        client = OpenAI(api_key=self.openai_api_key)
        
        logger.info(f"[TaxonomyBuilder] Generating summaries for {len(self.clusters)} clusters")
        
        summaries = {}
        
        for cluster in self.clusters:
            cluster_id = cluster['cluster_id']
            pages = cluster['pages']
            
            # Build prompt with cluster pages
            prompt = self._build_cluster_summary_prompt(cluster, pages)
            
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert technical documentation curator. Generate concise cluster summaries for grouping related documentation pages."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.3,
                    response_format={"type": "json_object"}
                )
                
                result = json.loads(response.choices[0].message.content)
                summaries[cluster_id] = result
                
                logger.info(
                    f"[TaxonomyBuilder] Cluster {cluster_id}: "
                    f"'{result.get('name', 'Unknown')}' ({cluster['size']} pages)"
                )
                
            except Exception as e:
                logger.error(f"[TaxonomyBuilder] Error summarizing cluster {cluster_id}: {e}")
                summaries[cluster_id] = {
                    'name': f"Cluster {cluster_id}",
                    'description': f"Group of {cluster['size']} related pages",
                    'error': str(e)
                }
        
        self.cluster_summaries = summaries
        return summaries
    
    def _build_cluster_summary_prompt(self, cluster: Dict, pages: List) -> str:
        """Build prompt for cluster summarization."""
        
        pages_info = []
        for page in pages[:10]:  # Limit to 10 pages to avoid token limits
            page_info = f"- {page.title}"
            if page.ai_summary:
                page_info += f": {page.ai_summary}"
            
            # Add key learning objectives
            los = page.ai_learning_objectives or []
            if los:
                lo_text = los[0].get('objective', '') if los else ''
                if lo_text:
                    page_info += f" | LO: {lo_text}"
            
            pages_info.append(page_info)
        
        if len(pages) > 10:
            pages_info.append(f"... and {len(pages) - 10} more pages")
        
        return f"""Analyze this cluster of related documentation pages and generate a summary.

**Cluster Info:**
- Size: {cluster['size']} pages
- Primary topic: {cluster['primary_topic']}
- Doc type: {cluster['primary_doc_type']}
- Audience: {cluster['primary_audience']}
- Cohesion: {cluster['cohesion']:.2f}

**Pages in cluster:**
{chr(10).join(pages_info)}

**Task:** Generate a JSON summary with this structure:
{{
  "name": "3-5 word module name",
  "description": "1-2 sentence description of what this module covers",
  "learning_outcomes": ["what users will know/be able to do after this module"],
  "prerequisites": ["concepts/skills needed before starting"],
  "difficulty": "beginner|intermediate|advanced",
  "estimated_hours": number (realistic time to complete all pages),
  "suggested_order": ["page_title_1", "page_title_2", ...] (optional: recommended reading order)
}}

Focus on:
1. Clear, actionable module name
2. Learning outcomes that span all pages in cluster
3. Prerequisites common to the module
4. Realistic difficulty and time estimates

Return valid JSON only."""
    
    def build_topic_hierarchy(self, all_categories: set = None) -> Dict[str, Dict]:
        """
        Build hierarchical topic structure by grouping clusters into parent categories.
        Uses GPT-4 to intelligently group based on actual cluster names.
        
        Args:
            all_categories: (Deprecated) Set of flat topic category names
            
        Returns:
            Dict mapping parent category name to cluster IDs
        """
        if not self.openai_api_key:
            logger.warning("[TaxonomyBuilder] No OpenAI API key, skipping topic hierarchy")
            # Return flat structure with all clusters in one category
            return {'Documentation': {
                'name': 'Documentation',
                'description': 'All documentation modules',
                'cluster_ids': [c['cluster_id'] for c in self.clusters]
            }}
        
        from openai import OpenAI
        client = OpenAI(api_key=self.openai_api_key)
        
        logger.info(f"[TaxonomyBuilder] Building topic hierarchy for {len(self.clusters)} clusters")
        
        # Build prompt with actual cluster names and their primary topics
        clusters_info = []
        for cluster in self.clusters[:50]:  # Limit to avoid token limits
            summary = self.cluster_summaries.get(cluster['cluster_id'], {})
            name = summary.get('name', f"Module {cluster['cluster_id']}")
            primary_topic = cluster.get('primary_topic', '')
            clusters_info.append(f"- {name} (topic: {primary_topic})")
        
        topics_list = "\n".join(clusters_info)
        
        prompt = f"""Analyze these {len(clusters_info)} documentation modules and organize them into logical parent categories with rich metadata.

**Modules:**
{topics_list}

**Task:** Create a logical grouping of these modules into 10-20 parent categories. For each category, provide:

1. **Name**: Clear, descriptive name (2-4 words)
2. **Overview**: 2-3 sentences explaining what this category covers, why it matters, and when you'd use it
3. **Target Audience**: Who should use this (e.g., "DevOps engineers", "SREs", "Developers", "Platform teams")
4. **Key Technologies**: List of main technologies/products covered (e.g., ["Azure", "AWS", "Kubernetes", "OpenTelemetry"])
5. **Prerequisites**: What should be completed first (can be empty array if none)
6. **Learning Outcomes**: 3-5 specific skills/knowledge users will gain (start with action verbs)

**Guidelines:**
- Group cloud providers together (Azure, AWS, GCP modules)
- Group related technologies (Kubernetes, OpenTelemetry, APIs)
- Group by functionality (Monitoring, Configuration, Security, Deployment)
- Group by product component (OneAgent, ActiveGate, DQL, etc)
- Look at the module NAMES not just topics - names are more specific
- Keep 2-10 modules per category

Return a JSON object with this structure:
{{
  "parent_categories": [
    {{
      "name": "Parent Category Name",
      "overview": "Detailed 2-3 sentence description covering what, why, and when",
      "target_audience": "Who this is for",
      "key_technologies": ["Tech1", "Tech2", "Tech3"],
      "prerequisites": ["Category Name"] or [],
      "learning_outcomes": [
        "Set up and configure X",
        "Monitor Y in production",
        "Integrate Z with existing systems"
      ],
      "module_names": ["Exact Module Name 1", "Exact Module Name 2", ...]
    }}
  ]
}}

Use the EXACT module names from the list above. Return valid JSON only."""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at organizing technical documentation taxonomies. Create clear, logical hierarchies."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            parent_categories = result.get('parent_categories', [])
            
            # Build name-to-cluster-id mapping
            name_to_id = {}
            for cluster in self.clusters:
                summary = self.cluster_summaries.get(cluster['cluster_id'], {})
                name = summary.get('name', f"Module {cluster['cluster_id']}")
                name_to_id[name.lower()] = cluster['cluster_id']
            
            # Convert to dict structure with cluster IDs and metadata
            hierarchy = {}
            for parent in parent_categories:
                parent_name = parent['name']
                module_names = parent.get('module_names', [])
                
                # Map module names to cluster IDs
                cluster_ids = []
                for module_name in module_names:
                    cluster_id = name_to_id.get(module_name.lower())
                    if cluster_id is not None:
                        cluster_ids.append(cluster_id)
                
                if cluster_ids:  # Only include parents with matched clusters
                    hierarchy[parent_name] = {
                        'name': parent_name,
                        'overview': parent.get('overview', parent.get('description', '')),
                        'target_audience': parent.get('target_audience', ''),
                        'key_technologies': parent.get('key_technologies', []),
                        'prerequisites': parent.get('prerequisites', []),
                        'learning_outcomes': parent.get('learning_outcomes', []),
                        'learning_outcomes': parent.get('learning_outcomes', []),
                        'cluster_ids': cluster_ids
                    }
            
            logger.info(f"[TaxonomyBuilder] Created {len(hierarchy)} parent categories with rich metadata")
            return hierarchy
            
        except Exception as e:
            logger.error(f"[TaxonomyBuilder] Error building topic hierarchy: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to flat structure
            return {'Documentation': {
                'name': 'Documentation',
                'description': 'All documentation modules',
                'cluster_ids': [c['cluster_id'] for c in self.clusters]
            }}
    
    def _sort_pages_by_learning_order(self, pages: List[Dict]) -> List[Dict]:
        """
        Sort pages within a module by optimal learning order.
        
        Uses:
        1. Prerequisite relationships (pages with fewer prerequisites first)
        2. Doc type progression (concepts → tutorials → how-tos → references)
        3. Difficulty (beginner → intermediate → advanced)
        4. Topics (group related pages together)
        
        Args:
            pages: List of page dictionaries with metadata
            
        Returns:
            Sorted list of pages in optimal learning order
        """
        if not pages:
            return []
        
        # Doc type ordering (lower = should come first)
        doc_type_order = {
            'concept': 1,
            'getting-started': 2,
            'tutorial': 3,
            'how-to': 4,
            'guide': 5,
            'reference': 6,
            'api-reference': 7,
            'unknown': 8,
        }
        
        # Difficulty ordering
        difficulty_order = {
            'beginner': 1,
            'intermediate': 2,
            'advanced': 3,
        }
        
        # Build prerequisite graph for pages in this module
        page_titles = {p['title']: i for i, p in enumerate(pages)}
        prereq_count = [0] * len(pages)
        
        # Count prerequisites for each page
        for i, page in enumerate(pages):
            prereqs = page.get('prerequisites', [])
            if prereqs:
                for prereq in prereqs:
                    # Check if this prereq is in the current module
                    prereq_name = prereq.get('name', '') if isinstance(prereq, dict) else str(prereq)
                    # Count as a prerequisite (increases complexity)
                    if prereq_name:
                        prereq_count[i] += 1
        
        # Sort pages using multiple criteria
        def sort_key(item):
            idx, page = item
            doc_type = page.get('ai_doc_type') or page.get('doc_type', 'unknown')
            difficulty = page.get('audience_level', 'intermediate')
            
            return (
                prereq_count[idx],  # Fewer prerequisites first
                doc_type_order.get(doc_type, 10),  # Doc type progression
                difficulty_order.get(difficulty, 2),  # Difficulty progression
                page.get('title', '')  # Alphabetical as tiebreaker
            )
        
        # Sort with index to maintain relationship with prereq_count
        indexed_pages = list(enumerate(pages))
        indexed_pages.sort(key=sort_key)
        
        # Return sorted pages without index
        return [page for idx, page in indexed_pages]
    
    def generate_taxonomy(self) -> Dict:
        """
        Generate hierarchical taxonomy from clusters.
        
        Combines:
        - Topic hierarchies (from ai_topics)
        - Clusters (from embedding similarity)
        - Prerequisites (from graph)
        
        Returns:
            Taxonomy dictionary with hierarchical topics
        """
        logger.info("[TaxonomyBuilder] Generating taxonomy")
        
        # Build topic hierarchy (now returns cluster_id assignments)
        topic_hierarchy = self.build_topic_hierarchy()
        
        # Build taxonomy structure with hierarchy
        root_topics = []
        
        # Build the taxonomy using the cluster ID assignments from GPT
        for parent_name, parent_info in topic_hierarchy.items():
            parent_clusters = []
            assigned_cluster_ids = parent_info.get('cluster_ids', [])
            
            # Get all clusters assigned to this parent
            for cluster in self.clusters:
                cluster_id = cluster['cluster_id']
                
                if cluster_id in assigned_cluster_ids:
                    # Get summary for this cluster
                    summary = self.cluster_summaries.get(cluster_id, {})
                    
                    # Build enhanced page data
                    pages_data = []
                    for p in cluster['pages']:
                        page_data = {
                            'page_id': p.id,
                            'title': p.title,
                            'url': p.url,
                            'doc_type': p.doc_type,
                            'ai_doc_type': p.ai_doc_type,
                            'audience_level': p.ai_audience_level,
                            'summary': p.ai_summary,
                            'learning_objectives': p.ai_learning_objectives or [],
                            'prerequisites': p.ai_prerequisite_chain or [],
                            'key_concepts': p.ai_key_concepts or [],
                            'topics': p.ai_topics or [],
                        }
                        pages_data.append(page_data)
                    
                    # Sort pages by prerequisites and difficulty
                    sorted_pages = self._sort_pages_by_learning_order(pages_data)
                    
                    cluster_entry = {
                        'id': f"{parent_name.lower().replace(' ', '_')}_{cluster_id}",
                        'name': summary.get('name', f"Module {cluster_id}"),
                        'description': summary.get('description', ''),
                        'difficulty': summary.get('difficulty', cluster.get('primary_audience', 'intermediate')),
                        'estimated_hours': summary.get('estimated_hours', len(cluster['pages']) * 0.5),
                        'prerequisites': summary.get('prerequisites', []),
                        'learning_outcomes': summary.get('learning_outcomes', []),
                        'cohesion': cluster['cohesion'],
                        'pages': sorted_pages
                    }
                    
                    parent_clusters.append(cluster_entry)
            
            # Calculate category statistics
            if parent_clusters:
                total_pages = sum(len(c['pages']) for c in parent_clusters)
                
                # Calculate difficulty breakdown
                difficulty_counts = {'beginner': 0, 'intermediate': 0, 'advanced': 0}
                for cluster in parent_clusters:
                    diff = cluster.get('difficulty', 'intermediate')
                    difficulty_counts[diff] = difficulty_counts.get(diff, 0) + 1
                
                # Calculate content type breakdown
                content_types = {}
                for cluster in parent_clusters:
                    for page in cluster['pages']:
                        doc_type = page.get('ai_doc_type') or page.get('doc_type', 'unknown')
                        content_types[doc_type] = content_types.get(doc_type, 0) + 1
                
                # Get top content types
                top_content_types = sorted(content_types.items(), key=lambda x: x[1], reverse=True)[:3]
                
                # Calculate estimated time (30 min per beginner module, 1 hour per intermediate, 2 hours per advanced)
                estimated_hours = (
                    difficulty_counts['beginner'] * 0.5 +
                    difficulty_counts['intermediate'] * 1.0 +
                    difficulty_counts['advanced'] * 2.0
                )
                
                # Calculate average cohesion
                avg_cohesion = sum(c['cohesion'] for c in parent_clusters) / len(parent_clusters)
                
                # Determine primary difficulty
                primary_difficulty = max(difficulty_counts.items(), key=lambda x: x[1])[0]
                
                root_topic = {
                    'id': parent_name.lower().replace(' ', '_'),
                    'name': parent_name,
                    'overview': parent_info.get('overview', ''),
                    'target_audience': parent_info.get('target_audience', ''),
                    'key_technologies': parent_info.get('key_technologies', []),
                    'prerequisites': parent_info.get('prerequisites', []),
                    'learning_outcomes': parent_info.get('learning_outcomes', []),
                    'clusters': parent_clusters,
                    'statistics': {
                        'total_pages': total_pages,
                        'total_modules': len(parent_clusters),
                        'difficulty_breakdown': difficulty_counts,
                        'primary_difficulty': primary_difficulty,
                        'content_types': dict(top_content_types),
                        'estimated_hours': round(estimated_hours, 1),
                        'avg_cohesion': round(avg_cohesion, 2)
                    }
                }
                root_topics.append(root_topic)
        
        # Build final taxonomy
        self.taxonomy = {
            'client_id': self.client_id,
            'client_name': self.client.name if self.client else f"Client {self.client_id}",
            'generated_at': datetime.utcnow().isoformat(),
            'statistics': {
                'total_pages': len(self.pages),
                'total_clusters': len(self.clusters),
                'total_topics': len(root_topics),
                'avg_cluster_size': np.mean([c['size'] for c in self.clusters]) if self.clusters else 0,
                'avg_cohesion': np.mean([c['cohesion'] for c in self.clusters]) if self.clusters else 0,
                'embedding_field': self.embedding_field,
            },
            'taxonomy': {
                'root_topics': root_topics
            },
            'metadata': {
                'clustering_method': 'kmeans',  # TODO: track actual method used
                'min_cluster_size': 3,
                'max_cluster_size': 15,
            }
        }
        
        logger.info(
            f"[TaxonomyBuilder] Taxonomy generated: {len(root_topics)} topics, "
            f"{len(self.clusters)} clusters, {len(self.pages)} pages"
        )
        
        return self.taxonomy
    
    def export_json(self, filepath: str):
        """Export taxonomy to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.taxonomy, f, indent=2)
        logger.info(f"[TaxonomyBuilder] Exported taxonomy to {filepath}")
    
    def export_markdown(self, filepath: str):
        """Export taxonomy to Markdown file."""
        lines = []
        
        # Header
        lines.append(f"# {self.taxonomy['client_name']} - Documentation Taxonomy")
        lines.append(f"\nGenerated: {self.taxonomy['generated_at']}")
        lines.append(f"\n## Statistics\n")
        
        stats = self.taxonomy['statistics']
        lines.append(f"- **Total Pages**: {stats['total_pages']}")
        lines.append(f"- **Topics**: {stats['total_topics']}")
        lines.append(f"- **Clusters/Modules**: {stats['total_clusters']}")
        lines.append(f"- **Avg Cluster Size**: {stats['avg_cluster_size']:.1f}")
        lines.append(f"- **Avg Cohesion**: {stats['avg_cohesion']:.2f}")
        lines.append(f"\n---\n")
        
        # Topics and clusters
        for topic in self.taxonomy['taxonomy']['root_topics']:
            lines.append(f"\n## {topic['name']}")
            lines.append(f"\n{topic.get('overview', topic.get('description', ''))}")
            
            # Add statistics if available
            if 'statistics' in topic:
                stats = topic['statistics']
                lines.append(f"\n**Stats**: {stats['total_modules']} modules • {stats['total_pages']} pages • {stats['estimated_hours']} hours • {stats['primary_difficulty']}")
            else:
                lines.append(f"\n**Pages**: {topic.get('total_pages', 0)}")
            
            for cluster in topic['clusters']:
                lines.append(f"\n### {cluster['name']}")
                lines.append(f"\n{cluster['description']}")
                lines.append(f"\n**Metadata:**")
                lines.append(f"- Difficulty: {cluster['difficulty']}")
                lines.append(f"- Estimated Time: {cluster['estimated_hours']:.1f} hours")
                lines.append(f"- Cohesion: {cluster['cohesion']:.2f}")
                lines.append(f"- Pages: {len(cluster['pages'])}")
                
                if cluster.get('prerequisites'):
                    lines.append(f"\n**Prerequisites:**")
                    for prereq in cluster['prerequisites']:
                        lines.append(f"- {prereq}")
                
                if cluster.get('learning_outcomes'):
                    lines.append(f"\n**Learning Outcomes:**")
                    for outcome in cluster['learning_outcomes']:
                        lines.append(f"- {outcome}")
                
                lines.append(f"\n**Pages:**")
                for page in cluster['pages']:
                    lines.append(f"- [{page['title']}]({page['url']}) ({page['ai_doc_type']})")
                
                lines.append("")
        
        # Write file
        with open(filepath, 'w') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"[TaxonomyBuilder] Exported taxonomy to {filepath}")
    
    def visualize_graph(self, filepath: str, format: str = 'png'):
        """
        Visualize prerequisite graph.
        
        Args:
            filepath: Output file path
            format: 'png', 'svg', 'dot', or 'mermaid'
        """
        if self.prerequisite_graph is None:
            logger.warning("[TaxonomyBuilder] No graph to visualize")
            return
        
        G = self.prerequisite_graph
        
        if format == 'mermaid':
            # Export as Mermaid diagram
            self._export_mermaid(filepath)
        
        elif format == 'dot':
            # Export as GraphViz DOT
            self._export_dot(filepath)
        
        elif format in ['png', 'svg', 'pdf']:
            # Render using matplotlib/graphviz
            try:
                import pygraphviz as pgv
                A = nx.nx_agraph.to_agraph(G)
                A.layout(prog='dot')
                A.draw(filepath, format=format)
                logger.info(f"[TaxonomyBuilder] Visualized graph to {filepath}")
            except ImportError:
                logger.warning("[TaxonomyBuilder] pygraphviz not available, falling back to DOT export")
                self._export_dot(filepath.replace(f'.{format}', '.dot'))
        
        else:
            raise ValueError(f"Unknown format: {format}")
    
    def _export_mermaid(self, filepath: str):
        """Export graph as Mermaid diagram."""
        lines = ["graph TD"]
        
        G = self.prerequisite_graph
        
        # Add nodes
        for node_id, attrs in G.nodes(data=True):
            node_type = attrs.get('type', 'unknown')
            if node_type == 'page':
                title = attrs.get('title', '')[:40]
                lines.append(f'    {node_id}["{title}"]')
            elif node_type == 'concept':
                name = attrs.get('name', '')[:30]
                lines.append(f'    {node_id}{{"{name}"}}')
        
        # Add edges
        for u, v, attrs in G.edges(data=True):
            importance = attrs.get('importance', '')
            if importance == 'essential':
                lines.append(f'    {u} ==> {v}')
            elif importance == 'recommended':
                lines.append(f'    {u} --> {v}')
            else:
                lines.append(f'    {u} -.-> {v}')
        
        with open(filepath, 'w') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"[TaxonomyBuilder] Exported Mermaid diagram to {filepath}")
    
    def _export_dot(self, filepath: str):
        """Export graph as GraphViz DOT format."""
        from networkx.drawing.nx_pydot import write_dot
        
        # Simplify node labels for readability
        # Remove 'name' attribute to avoid conflicts with pydot
        G_copy = self.prerequisite_graph.copy()
        for node_id, attrs in G_copy.nodes(data=True):
            # Clear all attributes and only set label
            if attrs.get('type') == 'page':
                label = attrs.get('title', '')[:40]
            elif attrs.get('type') == 'concept':
                label = attrs.get('name', '')[:30]
            else:
                label = str(node_id)[:30]
            
            # Clear attributes and set only label
            for key in list(G_copy.nodes[node_id].keys()):
                del G_copy.nodes[node_id][key]
            G_copy.nodes[node_id]['label'] = label
        
        write_dot(G_copy, filepath)
        logger.info(f"[TaxonomyBuilder] Exported DOT file to {filepath}")
    
    def generate_statistics_report(self) -> str:
        """Generate a text report with statistics and insights."""
        lines = []
        
        lines.append("="*60)
        lines.append(f"TAXONOMY BUILDER REPORT - {self.taxonomy['client_name']}")
        lines.append("="*60)
        lines.append(f"\nGenerated: {self.taxonomy['generated_at']}")
        lines.append(f"\n## Overall Statistics\n")
        
        stats = self.taxonomy['statistics']
        lines.append(f"Total Pages Analyzed: {stats['total_pages']}")
        lines.append(f"Total Topics: {stats['total_topics']}")
        lines.append(f"Total Clusters: {stats['total_clusters']}")
        lines.append(f"Avg Cluster Size: {stats['avg_cluster_size']:.1f} pages")
        lines.append(f"Avg Cohesion: {stats['avg_cohesion']:.2f} (0-1 scale)")
        
        # Graph statistics
        if self.prerequisite_graph:
            G = self.prerequisite_graph
            lines.append(f"\n## Prerequisite Graph\n")
            lines.append(f"Total Nodes: {G.number_of_nodes()}")
            lines.append(f"Total Edges: {G.number_of_edges()}")
            
            page_nodes = [n for n, d in G.nodes(data=True) if d.get('type') == 'page']
            concept_nodes = [n for n, d in G.nodes(data=True) if d.get('type') == 'concept']
            
            lines.append(f"Page Nodes: {len(page_nodes)}")
            lines.append(f"Concept Nodes: {len(concept_nodes)}")
            
            # Find foundational pages (high PageRank)
            try:
                pagerank = nx.pagerank(G)
                top_pages = sorted(
                    [(n, pr) for n, pr in pagerank.items() if n.startswith('page_')],
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
                
                lines.append(f"\n## Foundational Pages (by PageRank)\n")
                for node_id, score in top_pages:
                    node_data = G.nodes[node_id]
                    lines.append(f"- {node_data.get('title', 'Unknown')} (score: {score:.3f})")
            except:
                pass
        
        # Cluster details
        lines.append(f"\n## Clusters\n")
        for cluster in self.clusters:
            summary = self.cluster_summaries.get(cluster['cluster_id'], {})
            lines.append(f"\n### Cluster {cluster['cluster_id']}: {summary.get('name', 'Unnamed')}")
            lines.append(f"- Size: {cluster['size']} pages")
            lines.append(f"- Cohesion: {cluster['cohesion']:.2f}")
            lines.append(f"- Primary Topic: {cluster['primary_topic']}")
            lines.append(f"- Difficulty: {summary.get('difficulty', cluster.get('primary_audience', 'intermediate'))}")
        
        return '\n'.join(lines)
    
    def export_all(self, output_dir: str):
        """
        Export all outputs (JSON, Markdown, graph, report).
        
        Args:
            output_dir: Directory to save outputs
        """
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        client_slug = self.client.slug if self.client else f"client_{self.client_id}"
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        
        # Export JSON
        json_path = os.path.join(output_dir, f"{client_slug}_taxonomy_{timestamp}.json")
        self.export_json(json_path)
        
        # Export Markdown
        md_path = os.path.join(output_dir, f"{client_slug}_taxonomy_{timestamp}.md")
        self.export_markdown(md_path)
        
        # Export graph (Mermaid)
        mermaid_path = os.path.join(output_dir, f"{client_slug}_prerequisite_graph.mmd")
        self.visualize_graph(mermaid_path, format='mermaid')
        
        # Export graph (DOT)
        dot_path = os.path.join(output_dir, f"{client_slug}_prerequisite_graph.dot")
        self.visualize_graph(dot_path, format='dot')
        
        # Export statistics report
        report = self.generate_statistics_report()
        report_path = os.path.join(output_dir, f"{client_slug}_taxonomy_report.txt")
        with open(report_path, 'w') as f:
            f.write(report)
        
        logger.info(f"[TaxonomyBuilder] Exported all files to {output_dir}")
        
        return {
            'json': json_path,
            'markdown': md_path,
            'mermaid': mermaid_path,
            'dot': dot_path,
            'report': report_path,
        }

