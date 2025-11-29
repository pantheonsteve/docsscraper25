"""
AI-powered content analysis for documentation pages.

Hybrid approach using spaCy (local NLP) + GPT-4o-mini (structured extraction)
to extract topics, learning objectives, and prerequisite chains optimized for
lesson grouping and taxonomy building.

Enhanced with:
- Multi-level Bloom's taxonomy extraction
- Page summaries for efficient clustering
- Audience level classification
- Key concepts for dependency graphs
- Quality indicators for audit reports
"""

import logging
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json
import re

logger = logging.getLogger('crawler')


class ContentAnalyzer:
    """
    Analyzes documentation content using spaCy + GPT-4o-mini hybrid approach.
    
    Cost: ~$0.0001-0.0002 per page with GPT-4o-mini
    """
    
    def __init__(self, openai_api_key: str):
        """
        Initialize the content analyzer.
        
        Args:
            openai_api_key: OpenAI API key for GPT-4o-mini
        """
        self.openai_api_key = openai_api_key
        self._spacy_nlp = None
        self._openai_client = None
        
    @property
    def spacy_nlp(self):
        """Lazy-load spaCy model."""
        if self._spacy_nlp is None:
            try:
                import spacy
                self._spacy_nlp = spacy.load("en_core_web_sm")
                logger.info("Loaded spaCy model: en_core_web_sm")
            except OSError:
                logger.warning("spaCy model not found, attempting to download...")
                import subprocess
                subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"], check=True)
                import spacy
                self._spacy_nlp = spacy.load("en_core_web_sm")
                logger.info("Downloaded and loaded spaCy model: en_core_web_sm")
        return self._spacy_nlp
    
    @property
    def openai_client(self):
        """Lazy-load OpenAI client."""
        if self._openai_client is None:
            from openai import OpenAI
            self._openai_client = OpenAI(api_key=self.openai_api_key)
        return self._openai_client
    
    def analyze_page(
        self,
        page_id: int,
        url: str,
        title: str,
        main_content: str,
        sections: List[Dict],
        doc_type: str,
        existing_prerequisites: List = None,
        existing_learning_objectives: List = None,
        has_code_examples: bool = False,
        has_images: bool = False,
        has_videos: bool = False,
        word_count: int = 0,
    ) -> Dict:
        """
        Analyze a documentation page and extract rich metadata.
        
        Args:
            page_id: Page ID for logging
            url: Page URL
            title: Page title
            main_content: Main text content
            sections: Page sections with headings
            doc_type: Document type (tutorial, guide, etc.)
            existing_prerequisites: Existing regex-detected prerequisites
            existing_learning_objectives: Existing regex-detected learning objectives
            has_code_examples: Whether page has code examples
            has_images: Whether page has images
            has_videos: Whether page has videos
            word_count: Word count of the page
            
        Returns:
            Dictionary with ai_topics, ai_learning_objectives, ai_prerequisite_chain, 
            ai_summary, ai_audience_level, ai_key_concepts, ai_doc_type, 
            ai_quality_indicators, metadata
        """
        start_time = time.time()
        
        logger.info(f"[ContentAnalyzer] Page {page_id} ({url}): Starting analysis")
        
        # Skip certain doc types to save costs (but NOT 'unknown' - we want to reclassify those!)
        skip_types = ['navigation', 'landing', 'changelog']
        if doc_type in skip_types:
            logger.info(f"[ContentAnalyzer] Page {page_id}: Skipping doc_type='{doc_type}'")
            return self._empty_result(f"Skipped doc_type: {doc_type}")
        
        # Truncate content if too long (cost optimization)
        content_for_analysis = self._prepare_content(title, main_content, sections, max_chars=4000)
        
        # Step 1: spaCy preprocessing (fast, local)
        topic_candidates = self._extract_topic_candidates(content_for_analysis)
        prerequisite_mentions = self._extract_prerequisite_mentions(content_for_analysis)
        
        logger.info(
            f"[ContentAnalyzer] Page {page_id}: spaCy found {len(topic_candidates)} topic candidates, "
            f"{len(prerequisite_mentions)} prerequisite mentions"
        )
        
        # Step 2: GPT-4o-mini enrichment (single API call)
        try:
            llm_result = self._enrich_with_llm(
                url=url,
                title=title,
                content=content_for_analysis,
                doc_type=doc_type,
                topic_candidates=topic_candidates,
                prerequisite_mentions=prerequisite_mentions,
                existing_prerequisites=existing_prerequisites or [],
                existing_learning_objectives=existing_learning_objectives or [],
                has_code_examples=has_code_examples,
                has_images=has_images,
                has_videos=has_videos,
                word_count=word_count,
            )
        except Exception as e:
            logger.error(f"[ContentAnalyzer] Page {page_id}: LLM call failed: {e}")
            return self._empty_result(f"LLM error: {str(e)}")
        
        processing_time = time.time() - start_time
        
        # Build metadata
        metadata = {
            "model": "gpt-4o-mini",
            "timestamp": datetime.utcnow().isoformat(),
            "processing_time_seconds": round(processing_time, 2),
            "content_length": len(content_for_analysis),
            "spacy_candidates": len(topic_candidates),
            "prerequisite_mentions": len(prerequisite_mentions),
        }
        
        result = {
            # Core analysis fields
            "ai_topics": llm_result.get("topics", []),
            "ai_learning_objectives": llm_result.get("learning_objectives", []),
            "ai_prerequisite_chain": llm_result.get("prerequisite_chain", []),
            
            # New enhanced fields
            "ai_summary": llm_result.get("summary", ""),
            "ai_audience_level": llm_result.get("audience_level", "intermediate"),
            "ai_key_concepts": llm_result.get("key_concepts", []),
            "ai_doc_type": llm_result.get("doc_type", doc_type),
            "ai_quality_indicators": llm_result.get("quality_indicators", {}),
            "ai_related_topics": llm_result.get("related_topics", []),
            
            # Metadata
            "ai_analysis_metadata": metadata,
        }
        
        logger.info(
            f"[ContentAnalyzer] Page {page_id}: ✓ Extracted {len(result['ai_topics'])} topics, "
            f"{len(result['ai_learning_objectives'])} LOs, "
            f"{len(result['ai_prerequisite_chain'])} prerequisites, "
            f"{len(result['ai_key_concepts'])} key concepts in {processing_time:.2f}s"
        )
        
        return result
    
    def _prepare_content(
        self, 
        title: str, 
        main_content: str, 
        sections: List[Dict],
        max_chars: int = 4000
    ) -> str:
        """
        Prepare content for analysis, truncating if necessary.
        
        Prioritizes: title, section headings, first paragraphs of each section.
        """
        parts = [f"Title: {title}"]
        
        if sections:
            for section in sections[:10]:  # Max 10 sections
                heading = section.get('heading', '')
                content = section.get('content', '')
                if heading:
                    parts.append(f"\n## {heading}")
                if content:
                    # Take first 300 chars of each section
                    parts.append(content[:300])
        else:
            # No sections, use main content
            parts.append(main_content)
        
        full_text = "\n".join(parts)
        
        # Truncate if too long
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars] + "..."
        
        return full_text
    
    def _extract_topic_candidates(self, text: str) -> List[str]:
        """
        Extract topic candidates using spaCy NER and noun chunks.
        
        Returns list of candidate topic strings.
        """
        doc = self.spacy_nlp(text)
        candidates = set()
        
        # Named entities (ORG, PRODUCT, GPE, etc.)
        for ent in doc.ents:
            if ent.label_ in ['ORG', 'PRODUCT', 'GPE', 'FAC', 'NORP', 'EVENT']:
                candidates.add(ent.text)
        
        # Noun chunks (technical terms, concepts)
        for chunk in doc.noun_chunks:
            # Filter: length 2-4 words, contains at least one proper noun or technical term
            words = chunk.text.split()
            if 2 <= len(words) <= 4:
                # Check if it looks like a technical term (capitalized or compound)
                if any(w[0].isupper() for w in words if w) or '-' in chunk.text:
                    candidates.add(chunk.text)
        
        # Common technical patterns
        tech_patterns = [
            r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b',  # CamelCase
            r'\b[a-z]+(?:-[a-z]+)+\b',  # kebab-case
            r'\b[A-Z]{2,}\b',  # Acronyms
        ]
        for pattern in tech_patterns:
            for match in re.finditer(pattern, text):
                candidates.add(match.group(0))
        
        return list(candidates)[:50]  # Limit to top 50
    
    def _extract_prerequisite_mentions(self, text: str) -> List[str]:
        """
        Extract prerequisite mentions using spaCy dependency parsing.
        
        Returns list of prerequisite strings.
        """
        doc = self.spacy_nlp(text)
        mentions = set()
        
        # Pattern 1: "requires X", "needs X", "must have X"
        prerequisite_verbs = ['require', 'need', 'must', 'should', 'expect']
        for token in doc:
            if token.lemma_ in prerequisite_verbs:
                # Get objects/complements
                for child in token.children:
                    if child.dep_ in ['dobj', 'attr', 'pobj']:
                        # Get the full noun phrase
                        noun_phrase = ' '.join([t.text for t in child.subtree])
                        mentions.add(noun_phrase)
        
        # Pattern 2: Explicit prerequisite sections
        prereq_keywords = ['prerequisite', 'requirement', 'before you begin', 'you need', 'you should']
        for keyword in prereq_keywords:
            if keyword in text.lower():
                # Extract sentence containing keyword
                for sent in doc.sents:
                    if keyword in sent.text.lower():
                        mentions.add(sent.text.strip())
        
        return list(mentions)[:20]  # Limit to top 20
    
    def _enrich_with_llm(
        self,
        url: str,
        title: str,
        content: str,
        doc_type: str,
        topic_candidates: List[str],
        prerequisite_mentions: List[str],
        existing_prerequisites: List,
        existing_learning_objectives: List,
        has_code_examples: bool = False,
        has_images: bool = False,
        has_videos: bool = False,
        word_count: int = 0,
    ) -> Dict:
        """
        Call GPT-4o-mini to enrich and structure the extracted data.
        
        Single API call optimized for cost and lesson grouping use case.
        """
        prompt = self._build_prompt(
            url=url,
            title=title,
            content=content,
            doc_type=doc_type,
            topic_candidates=topic_candidates,
            prerequisite_mentions=prerequisite_mentions,
            existing_prerequisites=existing_prerequisites,
            existing_learning_objectives=existing_learning_objectives,
            has_code_examples=has_code_examples,
            has_images=has_images,
            has_videos=has_videos,
            word_count=word_count,
        )
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert technical documentation analyst and instructional designer. 
Your task is to extract structured metadata optimized for:
1. Grouping pages into coherent lessons and learning paths
2. Building documentation taxonomies
3. Creating dependency graphs for learning journeys
4. Identifying content gaps and quality issues

Apply educational frameworks like Bloom's Taxonomy rigorously. Be specific and actionable."""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,  # Lower temperature for more consistent output
            response_format={"type": "json_object"},
        )
        
        result_text = response.choices[0].message.content
        return json.loads(result_text)
    
    def _build_prompt(
        self,
        url: str,
        title: str,
        content: str,
        doc_type: str,
        topic_candidates: List[str],
        prerequisite_mentions: List[str],
        existing_prerequisites: List,
        existing_learning_objectives: List,
        has_code_examples: bool = False,
        has_images: bool = False,
        has_videos: bool = False,
        word_count: int = 0,
    ) -> str:
        """Build the LLM prompt for content analysis."""
        
        return f"""Analyze this technical documentation page and extract structured metadata for learning path construction and taxonomy building.

**Page Information:**
- URL: {url}
- Title: {title}
- Current Doc Type: {doc_type}
- Word Count: {word_count}
- Has Code Examples: {has_code_examples}
- Has Images: {has_images}
- Has Videos: {has_videos}

**Content:**
{content}

**spaCy Detected (for reference):**
- Topic candidates: {', '.join(topic_candidates[:20]) if topic_candidates else 'none'}
- Prerequisite mentions: {', '.join(prerequisite_mentions[:10]) if prerequisite_mentions else 'none'}

**Existing Data (from regex):**
- Prerequisites: {existing_prerequisites[:5] if existing_prerequisites else 'none'}
- Learning objectives: {existing_learning_objectives[:3] if existing_learning_objectives else 'none'}

**Task:**
Extract and structure the following in JSON format. This data will be used to:
1. Group related pages into lessons
2. Build learning paths with proper sequencing
3. Create a hierarchical documentation taxonomy
4. Generate audit reports identifying content gaps

Return JSON with this exact structure:
{{
  "summary": "1-2 sentence summary of what this page covers and its purpose",
  
  "doc_type": "tutorial|how-to|reference|concept|troubleshooting|quickstart|api-reference|guide|example|changelog|faq",
  
  "audience_level": "beginner|intermediate|advanced",
  
  "topics": [
    {{
      "name": "string (specific topic name, 1-3 words)",
      "relevance": 0.0-1.0 (how central is this topic to the page),
      "category": "string (broad category: monitoring, authentication, api, data, security, integration, configuration, etc.)",
      "parent_topic": "string or null (broader parent topic if applicable)",
      "child_topics": ["list of narrower sub-topics covered"],
      "related_topics": ["list of related topics at same level"]
    }}
  ],
  
  "learning_objectives": [
    {{
      "objective": "string (action-oriented: what the reader will be able to DO)",
      "bloom_level": "remember|understand|apply|analyze|evaluate|create",
      "bloom_verb": "string (the specific action verb: configure, explain, implement, compare, design, etc.)",
      "difficulty": "beginner|intermediate|advanced",
      "estimated_time_minutes": number (realistic time to achieve this objective),
      "measurable": boolean (can this be tested/verified?)
    }}
  ],
  
  "prerequisite_chain": [
    {{
      "concept": "string (prerequisite concept or knowledge required)",
      "type": "knowledge|skill|tool|access|environment",
      "importance": "essential|recommended|optional",
      "description": "string (brief description of what's needed)"
    }}
  ],
  
  "key_concepts": [
    {{
      "term": "string (technical term or concept introduced/explained)",
      "definition": "string (brief definition if provided, or null)",
      "is_new": boolean (is this concept introduced here vs. assumed known?)
    }}
  ],
  
  "related_topics": ["list of topic strings this page connects to"],
  
  "quality_indicators": {{
    "completeness_score": 0.0-1.0 (how complete is this documentation?),
    "completeness_notes": "string (what's missing or could be improved)",
    "needs_code_examples": boolean (should this page have code examples but doesn't?),
    "needs_visuals": boolean (would diagrams/screenshots help?),
    "needs_troubleshooting": boolean (should include troubleshooting section?),
    "outdated_signals": boolean (any signs content might be outdated?),
    "suggested_improvements": ["list of specific improvement suggestions"]
  }}
}}

**Guidelines:**

1. **Summary**: Write a concise 1-2 sentence summary that captures both WHAT the page covers and WHY a reader would need it. This will be used for clustering.

2. **Doc Type**: Re-classify based on actual content using Diátaxis framework:
   - tutorial: Learning-oriented, teaches through doing
   - how-to: Task-oriented, solves specific problems
   - reference: Information-oriented, describes the machinery
   - concept: Understanding-oriented, explains background
   - troubleshooting: Problem-solving focused
   - quickstart: Fast path to first success
   - api-reference: API endpoint documentation
   - example: Code examples and demos
   
3. **Topics**: Focus on hierarchical relationships. Extract 3-7 main topics with clear parent-child relationships. Topics should be specific enough to cluster similar pages.

4. **Learning Objectives**: 
   - Extract objectives across MULTIPLE Bloom levels when content supports it:
     * Remember: List, define, recall, identify
     * Understand: Explain, describe, summarize, interpret
     * Apply: Use, implement, configure, execute
     * Analyze: Compare, contrast, differentiate, examine
     * Evaluate: Assess, determine, recommend, judge
     * Create: Design, build, develop, construct
   - Match bloom_level to what the content actually enables
   - Tutorials should have Apply-level objectives
   - Concept pages should have Understand-level objectives
   - Be specific and measurable when possible

5. **Prerequisites**: Build a meaningful dependency chain:
   - "essential" = Cannot proceed without this
   - "recommended" = Will struggle without this
   - "optional" = Helpful but not required
   - Include both knowledge prerequisites and tool/access requirements

6. **Key Concepts**: Identify technical terms that are:
   - Introduced and defined in this page (is_new: true)
   - Used but assumed known (is_new: false)
   - This helps build a concept dependency graph

7. **Quality Indicators**: Be constructively critical:
   - Consider if a {doc_type} page SHOULD have certain elements
   - Tutorials should have code examples and step-by-step instructions
   - Reference docs should be comprehensive
   - How-to guides should be task-focused with clear outcomes

8. **General**:
   - Be specific and actionable - avoid vague terms
   - If data is sparse, return minimal but accurate info rather than guessing
   - Focus on information useful for grouping related pages and building learning paths

Return valid JSON only, no markdown code blocks or explanation."""
    
    def _empty_result(self, reason: str) -> Dict:
        """Return an empty result with metadata."""
        return {
            "ai_topics": [],
            "ai_learning_objectives": [],
            "ai_prerequisite_chain": [],
            "ai_summary": "",
            "ai_audience_level": "intermediate",
            "ai_key_concepts": [],
            "ai_doc_type": "unknown",
            "ai_quality_indicators": {},
            "ai_related_topics": [],
            "ai_analysis_metadata": {
                "model": "none",
                "timestamp": datetime.utcnow().isoformat(),
                "processing_time_seconds": 0,
                "skip_reason": reason,
            }
        }
    
    def merge_with_existing(
        self,
        ai_result: Dict,
        existing_prerequisites: List,
        existing_learning_objectives: List,
    ) -> Tuple[List, List]:
        """
        Merge AI-extracted data with existing regex-detected data.
        
        Returns:
            (enhanced_prerequisites, enhanced_learning_objectives)
        """
        # Merge prerequisites
        enhanced_prereqs = list(existing_prerequisites) if existing_prerequisites else []
        for ai_prereq in ai_result.get('ai_prerequisite_chain', []):
            # Add AI-detected prerequisites that aren't already in the list
            concept = ai_prereq.get('concept', '')
            if concept and concept not in [str(p) for p in enhanced_prereqs]:
                enhanced_prereqs.append(concept)
        
        # Merge learning objectives (enhance with Bloom levels)
        enhanced_los = []
        for ai_lo in ai_result.get('ai_learning_objectives', []):
            enhanced_los.append(ai_lo.get('objective', ''))
        
        # Add existing LOs that aren't covered by AI
        for existing_lo in (existing_learning_objectives or []):
            if existing_lo not in enhanced_los:
                enhanced_los.append(existing_lo)
        
        return enhanced_prereqs, enhanced_los
    
    def get_bloom_distribution(self, learning_objectives: List[Dict]) -> Dict[str, int]:
        """
        Get distribution of Bloom's taxonomy levels across learning objectives.
        
        Useful for validating that content covers multiple cognitive levels.
        """
        distribution = {
            "remember": 0,
            "understand": 0,
            "apply": 0,
            "analyze": 0,
            "evaluate": 0,
            "create": 0,
        }
        
        for lo in learning_objectives:
            level = lo.get("bloom_level", "").lower()
            if level in distribution:
                distribution[level] += 1
        
        return distribution
    
    def calculate_content_coverage(self, result: Dict) -> Dict[str, any]:
        """
        Calculate content coverage metrics from analysis results.
        
        Returns metrics useful for taxonomy building and gap analysis.
        """
        topics = result.get("ai_topics", [])
        los = result.get("ai_learning_objectives", [])
        prereqs = result.get("ai_prerequisite_chain", [])
        key_concepts = result.get("ai_key_concepts", [])
        quality = result.get("ai_quality_indicators", {})
        
        # Count new vs assumed concepts
        new_concepts = len([c for c in key_concepts if c.get("is_new", False)])
        assumed_concepts = len([c for c in key_concepts if not c.get("is_new", True)])
        
        # Count essential prerequisites
        essential_prereqs = len([p for p in prereqs if p.get("importance") == "essential"])
        
        # Get topic categories
        categories = list(set(t.get("category", "unknown") for t in topics))
        
        return {
            "topic_count": len(topics),
            "learning_objective_count": len(los),
            "prerequisite_count": len(prereqs),
            "essential_prerequisite_count": essential_prereqs,
            "key_concept_count": len(key_concepts),
            "new_concept_count": new_concepts,
            "assumed_concept_count": assumed_concepts,
            "categories": categories,
            "bloom_distribution": self.get_bloom_distribution(los),
            "completeness_score": quality.get("completeness_score", 0),
            "needs_improvements": quality.get("suggested_improvements", []),
        }
    
    def generate_learning_objective_embeddings(
        self, 
        learning_objectives: List[Dict],
        page_context: str = ""
    ) -> List[Dict]:
        """
        Generate embeddings for learning objectives to enable clustering by learning outcomes.
        
        Args:
            learning_objectives: List of learning objective dicts from AI analysis
            page_context: Optional page title/topic for context (improves embedding quality)
            
        Returns:
            List of dicts with {objective, bloom_level, difficulty, embedding_model, embedding}
        """
        if not learning_objectives:
            return []
        
        from openai import OpenAI
        client = OpenAI(api_key=self.openai_api_key)
        EMBEDDING_MODEL = "text-embedding-3-small"
        
        # Prepare texts for embedding
        # Format: "Context: {page_context} | Objective: {objective} | Level: {bloom_level}"
        # This format helps the embedding capture both the what and the how
        inputs = []
        for lo in learning_objectives:
            objective = lo.get("objective", "")
            bloom_level = lo.get("bloom_level", "")
            bloom_verb = lo.get("bloom_verb", "")
            difficulty = lo.get("difficulty", "")
            
            # Create rich text for embedding that captures the full learning context
            parts = []
            if page_context:
                parts.append(f"Context: {page_context}")
            parts.append(f"Objective: {objective}")
            if bloom_verb:
                parts.append(f"Action: {bloom_verb}")
            if bloom_level:
                parts.append(f"Level: {bloom_level}")
            if difficulty:
                parts.append(f"Difficulty: {difficulty}")
            
            text = " | ".join(parts)
            inputs.append(text)
        
        logger.info(f"[ContentAnalyzer] Generating {len(inputs)} learning objective embeddings")
        
        try:
            # Generate embeddings
            response = client.embeddings.create(model=EMBEDDING_MODEL, input=inputs)
            vectors = [d.embedding for d in response.data]
            
            # Build result with metadata
            result = []
            for lo, vec in zip(learning_objectives, vectors):
                result.append({
                    "objective": lo.get("objective", ""),
                    "bloom_level": lo.get("bloom_level", ""),
                    "bloom_verb": lo.get("bloom_verb", ""),
                    "difficulty": lo.get("difficulty", ""),
                    "estimated_time_minutes": lo.get("estimated_time_minutes"),
                    "measurable": lo.get("measurable"),
                    "embedding_model": EMBEDDING_MODEL,
                    "embedding": vec,
                })
            
            logger.info(f"[ContentAnalyzer] ✓ Generated {len(result)} LO embeddings")
            return result
            
        except Exception as e:
            logger.error(f"[ContentAnalyzer] Error generating LO embeddings: {e}")
            return []
