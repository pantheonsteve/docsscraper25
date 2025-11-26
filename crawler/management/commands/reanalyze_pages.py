"""
Management command to re-run structural analysis on already crawled pages.

This backfills:
- code_blocks
- prerequisites
- learning_objectives
- next_steps
- has_prerequisites / has_learning_objectives / has_next_steps

using the current extraction logic against stored raw_html.
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from bs4 import BeautifulSoup  # type: ignore

from crawler.models import CrawledPage


class Command(BaseCommand):
    help = "Re-analyze existing CrawledPage records (code blocks & learning objectives)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--page-id",
            type=int,
            help="Re-analyze a single page by ID",
        )
        parser.add_argument(
            "--job-id",
            type=int,
            help="Limit re-analysis to a specific CrawlJob ID",
        )
        parser.add_argument(
            "--client-id",
            type=int,
            help="Limit re-analysis to a specific Client ID",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Maximum number of pages to process",
        )

    def handle(self, *args, **options):
        page_id = options.get("page_id")
        job_id = options.get("job_id")
        client_id = options.get("client_id")
        limit = options.get("limit")

        qs = CrawledPage.objects.all()

        if page_id:
            qs = qs.filter(id=page_id)
        if job_id:
            qs = qs.filter(job_id=job_id)
        if client_id:
            qs = qs.filter(client_id=client_id)

        # Only pages with raw_html are worth re-analyzing
        qs = qs.exclude(Q(raw_html__isnull=True) | Q(raw_html__exact=""))

        total = qs.count()
        if limit:
            qs = qs.order_by("id")[:limit]

        selected = qs.count()
        self.stdout.write(
            self.style.NOTICE(
                f"Re-analyzing {selected} page(s) "
                f"(from {total} with raw_html; filters: "
                f"page_id={page_id}, job_id={job_id}, client_id={client_id})"
            )
        )

        processed = 0
        updated = 0

        for page in qs.iterator():
            processed += 1
            soup = BeautifulSoup(page.raw_html or "", "html.parser")

            # --- Code blocks ---
            code_blocks = self._extract_code_blocks(soup)

            # --- Prereqs / learning objectives / next steps ---
            prereq_ctx = self._extract_prerequisites_and_context(soup)

            # --- Content type / video / troubleshooting metrics ---
            comp = self._extract_comprehensiveness_metrics(soup)

            # Track whether anything changed
            before = {
                "code_blocks": page.code_blocks or [],
                "prerequisites": page.prerequisites or [],
                "learning_objectives": page.learning_objectives or [],
                "next_steps": page.next_steps or [],
                "has_prerequisites": page.has_prerequisites,
                "has_learning_objectives": page.has_learning_objectives,
                "has_next_steps": page.has_next_steps,
                "has_diagrams": page.has_diagrams,
                "has_troubleshooting": page.has_troubleshooting,
                "content_type_diversity": page.content_type_diversity,
            }

            page.code_blocks = code_blocks
            page.prerequisites = prereq_ctx["prerequisites"]
            page.learning_objectives = prereq_ctx["learning_objectives"]
            page.next_steps = prereq_ctx["next_steps"]
            page.has_prerequisites = prereq_ctx["has_prerequisites"]
            page.has_learning_objectives = prereq_ctx["has_learning_objectives"]
            page.has_next_steps = prereq_ctx["has_next_steps"]

            # Update comprehensiveness metrics
            page.has_diagrams = comp["has_diagrams"]
            page.has_troubleshooting = comp["has_troubleshooting"]
            page.content_type_diversity = comp["content_type_diversity"]

            after = {
                "code_blocks": page.code_blocks or [],
                "prerequisites": page.prerequisites or [],
                "learning_objectives": page.learning_objectives or [],
                "next_steps": page.next_steps or [],
                "has_prerequisites": page.has_prerequisites,
                "has_learning_objectives": page.has_learning_objectives,
                "has_next_steps": page.has_next_steps,
                "has_diagrams": page.has_diagrams,
                "has_troubleshooting": page.has_troubleshooting,
                "content_type_diversity": page.content_type_diversity,
            }

            if after != before:
                page.save(
                    update_fields=[
                        "code_blocks",
                        "prerequisites",
                        "learning_objectives",
                        "next_steps",
                        "has_prerequisites",
                        "has_learning_objectives",
                        "has_next_steps",
                        "has_diagrams",
                        "has_troubleshooting",
                        "content_type_diversity",
                    ]
                )
                updated += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Updated page {page.id} ({page.url}) "
                        f"– code_blocks={len(page.code_blocks or [])}, "
                        f"learning_objectives={len(page.learning_objectives or [])}, "
                        f"content_type_diversity={page.content_type_diversity}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Processed {processed} page(s), updated {updated}."
            )
        )

    # ------------------------------------------------------------------
    # Helpers: copy of current spider logic (kept in-sync manually)
    # ------------------------------------------------------------------

    def _extract_code_blocks(self, soup):
        """
        Extract code blocks in the same way as the spider (fallback to <pre> text
        if there's no <code> child).
        """
        import re

        code_blocks = []

        for pre in soup.find_all("pre"):
            code = pre.find("code")

            if code is not None:
                # Try to detect language from class on <code>
                language = ""
                if "class" in code.attrs:
                    classes = code["class"]
                    for cls in classes:
                        if "language-" in cls:
                            language = cls.replace("language-", "")
                            break
                text_source = code
            else:
                # Fallback: use all text inside <pre>
                language = ""
                text_source = pre

            code_text = text_source.get_text()

            code_blocks.append(
                {
                    "language": language or "plaintext",
                    "content": code_text,
                    "line_count": len(code_text.splitlines()),
                    "has_copy_button": pre.find(
                        "button", class_=re.compile("copy")
                    )
                    is not None,
                }
            )

        return code_blocks

    def _extract_prerequisites_and_context(self, soup):
        """
        Copy of spider.extract_prerequisites_and_context, simplified to only
        rely on soup and not on self.
        """
        prerequisites = []
        learning_objectives = []
        next_steps = []

        # Comprehensive patterns
        prereq_patterns = [
            "before you begin",
            "prerequisites",
            "requirements",
            "what you need",
            "you will need",
            "you'll need",
            "assumes you have",
            "required",
            "things you need",
            "before starting",
        ]

        learning_patterns = [
            "learning objectives",
            "you will learn",
            "you'll learn",
            "what you'll learn",
            "what you will learn",
            "what will you learn",  # important for Dynatrace
            "in this guide",
            "this guide covers",
            "this tutorial covers",
            "in this tutorial",
            "by the end",
            "after completing",
        ]

        next_steps_patterns = [
            "next steps",
            "what's next",
            "where to go",
            "continue learning",
            "further reading",
            "what to do next",
        ]

        # Strategy 1: headings
        for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
            heading_text = heading.get_text(strip=True).lower()

            if any(p in heading_text for p in prereq_patterns):
                content = self._extract_content_after_element(heading)
                if content:
                    prerequisites.append(content[:1000])

            if any(p in heading_text for p in learning_patterns):
                content = self._extract_content_after_element(heading)
                if content:
                    learning_objectives.append(content[:1000])

            if any(p in heading_text for p in next_steps_patterns):
                content = self._extract_content_after_element(heading)
                if content:
                    next_steps.append(content[:1000])

        # Strategy 2: bold/strong labels
        for strong in soup.find_all(["strong", "b"]):
            strong_text = strong.get_text(strip=True).lower()

            if any(p in strong_text for p in learning_patterns):
                content = self._extract_content_after_element(strong)
                if content and content not in learning_objectives:
                    learning_objectives.append(content[:1000])

            if any(p in strong_text for p in prereq_patterns):
                content = self._extract_content_after_element(strong)
                if content and content not in prerequisites:
                    prerequisites.append(content[:1000])

        # Strategy 3: paragraphs followed by lists
        for p in soup.find_all(["p", "div"]):
            p_text = p.get_text(strip=True).lower()

            if any(pat in p_text for pat in learning_patterns):
                next_list = p.find_next_sibling(["ul", "ol"])
                if next_list:
                    list_content = next_list.get_text(strip=True)
                    if list_content and list_content not in learning_objectives:
                        learning_objectives.append(list_content[:1000])

            if any(pat in p_text for pat in prereq_patterns):
                next_list = p.find_next_sibling(["ul", "ol"])
                if next_list:
                    list_content = next_list.get_text(strip=True)
                    if list_content and list_content not in prerequisites:
                        prerequisites.append(list_content[:1000])

        # Strategy 4: unlabeled lists near top that look like objectives
        if not learning_objectives:
            main = soup.find("main") or soup.find("article") or soup
            early_lists = main.find_all(["ul", "ol"], limit=3)

            for ul in early_lists:
                items = ul.find_all("li")
                if 2 <= len(items) <= 10:
                    items_text = [li.get_text(strip=True).lower() for li in items]
                    objective_indicators = [
                        "understand",
                        "learn",
                        "describe",
                        "explain",
                        "identify",
                        "demonstrate",
                        "apply",
                        "configure",
                        "create",
                        "use",
                    ]

                    matching_items = sum(
                        1
                        for item in items_text
                        if any(ind in item for ind in objective_indicators)
                    )

                    if matching_items / len(items) > 0.5:
                        list_content = ul.get_text(strip=True)
                        if list_content not in learning_objectives:
                            learning_objectives.append(list_content[:1000])
                            break

        return {
            "prerequisites": prerequisites,
            "learning_objectives": learning_objectives,
            "next_steps": next_steps,
            "has_prerequisites": len(prerequisites) > 0,
            "has_learning_objectives": len(learning_objectives) > 0,
            "has_next_steps": len(next_steps) > 0,
        }

    def _extract_comprehensiveness_metrics(self, soup):
        """
        Copy of spider.extract_comprehensiveness_metrics, limited to fields
        needed for backfill (diagrams, troubleshooting, diversity).
        """
        import re

        # Sections reused from existing extractor
        from bs4 import BeautifulSoup  # noqa: F401  # for type hints only

        # Reuse existing sections logic by approximating: count headings as sections
        sections = soup.find_all(["h2", "h3"])

        diagrams = soup.find_all("img", alt=re.compile("diagram|flow|architecture", re.I))
        videos = soup.find_all("video") or soup.find_all(
            "iframe", src=re.compile("youtube|vimeo", re.I)
        )
        interactive_demos = soup.find_all(
            class_=re.compile("demo|interactive|playground", re.I)
        )

        troubleshooting = any(
            pattern in heading.get_text().lower()
            for heading in soup.find_all(["h2", "h3"])
            for pattern in ["troubleshoot", "common issues", "debugging", "problems", "errors"]
        )

        code_blocks = len(soup.find_all("pre"))

        return {
            "has_diagrams": len(diagrams) > 0,
            "has_troubleshooting": troubleshooting,
            "content_type_diversity": sum(
                [
                    len(diagrams) > 0,
                    len(videos) > 0,
                    len(interactive_demos) > 0,
                    code_blocks > 0,
                    len(soup.find_all("table")) > 0,
                ]
            ),
        }

    def _extract_content_after_element(self, element):
        """
        Simplified copy of spider._extract_content_after_element, using only
        local navigation from the given element.
        """
        content_parts = []

        # For inline elements (strong/b), start from the parent
        if element.name in ["strong", "b", "em", "i"]:
            parent = element.parent
            if parent:
                # Text after the strong tag inside the same parent
                from bs4 import NavigableString  # type: ignore

                remaining_text = "".join(
                    [
                        str(s)
                        for s in element.next_siblings
                        if isinstance(s, NavigableString) or getattr(s, "name", "") != "script"
                    ]
                )
                if remaining_text.strip():
                    content_parts.append(remaining_text.strip())
                start_element = parent
            else:
                start_element = element
        else:
            start_element = element

        # Then traverse following siblings until a same/higher-level heading
        for sibling in start_element.find_next_siblings():
            if element.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                if sibling.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                    sibling_level = int(sibling.name[1])
                    element_level = int(element.name[1])
                    if sibling_level <= element_level:
                        break

            if getattr(sibling, "name", None) == "script":
                continue
            text = sibling.get_text(strip=True)
            if text:
                content_parts.append(text)

        return " ".join(content_parts).strip()


