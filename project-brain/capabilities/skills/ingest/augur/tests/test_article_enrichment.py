from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
ENRICH_PATH = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "ingest" / "scripts" / "article_enrichment.py"
FIXTURES = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "ingest" / "augur" / "tests" / "fixtures"


def _load_enrichment():
    spec = importlib.util.spec_from_file_location("ingest_article_enrichment", ENRICH_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_article_enrichment"] = module
    spec.loader.exec_module(module)
    return module


def test_split_raw_content_finds_original_section():
    m = _load_enrichment()
    body = (FIXTURES / "raw_article_short.md").read_text().split("---", 2)[2]
    enriched_sections, raw_content = m.split_body(body)
    assert enriched_sections == {}
    assert "Leverage in software" in raw_content


def test_split_recognizes_existing_enrichment():
    m = _load_enrichment()
    body = (FIXTURES / "enriched_article_short.md").read_text().split("---", 2)[2]
    enriched_sections, raw_content = m.split_body(body)
    assert "Executive summary" in enriched_sections
    assert "Key insights" in enriched_sections
    assert "Why it matters" in enriched_sections
    assert "Verbatim quotes" in enriched_sections
    assert "Cross-references" in enriched_sections
    assert "Leverage in software" in raw_content


def test_compose_enriched_body_round_trips():
    m = _load_enrichment()
    sections = {
        "Executive summary": "- bullet a\n- bullet b\n",
        "Key insights": "1. one\n2. two\n",
        "Why it matters": "Because.\n",
        "Verbatim quotes": "> quote\n",
        "Cross-references": "- [[wiki/x]]\n",
    }
    raw = "Original article text.\n"
    body = m.compose_body(sections, raw)
    enriched_sections, raw_back = m.split_body(body)
    assert set(enriched_sections.keys()) == set(sections.keys())
    assert "Original article text." in raw_back


def test_idempotency_marker_in_frontmatter():
    m = _load_enrichment()
    fm_before = {"title": "x", "x-augur-note-type": "url"}
    fm_after = m.stamp_enrichment_frontmatter(fm_before, version=1)
    assert fm_after["x-augur-enrichment-status"] == "enriched"
    assert fm_after["x-augur-enrichment-version"] == 1
    fm_again = m.stamp_enrichment_frontmatter(fm_after, version=1)
    assert fm_again["x-augur-enrichment-version"] == 1


def test_idempotency_marker_bumps_on_higher_version():
    m = _load_enrichment()
    fm = {"x-augur-enrichment-status": "enriched", "x-augur-enrichment-version": 1}
    fm_v2 = m.stamp_enrichment_frontmatter(fm, version=2)
    assert fm_v2["x-augur-enrichment-version"] == 2


def test_build_llm_dispatch_payload():
    m = _load_enrichment()
    payload = m.build_llm_dispatch_payload(
        note_title="The Architecture of Leverage",
        note_url="https://example.com/leverage",
        raw_content="Leverage is the multiplier that lets one good decision pay dividends.",
        existing_entities=["leverage", "architecture"],
    )
    assert payload["needs_llm"] is True
    assert payload["task"] == "enrich-article"
    assert "instructions" in payload
    assert payload["expected_result_schema"] == {
        "executive_summary": "string (markdown bullet list, 3-7 bullets)",
        "key_insights": "string (markdown numbered list, 3-5 insights)",
        "why_it_matters": "string (one paragraph, 2-4 sentences)",
        "verbatim_quotes": "string (markdown blockquotes, 1-3 quotes, longest impactful passages, preserved verbatim from the source)",
        "cross_references": "list of wiki page slugs to link, e.g. ['concepts/leverage']",
    }
    assert "leverage" in payload["existing_entities"]
