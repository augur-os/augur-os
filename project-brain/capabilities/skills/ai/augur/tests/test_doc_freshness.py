"""Tests for ops/doc_freshness.py — broken link and stale doc detection.

Validates the auto-doc-freshness ops command: scanning for broken internal
markdown links and stale documentation, then fixing broken links by removing
the link syntax while keeping the text.
"""
from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.lib.ops_protocol import OpsContext

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "doc_freshness.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_spec = importlib.util.spec_from_file_location("ai_doc_freshness", SCRIPT_PATH)
doc_freshness = importlib.util.module_from_spec(_spec)
sys.modules["ai_doc_freshness"] = doc_freshness
assert _spec.loader is not None
_spec.loader.exec_module(doc_freshness)


def _make_ctx(tmp_path: Path, **overrides) -> OpsContext:
    defaults = {"project_root": tmp_path, "difficulty": 0, "dry_run": False}
    defaults.update(overrides)
    return OpsContext(**defaults)


# ---------------------------------------------------------------------------
# Module-level sanity
# ---------------------------------------------------------------------------


class TestModuleInterface:
    def test_name_attribute(self):
        assert doc_freshness.name == "auto-doc-freshness"

    def test_scan_is_callable(self):
        assert callable(doc_freshness.scan)

    def test_fix_is_callable(self):
        assert callable(doc_freshness.fix)


# ---------------------------------------------------------------------------
# Scan — broken links
# ---------------------------------------------------------------------------


class TestScanBrokenLinks:
    def test_no_docs_dir_returns_healthy(self, tmp_path: Path):
        ctx = _make_ctx(tmp_path)
        result = doc_freshness.scan(ctx)
        assert result.severity == "info"
        assert result.issues == []

    def test_valid_links_returns_healthy(self, tmp_path: Path):
        docs = tmp_path / "docs"
        docs.mkdir()
        target = docs / "other.md"
        target.write_text("# Other\nContent here.", encoding="utf-8")
        main = docs / "readme.md"
        main.write_text("See [other doc](other.md) for details.", encoding="utf-8")

        ctx = _make_ctx(tmp_path)
        result = doc_freshness.scan(ctx)
        assert result.issues == []

    def test_broken_link_detected(self, tmp_path: Path):
        docs = tmp_path / "docs"
        docs.mkdir()
        main = docs / "readme.md"
        main.write_text("See [missing](nonexistent.md) for details.", encoding="utf-8")

        ctx = _make_ctx(tmp_path)
        result = doc_freshness.scan(ctx)
        assert len(result.issues) >= 1
        assert any(i["action"] == "broken-link" for i in result.issues)
        assert result.severity == "warning"

    def test_external_urls_are_skipped(self, tmp_path: Path):
        docs = tmp_path / "docs"
        docs.mkdir()
        main = docs / "readme.md"
        main.write_text(
            "See [Google](https://google.com) and [anchor](#section).",
            encoding="utf-8",
        )

        ctx = _make_ctx(tmp_path)
        result = doc_freshness.scan(ctx)
        assert result.issues == []

    def test_difficulty_controls_glob_scope(self, tmp_path: Path):
        """At difficulty=0 only docs/ is scanned; at difficulty>=1 SKILL.md files too."""
        docs = tmp_path / "docs"
        docs.mkdir()
        plugins = tmp_path / "plugins" / "ai" / "skills" / "test_skill"
        plugins.mkdir(parents=True)
        skill_md = plugins / "SKILL.md"
        skill_md.write_text("See [gone](gone.md) link.", encoding="utf-8")

        # difficulty=0 should NOT pick up SKILL.md
        ctx = _make_ctx(tmp_path, difficulty=0)
        result = doc_freshness.scan(ctx)
        broken_skill = [i for i in result.issues if "SKILL.md" in i.get("file", "")]
        assert broken_skill == []

        # difficulty=1 should pick up SKILL.md
        ctx = _make_ctx(tmp_path, difficulty=1)
        result = doc_freshness.scan(ctx)
        broken_skill = [i for i in result.issues if "SKILL.md" in i.get("file", "")]
        assert len(broken_skill) == 1

    def test_links_inside_code_are_ignored(self, tmp_path: Path):
        docs = tmp_path / "docs"
        docs.mkdir()
        main = docs / "plan.md"
        main.write_text(
            """# Plan

```python
return _PROVIDERS[provider](audio_path, options or {})
r = tools["audio-classify"](
    transcript_text="ok",
)
```

Ignore inline code too: `tools["enrich-article"](str(note))`.

But catch [missing](missing.md) in prose.
""",
            encoding="utf-8",
        )

        result = doc_freshness.scan(_make_ctx(tmp_path))

        assert [issue["line"] for issue in result.issues] == [12]
        assert result.issues[0]["link_text"] == "missing"


# ---------------------------------------------------------------------------
# Scan — stale docs
# ---------------------------------------------------------------------------


class TestScanStaleDocs:
    def test_stale_docs_only_at_difficulty_2(self, tmp_path: Path):
        docs = tmp_path / "docs"
        docs.mkdir()
        stale = docs / "old.md"
        stale.write_text("# Old Doc", encoding="utf-8")
        # Make it old
        old_time = time.time() - (100 * 86400)
        import os
        os.utime(stale, (old_time, old_time))

        ctx = _make_ctx(tmp_path, difficulty=1)
        result = doc_freshness.scan(ctx)
        stale_issues = [i for i in result.issues if i.get("action") == "stale-doc"]
        assert stale_issues == []

        ctx = _make_ctx(tmp_path, difficulty=2)
        result = doc_freshness.scan(ctx)
        stale_issues = [i for i in result.issues if i.get("action") == "stale-doc"]
        assert len(stale_issues) >= 1


# ---------------------------------------------------------------------------
# Fix
# ---------------------------------------------------------------------------


class TestFix:
    def test_dry_run_returns_summary(self, tmp_path: Path):
        ctx = _make_ctx(tmp_path, dry_run=True)
        issues = [{"action": "broken-link", "file": "docs/a.md", "link_text": "A", "link_target": "b.md"}]
        result = doc_freshness.fix(ctx, issues)
        assert result.success is True
        assert "Dry run" in result.summary

    @patch.object(doc_freshness, "_commit_files", return_value=None)
    def test_broken_link_fix_replaces_link_with_text(self, _mock_commit, tmp_path: Path):
        docs = tmp_path / "docs"
        docs.mkdir()
        md = docs / "readme.md"
        md.write_text("See [missing](nonexistent.md) for details.", encoding="utf-8")

        issues = [
            {
                "action": "broken-link",
                "file": "docs/readme.md",
                "link_text": "missing",
                "link_target": "nonexistent.md",
                "line": 1,
            }
        ]
        ctx = _make_ctx(tmp_path)
        result = doc_freshness.fix(ctx, issues)
        assert result.success is True
        assert "missing" in md.read_text()
        assert "[missing]" not in md.read_text()

    def test_stale_docs_are_not_auto_fixed(self, tmp_path: Path):
        ctx = _make_ctx(tmp_path)
        issues = [{"action": "stale-doc", "file": "docs/old.md", "age_days": 120}]
        result = doc_freshness.fix(ctx, issues)
        assert result.success is True
        assert "manual review" in result.summary.lower() or "stale" in result.summary.lower()
