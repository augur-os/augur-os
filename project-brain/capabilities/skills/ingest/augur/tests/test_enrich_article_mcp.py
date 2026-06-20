from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
TOOLS_PATH = (
    PROJECT_ROOT
    / "project-brain"
    / "capabilities"
    / "skills"
    / "ingest"
    / "scripts"
    / "mcp"
    / "tools_enrich.py"
)
SKILL_PATH = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "ingest" / "SKILL.md"
CAPABILITY_PATH = PROJECT_ROOT / "config" / "system" / "capability_exposure.yaml"


def _load_tools():
    spec = importlib.util.spec_from_file_location("ingest_tools_enrich", TOOLS_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_tools_enrich"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeMcp:
    def __init__(self) -> None:
        self.tools = {}
        self.annotations = {}

    def tool(self, name, annotations=None):
        def decorator(func):
            self.tools[name] = func
            self.annotations[name] = annotations
            return func

        return decorator


def _capture(mod):
    fake = FakeMcp()
    mod.register_enrich_tools(fake, lambda func: func, None)
    return fake


def _write_note(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, yaml_block, _ = text.split("---\n", 2)
    parsed = yaml.safe_load(yaml_block)
    return parsed if isinstance(parsed, dict) else {}


def test_register_enrich_tools_exposes_names_and_annotations() -> None:
    mod = _load_tools()
    fake = _capture(mod)

    assert "enrich-article" in fake.tools
    assert "submit-enrich-article-result" in fake.tools
    assert fake.annotations["enrich-article"]["title"] == "Enrich Article"
    assert fake.annotations["enrich-article"]["readOnlyHint"] is True
    assert fake.annotations["submit-enrich-article-result"]["title"] == "Submit Enrich Article Result"
    assert fake.annotations["submit-enrich-article-result"]["readOnlyHint"] is False
    assert fake.annotations["submit-enrich-article-result"]["idempotentHint"] is True


def test_enrich_article_returns_needs_llm_payload_for_url_note(tmp_path: Path) -> None:
    mod = _load_tools()
    fake = _capture(mod)
    note = _write_note(
        tmp_path / "2026-05-16-url-test.md",
        """---
title: Test Article
url: https://example.com/article
x-augur-note-type: url
tags:
- leverage
---

## Original content

This is a test article about leverage and [[wiki/concepts/architecture]].
""",
    )

    result = fake.tools["enrich-article"](str(note))

    assert result.get("needs_llm") is True
    assert result["task"] == "enrich-article"
    assert result["note_path"] == str(note)
    assert result["note_title"] == "Test Article"
    assert result["note_url"] == "https://example.com/article"
    assert "raw_content_preview" in result
    assert "This is a test article" in result["raw_content_preview"]
    assert "instructions" in result
    assert "expected_result_schema" in result
    assert "leverage" in result["existing_entities"]
    assert "concepts/architecture" in result["existing_entities"]


def test_enrich_article_accepts_file_note(tmp_path: Path) -> None:
    mod = _load_tools()
    fake = _capture(mod)
    note = _write_note(
        tmp_path / "2026-05-16-file-test.md",
        """---
title: File Article
x-augur-note-type: file
source_path: C:/Users/intel/Documents/article.pdf
---

Extracted article body.
""",
    )

    result = fake.tools["enrich-article"](str(note))

    assert result.get("needs_llm") is True
    assert result["note_path"] == str(note)
    assert "Extracted article body." in result["raw_content_preview"]


def test_enrich_article_rejects_missing_note(tmp_path: Path) -> None:
    mod = _load_tools()
    fake = _capture(mod)

    result = fake.tools["enrich-article"](str(tmp_path / "missing.md"))

    assert result["success"] is False
    assert "note not found" in result["error"]


def test_enrich_article_rejects_missing_note_type(tmp_path: Path) -> None:
    mod = _load_tools()
    fake = _capture(mod)
    note = _write_note(
        tmp_path / "2026-05-16-unknown-test.md",
        """---
title: Missing Type
---

Body.
""",
    )

    result = fake.tools["enrich-article"](str(note))

    assert result["success"] is False
    assert "x-augur-note-type" in result["error"]


def test_enrich_article_rejects_non_url_or_file_note(tmp_path: Path) -> None:
    mod = _load_tools()
    fake = _capture(mod)
    note = _write_note(
        tmp_path / "2026-05-16-thought-test.md",
        """---
title: Thought
x-augur-note-type: thought
---

I think.
""",
    )

    result = fake.tools["enrich-article"](str(note))

    assert result["success"] is False
    assert "thought" in result["error"]


def test_enrich_article_skips_already_enriched_at_current_version(tmp_path: Path) -> None:
    mod = _load_tools()
    fake = _capture(mod)
    note = _write_note(
        tmp_path / "2026-05-16-url-test.md",
        """---
title: Test
url: https://example.com
x-augur-note-type: url
x-augur-enrichment-status: enriched
x-augur-enrichment-version: 1
---

## Executive summary

- Existing.

## Original content

This is a test article.
""",
    )

    result = fake.tools["enrich-article"](str(note))

    assert result["success"] is True
    assert result["skipped"] is True
    assert result["reason"] == "already enriched"


def test_submit_enrich_article_result_writes_sections_and_preserves_raw_content(
    tmp_path: Path,
) -> None:
    mod = _load_tools()
    fake = _capture(mod)
    note = _write_note(
        tmp_path / "2026-05-16-url-test.md",
        """---
title: Test
url: https://example.com
x-augur-note-type: url
---

## Original content

The architecture of leverage is in the compounding.
""",
    )

    result = fake.tools["submit-enrich-article-result"](
        note_path=str(note),
        executive_summary="- leverage compounds\n- architects build leverage\n",
        key_insights="1. compounding is more durable than throughput\n",
        why_it_matters="Because friction makes future work slower.\n",
        verbatim_quotes="> The architecture of leverage is in the compounding.\n",
        cross_references_json=["concepts/leverage", "wiki/concepts/architecture", ""],
    )

    assert result["success"] is True
    metadata = _frontmatter(note)
    assert metadata["x-augur-enrichment-status"] == "enriched"
    assert metadata["x-augur-enrichment-version"] == 1
    text = note.read_text(encoding="utf-8")
    assert "## Executive summary" in text
    assert "## Key insights" in text
    assert "## Why it matters" in text
    assert "## Verbatim quotes" in text
    assert "## Cross-references" in text
    assert "- [[wiki/concepts/leverage]]" in text
    assert "- [[wiki/concepts/architecture]]" in text
    assert text.count("## Original content") == 1
    assert text.index("## Cross-references") < text.index("## Original content")
    assert "The architecture of leverage is in the compounding." in text
    assert result["sections_written"] == [
        "Executive summary",
        "Key insights",
        "Why it matters",
        "Verbatim quotes",
        "Cross-references",
    ]


def test_submit_enrich_article_result_accepts_cross_references_json_string(
    tmp_path: Path,
) -> None:
    mod = _load_tools()
    fake = _capture(mod)
    note = _write_note(
        tmp_path / "2026-05-16-file-test.md",
        """---
title: File
x-augur-note-type: file
---

Raw file content.
""",
    )

    result = fake.tools["submit-enrich-article-result"](
        note_path=str(note),
        executive_summary="- summary\n",
        key_insights="1. insight\n",
        why_it_matters="It matters.\n",
        verbatim_quotes="> Raw file content.\n",
        cross_references_json='["concepts/files"]',
    )

    assert result["success"] is True
    assert "[[wiki/concepts/files]]" in note.read_text(encoding="utf-8")


def test_skill_and_capability_exposure_declare_enrich_tools() -> None:
    skill_text = SKILL_PATH.read_text(encoding="utf-8")
    _, skill_yaml, _ = skill_text.split("---\n", 2)
    skill_meta = yaml.safe_load(skill_yaml)
    tools = skill_meta["x-augur-mcp-tools"]
    assert "enrich-article" in tools
    assert "submit-enrich-article-result" in tools

    capability = yaml.safe_load(CAPABILITY_PATH.read_text(encoding="utf-8"))
    capabilities = capability["capabilities"]
    assert "mcp-tool:enrich-article" in capabilities
    assert "mcp-tool:submit-enrich-article-result" in capabilities
    assert capabilities["mcp-tool:enrich-article"]["classification_status"] == "approved"
    assert (
        capabilities["mcp-tool:submit-enrich-article-result"]["classification_status"]
        == "approved"
    )
