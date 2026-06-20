"""Auto-generated importability test for wiki_schema."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_wiki_schema_importable():
    """Verify that wiki_schema can be imported without errors."""
    import importlib
    mod = importlib.import_module("wiki_schema")
    assert mod is not None


def test_concept_schema_requires_compiled_truth_and_timeline() -> None:
    from skills.wiki.scripts.wiki_schema import page_schema

    schema = page_schema(page="concepts/example", page_type="concept")

    assert "Compiled truth" in schema["required_sections"]
    assert "Timeline" in schema["required_sections"]


def test_v4_lint_penalties_are_configured() -> None:
    from skills.wiki.scripts.wiki_schema import lint_penalties

    penalties = lint_penalties()

    assert penalties["timeline_entry_missing_at_or_source"] == 40
    assert penalties["timeline_entry_missing_observation"] == 40
    assert penalties["compiled_truth_contains_source_marker"] == 40
    assert penalties["timeline_out_of_order"] == 8
    assert penalties["legacy_concept_article_v3"] == 10
