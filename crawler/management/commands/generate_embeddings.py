"""
Generate OpenAI embeddings (text-embedding-3-small) for crawled pages.

Embeds:
- One vector for the full page (`page.page_embedding`)
- One vector per semantic section (`page.section_embeddings`), based on `page.sections`

Usage examples:

    # Generate embeddings for a single page
    python manage.py generate_embeddings --page-id 123

    # Generate embeddings for all pages in a job
    python manage.py generate_embeddings --job-id 56

    # Generate embeddings for all pages of a client
    python manage.py generate_embeddings --client-id 3

    # Force re-generation even if embeddings already exist
    python manage.py generate_embeddings --job-id 56 --force
"""

from django.core.management.base import BaseCommand, CommandError
from decouple import config

from crawler.models import CrawledPage

try:
    # New-style OpenAI client
    from openai import OpenAI
except ImportError:
    OpenAI = None


EMBEDDING_MODEL = "text-embedding-3-small"


class Command(BaseCommand):
    help = "Generate OpenAI embeddings for crawled pages (full-page and per-section)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--page-id",
            type=int,
            help="Generate embeddings for a single page ID",
        )
        parser.add_argument(
            "--job-id",
            type=int,
            help="Generate embeddings for all pages in a given job",
        )
        parser.add_argument(
            "--client-id",
            type=int,
            help="Generate embeddings for all pages for a given client",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Maximum number of pages to process",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recompute embeddings even if they already exist",
        )

    def handle(self, *args, **options):
        if OpenAI is None:
            raise CommandError(
                "The 'openai' package is not installed. "
                "Add `openai` to requirements.txt and `pip install -r requirements.txt`."
            )

        api_key = config("OPENAI_API_KEY", default=None)
        if not api_key:
            raise CommandError(
                "OPENAI_API_KEY is not set. Please add it to your .env file."
            )

        client = OpenAI(api_key=api_key)

        page_id = options.get("page_id")
        job_id = options.get("job_id")
        client_id = options.get("client_id")
        limit = options.get("limit")
        force = options.get("force")

        queryset = CrawledPage.objects.all()
        if page_id:
            queryset = queryset.filter(id=page_id)
        if job_id:
            queryset = queryset.filter(job_id=job_id)
        if client_id:
            queryset = queryset.filter(client_id=client_id)

        # Only embed pages that actually have content
        queryset = queryset.exclude(main_content__isnull=True).exclude(main_content="")

        if not force:
            # Skip pages that already have embeddings
            from django.db.models import Q
            queryset = queryset.filter(
                Q(page_embedding__isnull=True) | Q(page_embedding=[])
            )

        if limit:
            queryset = queryset.order_by("id")[: limit]

        total = queryset.count()
        if total == 0:
            self.stdout.write("No pages to embed (check filters or use --force).")
            return

        self.stdout.write(f"Generating embeddings for {total} page(s)...")

        for page in queryset.iterator():
            try:
                self._embed_page(client, page)
            except Exception as exc:
                self.stderr.write(
                    f"[page {page.id}] Error generating embeddings: {exc}"
                )

        self.stdout.write(self.style.SUCCESS("Embedding generation completed."))

    # ------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------

    def _embed_page(self, client, page: CrawledPage):
        # Prepare texts: full page + each section
        inputs = []
        index_map = []

        full_text = (page.main_content or "").strip()
        if full_text:
            inputs.append(full_text)
            index_map.append(("page", None))

        sections = page.sections or []
        for idx, section in enumerate(sections):
            content = (section.get("content") or "").strip()
            if not content:
                continue
            heading = (section.get("heading") or "").strip()
            # Combine heading and content for richer section-level embeddings
            text = f"{heading}\n\n{content}" if heading else content
            inputs.append(text)
            index_map.append(("section", idx))

        if not inputs:
            # Nothing to embed
            return

        self.stdout.write(
            f"[page {page.id}] Requesting {len(inputs)} embeddings from {EMBEDDING_MODEL}..."
        )

        response = client.embeddings.create(model=EMBEDDING_MODEL, input=inputs)
        vectors = [d.embedding for d in response.data]

        page_embedding = []
        section_embeddings = []

        for (kind, idx), vec in zip(index_map, vectors):
            if kind == "page":
                page_embedding = vec
            elif kind == "section":
                section = (page.sections or [])[idx]
                section_entry = {
                    "index": idx,
                    "heading": section.get("heading"),
                    "level": section.get("level"),
                    "word_count": section.get("word_count"),
                    "has_code": section.get("has_code"),
                    "has_list": section.get("has_list"),
                    "content": section.get("content"),
                    "embedding_model": EMBEDDING_MODEL,
                    "embedding": vec,
                }
                section_embeddings.append(section_entry)

        # Generate learning objective embeddings if page has AI-extracted LOs
        learning_objective_embeddings = []
        if page.ai_learning_objectives:
            lo_inputs = []
            for lo in page.ai_learning_objectives:
                objective = lo.get("objective", "")
                bloom_level = lo.get("bloom_level", "")
                bloom_verb = lo.get("bloom_verb", "")
                difficulty = lo.get("difficulty", "")
                
                # Create rich text for embedding
                parts = [f"Context: {page.title}"]
                parts.append(f"Objective: {objective}")
                if bloom_verb:
                    parts.append(f"Action: {bloom_verb}")
                if bloom_level:
                    parts.append(f"Level: {bloom_level}")
                if difficulty:
                    parts.append(f"Difficulty: {difficulty}")
                
                lo_inputs.append(" | ".join(parts))
            
            if lo_inputs:
                self.stdout.write(
                    f"[page {page.id}] Generating {len(lo_inputs)} learning objective embeddings..."
                )
                lo_response = client.embeddings.create(model=EMBEDDING_MODEL, input=lo_inputs)
                lo_vectors = [d.embedding for d in lo_response.data]
                
                for lo, vec in zip(page.ai_learning_objectives, lo_vectors):
                    learning_objective_embeddings.append({
                        "objective": lo.get("objective", ""),
                        "bloom_level": lo.get("bloom_level", ""),
                        "bloom_verb": lo.get("bloom_verb", ""),
                        "difficulty": lo.get("difficulty", ""),
                        "estimated_time_minutes": lo.get("estimated_time_minutes"),
                        "measurable": lo.get("measurable"),
                        "embedding_model": EMBEDDING_MODEL,
                        "embedding": vec,
                    })
        
        # Persist to page
        page.page_embedding = page_embedding
        page.section_embeddings = section_embeddings
        page.learning_objective_embeddings = learning_objective_embeddings
        page.save(update_fields=[
            "page_embedding", 
            "section_embeddings", 
            "learning_objective_embeddings"
        ])

        self.stdout.write(
            self.style.SUCCESS(
                f"[page {page.id}] ✓ Saved {len(section_embeddings)} section + "
                f"{len(learning_objective_embeddings)} LO embeddings (+ full-page)"
            )
        )


