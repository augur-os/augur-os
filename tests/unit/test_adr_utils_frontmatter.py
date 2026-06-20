from src.lib.adr_utils import scan_adrs
from src.lib.frontmatter_utils import write_frontmatter


def test_scan_adrs_reads_frontmatter(tmp_path):
    """scan_adrs should parse YAML frontmatter as primary source."""
    adr = tmp_path / "ADR-100-test-feature.md"
    write_frontmatter(
        adr,
        {
            "status": "Implemented",
            "date": "2026-03-01",
            "deciders": ["Alice"],
            "related": ["ADR-050"],
            "hub": "dev",
            "tags": ["testing"],
            "superseded_by": None,
        },
        "# ADR-100: Test Feature\n\n## Context\n",
    )

    results = scan_adrs(tmp_path)
    assert len(results) == 1
    r = results[0]
    assert r["number"] == 100
    assert r["status"] == "Implemented"
    assert r["date"] == "2026-03-01"
    assert r["title"] == "Test Feature"
    assert r["hub"] == "dev"
    assert r["tags"] == ["testing"]
    assert r["related"] == ["ADR-050"]


def test_scan_adrs_falls_back_to_inline(tmp_path):
    """scan_adrs should still parse old-format ADRs without frontmatter."""
    adr = tmp_path / "ADR-200-legacy.md"
    adr.write_text("# ADR-200: Legacy Format\n\n**Status**: Proposed\n**Date**: 2026-01-01\n\n## Context\n")

    results = scan_adrs(tmp_path)
    assert len(results) == 1
    assert results[0]["status"] == "Proposed"
    assert results[0]["date"] == "2026-01-01"
