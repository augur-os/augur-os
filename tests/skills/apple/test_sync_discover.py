"""Tests for sync_discover.py — content-based vault sync discovery scanner."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ─── path setup ───────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.config.paths import get_skill_root

APPLE_AVAILABLE = True
APPLE_UNAVAILABLE_REASON = ""
try:
    APPLE_SCRIPTS = get_skill_root("apple") / "scripts"
except ValueError as exc:
    APPLE_AVAILABLE = False
    APPLE_UNAVAILABLE_REASON = f"Apple skill is not installed in this checkout: {exc}"
    APPLE_SCRIPTS = None
if APPLE_SCRIPTS is not None and not (APPLE_SCRIPTS / "sync_discover.py").is_file():
    APPLE_AVAILABLE = False
    APPLE_UNAVAILABLE_REASON = (
        f"Apple sync discovery script is not installed in this checkout: {APPLE_SCRIPTS / 'sync_discover.py'}"
    )
if APPLE_AVAILABLE and APPLE_SCRIPTS is not None and str(APPLE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(APPLE_SCRIPTS))

if APPLE_AVAILABLE:
    from sync_discover import (
        DataItem,
        SyncItem,
        _parse_frontmatter_and_body,
        _parse_frontmatter_only,
        discover,
        discover_by_target,
        discover_data,
    )

pytestmark = pytest.mark.skipif(not APPLE_AVAILABLE, reason=APPLE_UNAVAILABLE_REASON)


# ─── helpers ──────────────────────────────────────────────────────────────────


def _write_md(path: Path, frontmatter: str, body: str = "") -> Path:
    """Write a markdown file with optional YAML frontmatter."""
    content = f"---\n{frontmatter}\n---\n{body}" if frontmatter else body
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ─── tests ────────────────────────────────────────────────────────────────────


class TestParserFrontmatterOnly:
    """Unit tests for the _parse_frontmatter_only helper."""

    def test_parses_valid_frontmatter(self, tmp_path: Path) -> None:
        md = _write_md(tmp_path / "a.md", 'sync_target: notes\ntitle: "My Note"')
        fm = _parse_frontmatter_only(md)
        assert fm["sync_target"] == "notes"
        assert fm["title"] == "My Note"

    def test_returns_empty_for_no_frontmatter(self, tmp_path: Path) -> None:
        md = tmp_path / "b.md"
        md.write_text("Just some text\nno frontmatter here\n", encoding="utf-8")
        assert _parse_frontmatter_only(md) == {}

    def test_returns_empty_for_unclosed_frontmatter(self, tmp_path: Path) -> None:
        md = tmp_path / "c.md"
        md.write_text("---\ntitle: oops\nno closing marker\n", encoding="utf-8")
        assert _parse_frontmatter_only(md) == {}

    def test_returns_empty_for_empty_frontmatter(self, tmp_path: Path) -> None:
        md = tmp_path / "d.md"
        md.write_text("---\n---\nbody\n", encoding="utf-8")
        assert _parse_frontmatter_only(md) == {}


class TestDiscover:
    """Tests for the main discover() function."""

    def test_discover_returns_sync_items(self, tmp_path: Path) -> None:
        """File with sync_target: notes in frontmatter is found."""
        _write_md(
            tmp_path / "note.md",
            'sync_target: notes\ntitle: "My Sync Note"',
            body="Some body content",
        )
        items = discover(tmp_path)
        assert len(items) == 1
        assert items[0].sync_target == "notes"
        assert items[0].title == "My Sync Note"
        assert items[0].path == (tmp_path / "note.md").resolve()

    def test_discover_skips_no_frontmatter(self, tmp_path: Path) -> None:
        """Plain markdown without frontmatter is skipped."""
        md = tmp_path / "plain.md"
        md.write_text("sync_target: notes\nJust plain text\n", encoding="utf-8")
        items = discover(tmp_path)
        assert len(items) == 0

    def test_discover_skips_sync_target_in_body(self, tmp_path: Path) -> None:
        """sync_target: in body text (not frontmatter) is skipped."""
        _write_md(
            tmp_path / "body.md",
            'title: "No Sync"',
            body="sync_target: notes\nThis is in the body, not frontmatter.",
        )
        items = discover(tmp_path)
        assert len(items) == 0

    def test_discover_skips_unknown_target(self, tmp_path: Path) -> None:
        """sync_target: dropbox is skipped with warning."""
        _write_md(
            tmp_path / "dropbox.md",
            'sync_target: dropbox\ntitle: "Dropbox File"',
        )
        items = discover(tmp_path)
        assert len(items) == 0

    def test_discover_multiple_files(self, tmp_path: Path) -> None:
        """Multiple sync files discovered and sorted."""
        _write_md(tmp_path / "a.md", 'sync_target: reminders\ntitle: "Reminders A"')
        _write_md(tmp_path / "b.md", 'sync_target: notes\ntitle: "Notes B"')
        _write_md(tmp_path / "c.md", 'sync_target: notes\ntitle: "Notes C"')
        items = discover(tmp_path)
        assert len(items) == 3
        # Sorted by (target, path): notes before reminders
        assert items[0].sync_target == "notes"
        assert items[1].sync_target == "notes"
        assert items[2].sync_target == "reminders"

    def test_discover_nested_directories(self, tmp_path: Path) -> None:
        """Files in nested vault directories are found."""
        _write_md(
            tmp_path / "hub" / "skill" / "notes" / "deep.md",
            'sync_target: notes\ntitle: "Deep Note"',
        )
        items = discover(tmp_path)
        assert len(items) == 1
        assert items[0].title == "Deep Note"


class TestDiscoverByTarget:
    """Tests for discover_by_target() filtering."""

    def test_discover_by_target_filters(self, tmp_path: Path) -> None:
        """Filters correctly between notes and reminders."""
        _write_md(tmp_path / "note.md", 'sync_target: notes\ntitle: "Note"')
        _write_md(tmp_path / "reminder.md", 'sync_target: reminders\ntitle: "Reminder"')

        notes = discover_by_target("notes", tmp_path)
        assert len(notes) == 1
        assert notes[0].sync_target == "notes"

        reminders = discover_by_target("reminders", tmp_path)
        assert len(reminders) == 1
        assert reminders[0].sync_target == "reminders"

    def test_discover_by_target_no_matches(self, tmp_path: Path) -> None:
        """Returns empty list when no files match the target."""
        _write_md(tmp_path / "note.md", 'sync_target: notes\ntitle: "Note"')
        reminders = discover_by_target("reminders", tmp_path)
        assert len(reminders) == 0


class TestOptionalFields:
    """Tests for optional frontmatter field extraction."""

    def test_discover_extracts_optional_fields(self, tmp_path: Path) -> None:
        """sync_folder, sync_id, sync_list, sync_section extracted."""
        fm = "sync_target: notes\n" 'title: "Full Note"\n' 'sync_folder: "My Folder"\n' 'sync_id: "note-123"'
        _write_md(tmp_path / "full.md", fm)
        items = discover(tmp_path)
        assert len(items) == 1
        assert items[0].sync_folder == "My Folder"
        assert items[0].sync_id == "note-123"
        assert items[0].sync_list is None
        assert items[0].sync_section is None

    def test_discover_extracts_reminders_fields(self, tmp_path: Path) -> None:
        """sync_list and sync_section extracted for reminders."""
        fm = "sync_target: reminders\n" 'title: "Shopping"\n' 'sync_list: "Shopping"\n' 'sync_section: "Groceries"'
        _write_md(tmp_path / "shopping.md", fm)
        items = discover(tmp_path)
        assert len(items) == 1
        assert items[0].sync_list == "Shopping"
        assert items[0].sync_section == "Groceries"

    def test_title_defaults_to_stem(self, tmp_path: Path) -> None:
        """When title is missing, defaults to file stem."""
        _write_md(tmp_path / "untitled.md", "sync_target: notes")
        items = discover(tmp_path)
        assert len(items) == 1
        assert items[0].title == "untitled"


class TestFallbackWhenRgMissing:
    """Tests for grep fallback when rg is not installed."""

    def test_discover_fallback_when_rg_missing(self, tmp_path: Path) -> None:
        """Falls back to grep when rg is not on PATH."""
        _write_md(tmp_path / "note.md", 'sync_target: notes\ntitle: "Fallback Note"')

        original_which = __import__("shutil").which

        def mock_which(cmd: str) -> str | None:
            if cmd == "rg":
                return None
            return original_which(cmd)

        with patch("sync_discover.shutil.which", side_effect=mock_which):
            items = discover(tmp_path)

        assert len(items) == 1
        assert items[0].title == "Fallback Note"


class TestSyncItemSerialization:
    """Tests for SyncItem.to_dict() serialization."""

    def test_to_dict_serializes_path(self) -> None:
        item = SyncItem(
            path=Path("/vault/note.md"),
            sync_target="notes",
            title="Test",
        )
        d = item.to_dict()
        assert d["path"] == "/vault/note.md"
        assert d["sync_target"] == "notes"
        assert d["sync_folder"] is None


class TestNonExistentVault:
    """Tests for error handling with missing vault."""

    def test_discover_empty_on_missing_vault(self, tmp_path: Path) -> None:
        """Returns empty list when vault root does not exist."""
        items = discover(tmp_path / "nonexistent")
        assert items == []


# ─── ADR-453: data source discovery tests ────────────────────────────────────


class TestParseFrontmatterAndBody:
    """Unit tests for the _parse_frontmatter_and_body helper."""

    def test_parses_frontmatter_and_body(self, tmp_path: Path) -> None:
        md = _write_md(
            tmp_path / "a.md",
            'data_source: dashboard\ntitle: "Test"',
            body="Body content here.",
        )
        fm, body = _parse_frontmatter_and_body(md)
        assert fm["data_source"] == "dashboard"
        assert fm["title"] == "Test"
        assert "Body content here." in body

    def test_no_frontmatter_returns_full_body(self, tmp_path: Path) -> None:
        md = tmp_path / "b.md"
        md.write_text("Just plain text\nSecond line\n", encoding="utf-8")
        fm, body = _parse_frontmatter_and_body(md)
        assert fm == {}
        assert "Just plain text" in body
        assert "Second line" in body

    def test_empty_frontmatter_returns_body(self, tmp_path: Path) -> None:
        md = tmp_path / "c.md"
        md.write_text("---\n---\nBody after empty frontmatter\n", encoding="utf-8")
        fm, body = _parse_frontmatter_and_body(md)
        assert fm == {}
        assert "Body after empty frontmatter" in body

    def test_unclosed_frontmatter_returns_empty(self, tmp_path: Path) -> None:
        md = tmp_path / "d.md"
        md.write_text("---\ntitle: oops\nno closing\n", encoding="utf-8")
        fm, body = _parse_frontmatter_and_body(md)
        assert fm == {}
        assert body == ""


class TestDiscoverData:
    """Tests for discover_data() — data source discovery (ADR-453)."""

    def test_discovers_data_source_files(self, tmp_path: Path) -> None:
        """File with data_source: dashboard in frontmatter is found."""
        _write_md(
            tmp_path / "ideas.md",
            'data_source: dashboard\ndata_type: ideas\nskill: venture\ntitle: "Startup Ideas"',
            body="## My Ideas\n- Idea 1\n- Idea 2",
        )
        items = discover_data(vault_root=tmp_path)
        assert len(items) == 1
        assert items[0].data_type == "ideas"
        assert items[0].skill == "venture"
        assert items[0].title == "Startup Ideas"

    def test_skips_unknown_data_source(self, tmp_path: Path) -> None:
        """data_source: unknown is skipped."""
        _write_md(
            tmp_path / "bad.md",
            'data_source: unknown\ndata_type: stuff\nskill: test\ntitle: "Bad"',
        )
        items = discover_data(vault_root=tmp_path)
        assert len(items) == 0

    def test_filters_by_data_type(self, tmp_path: Path) -> None:
        """Filters correctly by data_type parameter."""
        _write_md(
            tmp_path / "ideas.md",
            'data_source: dashboard\ndata_type: ideas\nskill: venture\ntitle: "Ideas"',
        )
        _write_md(
            tmp_path / "notes.md",
            'data_source: dashboard\ndata_type: notes\nskill: venture\ntitle: "Notes"',
        )

        ideas = discover_data(data_type="ideas", vault_root=tmp_path)
        assert len(ideas) == 1
        assert ideas[0].data_type == "ideas"

        notes = discover_data(data_type="notes", vault_root=tmp_path)
        assert len(notes) == 1
        assert notes[0].data_type == "notes"

    def test_filters_by_skill(self, tmp_path: Path) -> None:
        """Filters correctly by skill parameter."""
        _write_md(
            tmp_path / "a.md",
            'data_source: dashboard\ndata_type: ideas\nskill: venture\ntitle: "Venture"',
        )
        _write_md(
            tmp_path / "b.md",
            'data_source: dashboard\ndata_type: ideas\nskill: career\ntitle: "Career"',
        )

        venture = discover_data(skill="venture", vault_root=tmp_path)
        assert len(venture) == 1
        assert venture[0].skill == "venture"

    def test_filters_by_both(self, tmp_path: Path) -> None:
        """Combined data_type + skill filtering."""
        _write_md(
            tmp_path / "a.md",
            'data_source: dashboard\ndata_type: ideas\nskill: venture\ntitle: "A"',
        )
        _write_md(
            tmp_path / "b.md",
            'data_source: dashboard\ndata_type: notes\nskill: venture\ntitle: "B"',
        )
        _write_md(
            tmp_path / "c.md",
            'data_source: dashboard\ndata_type: ideas\nskill: career\ntitle: "C"',
        )

        results = discover_data(data_type="ideas", skill="venture", vault_root=tmp_path)
        assert len(results) == 1
        assert results[0].title == "A"

    def test_returns_empty_for_no_data_files(self, tmp_path: Path) -> None:
        """Returns empty when no data_source files exist."""
        _write_md(tmp_path / "sync.md", 'sync_target: notes\ntitle: "Not Data"')
        items = discover_data(vault_root=tmp_path)
        assert len(items) == 0

    def test_returns_empty_for_missing_vault(self, tmp_path: Path) -> None:
        """Returns empty when vault does not exist."""
        items = discover_data(vault_root=tmp_path / "nonexistent")
        assert items == []

    def test_title_defaults_to_stem(self, tmp_path: Path) -> None:
        """When title is missing, defaults to file stem."""
        _write_md(tmp_path / "my-data.md", "data_source: dashboard\ndata_type: config\nskill: test")
        items = discover_data(vault_root=tmp_path)
        assert len(items) == 1
        assert items[0].title == "my-data"

    def test_sorted_by_type_skill_path(self, tmp_path: Path) -> None:
        """Results are sorted by (data_type, skill, path)."""
        _write_md(
            tmp_path / "z.md",
            'data_source: dashboard\ndata_type: notes\nskill: alpha\ntitle: "Z"',
        )
        _write_md(
            tmp_path / "a.md",
            'data_source: dashboard\ndata_type: ideas\nskill: beta\ntitle: "A"',
        )
        items = discover_data(vault_root=tmp_path)
        assert len(items) == 2
        assert items[0].data_type == "ideas"
        assert items[1].data_type == "notes"

    def test_does_not_interfere_with_sync_discover(self, tmp_path: Path) -> None:
        """discover_data ignores sync_target-only files; discover ignores data_source-only files."""
        _write_md(
            tmp_path / "sync.md",
            'sync_target: notes\ntitle: "Sync Only"',
        )
        _write_md(
            tmp_path / "data.md",
            'data_source: dashboard\ndata_type: ideas\nskill: test\ntitle: "Data Only"',
        )

        sync_items = discover(tmp_path)
        data_items = discover_data(vault_root=tmp_path)

        assert len(sync_items) == 1
        assert sync_items[0].title == "Sync Only"
        assert len(data_items) == 1
        assert data_items[0].title == "Data Only"


class TestDataItemSerialization:
    """Tests for DataItem.to_dict() serialization."""

    def test_to_dict_serializes_path(self) -> None:
        item = DataItem(
            path=Path("/vault/ideas.md"),
            data_type="ideas",
            skill="venture",
            title="Test",
        )
        d = item.to_dict()
        assert d["path"] == "/vault/ideas.md"
        assert d["data_type"] == "ideas"
        assert d["skill"] == "venture"
        assert d["title"] == "Test"


class TestDataDiscoverFallback:
    """Tests for grep fallback in data source discovery."""

    def test_discover_data_fallback_when_rg_missing(self, tmp_path: Path) -> None:
        """Falls back to grep when rg is not on PATH for data discovery."""
        _write_md(
            tmp_path / "item.md",
            'data_source: dashboard\ndata_type: ideas\nskill: test\ntitle: "Fallback Item"',
        )

        original_which = __import__("shutil").which

        def mock_which(cmd: str) -> str | None:
            if cmd == "rg":
                return None
            return original_which(cmd)

        with patch("sync_discover.shutil.which", side_effect=mock_which):
            items = discover_data(vault_root=tmp_path)

        assert len(items) == 1
        assert items[0].title == "Fallback Item"
