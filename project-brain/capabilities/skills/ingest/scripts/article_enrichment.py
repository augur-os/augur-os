"""Pure-logic helpers for ADR-753 article enrichment.

Owns:
  - section template (5 named top-level sections)
  - body splitter: parse a note's markdown body into {section: content} + raw_content
  - body composer: render enriched sections + raw_content back into a body string
  - frontmatter stamping for enrichment status / version
  - LLM-Assisted MCP Pattern dispatch payload builder

NO I/O. The MCP tool layer (tools_enrich.py) and daemon job
(run_pending_enrichment.py) are responsible for reading and writing files.
"""
from __future__ import annotations

import re
from typing import Any


ENRICHMENT_SECTIONS = (
    "Executive summary",
    "Key insights",
    "Why it matters",
    "Verbatim quotes",
    "Cross-references",
)

RAW_SECTION_HEADING = "Original content"

_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def split_body(body: str) -> tuple[dict[str, str], str]:
    """Split a body into (enriched_sections, raw_content).

    enriched_sections is a dict from heading to content (without the heading
    line) for any of the five known enrichment sections found in the body.
    raw_content is everything under "## Original content" (or the entire body
    when no enrichment has been applied yet).
    """
    sections: dict[str, str] = {}
    raw = body
    headings = list(_H2_RE.finditer(body))
    if not headings:
        return {}, body.strip() + "\n"

    # Build section spans.
    for i, m in enumerate(headings):
        name = m.group(1).strip()
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(body)
        content = body[start:end].strip("\n")
        if name == RAW_SECTION_HEADING:
            raw = content
        elif name in ENRICHMENT_SECTIONS:
            sections[name] = content
    # If we never hit "Original content" but did find enrichment sections,
    # the raw is whatever comes after the last enrichment section that isn't
    # itself a known section. Fall back to the whole body for safety when
    # the markdown structure is unfamiliar.
    if not any(m.group(1).strip() == RAW_SECTION_HEADING for m in headings) and not sections:
        return {}, body.strip() + "\n"
    return sections, raw.strip() + "\n"


def compose_body(enriched_sections: dict[str, str], raw_content: str) -> str:
    parts: list[str] = []
    for name in ENRICHMENT_SECTIONS:
        if name in enriched_sections and enriched_sections[name].strip():
            parts.append(f"## {name}\n\n{enriched_sections[name].strip()}\n")
    parts.append(f"## {RAW_SECTION_HEADING}\n\n{raw_content.strip()}\n")
    return "\n".join(parts).rstrip() + "\n"


def stamp_enrichment_frontmatter(fm: dict[str, Any], version: int) -> dict[str, Any]:
    new_fm = dict(fm)
    new_fm["x-augur-enrichment-status"] = "enriched"
    current = int(fm.get("x-augur-enrichment-version", 0) or 0)
    if version > current:
        new_fm["x-augur-enrichment-version"] = version
    else:
        new_fm["x-augur-enrichment-version"] = max(current, version)
    return new_fm


def build_llm_dispatch_payload(
    *,
    note_title: str,
    note_url: str | None,
    raw_content: str,
    existing_entities: list[str],
) -> dict[str, Any]:
    """Build the {needs_llm: true, ...} payload returned by the enrich-article tool.

    The AI client reads `instructions` and `raw_content_preview`, produces
    the five fields, and calls submit-enrich-article-result with them.
    """
    preview = raw_content[:8000]
    return {
        "needs_llm": True,
        "task": "enrich-article",
        "note_title": note_title,
        "note_url": note_url,
        "raw_content_preview": preview,
        "raw_content_full_length_chars": len(raw_content),
        "existing_entities": existing_entities,
        "instructions": (
            "Produce a structured enrichment of the source article. Output JSON with five fields. "
            "Executive summary: 3-7 bullets. Key insights: 3-5 numbered insights specific to this piece. "
            "Why it matters: one 2-4 sentence paragraph tied to existing_entities when relevant. "
            "Verbatim quotes: 1-3 of the longest impactful passages, preserved verbatim. "
            "Cross-references: a list of wiki page slugs (e.g. 'concepts/leverage') that would link from this note. "
            "Use existing_entities as candidates for cross-references; you may add new ones."
        ),
        "expected_result_schema": {
            "executive_summary": "string (markdown bullet list, 3-7 bullets)",
            "key_insights": "string (markdown numbered list, 3-5 insights)",
            "why_it_matters": "string (one paragraph, 2-4 sentences)",
            "verbatim_quotes": "string (markdown blockquotes, 1-3 quotes, longest impactful passages, preserved verbatim from the source)",
            "cross_references": "list of wiki page slugs to link, e.g. ['concepts/leverage']",
        },
    }
