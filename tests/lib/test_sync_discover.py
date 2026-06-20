"""Tests for src.lib.sync_discover — vault-wide content-based sync discovery."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

# ─── helpers ──────────────────────────────────────────────────────────────────


def _write_md(path: Path, frontmatter: str, body: str = "") -> Path:
    """Write a markdown file with optional YAML frontmatter."""
    content = f"---\n{frontmatter}\n---\n{body}" if frontmatter else body
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ─── tests ────────────────────────────────────────────────────────────────────


class TestDiscoverSyncItems:
    """Tests for discover_sync_items()."""

    def test_discovers_files_with_sync_target(self, tmp_path: Path) -> None:
        """Files with sync_target in frontmatter are discovered."""
        md = _write_md(
            tmp_path / "note.md",
            'title: "Test Note"\nsync_target: notes',
            body="Some content",
        )

        from src.lib.sync_discover import discover_sync_items

        items = discover_sync_items(vault_root=tmp_path)
        assert len(items) == 1
        assert items[0].sync_target == "notes"
        assert items[0].title == "Test Note"
        assert items[0].path == md.resolve()

    def test_skips_files_without_frontmatter(self, tmp_path: Path) -> None:
        """Files without frontmatter are skipped."""
        md = tmp_path / "plain.md"
        md.write_text("# Just markdown\nNo frontmatter here\n", encoding="utf-8")

        from src.lib.sync_discover import discover_sync_items

        items = discover_sync_items(vault_root=tmp_path)
        assert len(items) == 0

    def test_discovers_multiple_sync_targets(self, tmp_path: Path) -> None:
        """Files with different sync_target values are all discovered."""
        _write_md(tmp_path / "note.md", 'title: "A Note"\nsync_target: notes')
        _write_md(
            tmp_path / "reminder.md",
            'title: "A Reminder"\nsync_target: reminders\nsync_list: Shopping',
        )

        from src.lib.sync_discover import discover_sync_items

        items = discover_sync_items(vault_root=tmp_path)
        assert len(items) == 2
        targets = {item.sync_target for item in items}
        assert targets == {"notes", "reminders"}

    def test_handles_malformed_frontmatter_gracefully(self, tmp_path: Path) -> None:
        """Malformed YAML frontmatter does not crash discovery."""
        md = tmp_path / "bad.md"
        md.write_text("---\ntitle: [invalid yaml\nsync_target notes\n---\nBody\n", encoding="utf-8")

        from src.lib.sync_discover import discover_sync_items

        items = discover_sync_items(vault_root=tmp_path)
        assert len(items) == 0

    def test_skips_sync_target_in_body(self, tmp_path: Path) -> None:
        """sync_target in body text (not frontmatter) is ignored."""
        _write_md(
            tmp_path / "body.md",
            'title: "No Sync"',
            body="sync_target: notes\nThis is in the body only.",
        )

        from src.lib.sync_discover import discover_sync_items

        items = discover_sync_items(vault_root=tmp_path)
        assert len(items) == 0

    def test_skips_unknown_sync_target(self, tmp_path: Path) -> None:
        """Unknown sync_target values are skipped."""
        _write_md(tmp_path / "dropbox.md", 'title: "Bad Target"\nsync_target: dropbox')

        from src.lib.sync_discover import discover_sync_items

        items = discover_sync_items(vault_root=tmp_path)
        assert len(items) == 0

    def test_extracts_optional_fields(self, tmp_path: Path) -> None:
        """Optional fields (sync_folder, sync_list, sync_id) are extracted."""
        fm = "sync_target: notes\n" 'title: "Full Note"\n' 'sync_folder: "My Folder"\n' 'sync_id: "abc123"'
        _write_md(tmp_path / "full.md", fm)

        from src.lib.sync_discover import discover_sync_items

        items = discover_sync_items(vault_root=tmp_path)
        assert len(items) == 1
        assert items[0].sync_folder == "My Folder"
        assert items[0].sync_id == "abc123"
        assert items[0].sync_list is None

    def test_title_defaults_to_filename_stem(self, tmp_path: Path) -> None:
        """When title is missing from frontmatter, defaults to file stem."""
        _write_md(tmp_path / "untitled-note.md", "sync_target: notes")

        from src.lib.sync_discover import discover_sync_items

        items = discover_sync_items(vault_root=tmp_path)
        assert len(items) == 1
        assert items[0].title == "untitled-note"

    def test_modified_timestamp_is_populated(self, tmp_path: Path) -> None:
        """The modified field is populated from file mtime."""
        _write_md(tmp_path / "timed.md", 'title: "Timed"\nsync_target: notes')

        from src.lib.sync_discover import discover_sync_items

        items = discover_sync_items(vault_root=tmp_path)
        assert len(items) == 1
        assert isinstance(items[0].modified, datetime)

    def test_discovers_nested_directories(self, tmp_path: Path) -> None:
        """Files in nested subdirectories are found."""
        _write_md(
            tmp_path / "sub" / "deep" / "nested.md",
            'title: "Deep"\nsync_target: notes',
        )

        from src.lib.sync_discover import discover_sync_items

        items = discover_sync_items(vault_root=tmp_path)
        assert len(items) == 1
        assert items[0].title == "Deep"

    def test_returns_empty_for_nonexistent_vault(self, tmp_path: Path) -> None:
        """Returns empty list when vault root does not exist."""
        from src.lib.sync_discover import discover_sync_items

        items = discover_sync_items(vault_root=tmp_path / "nonexistent")
        assert items == []


class TestFallbackDiscovery:
    """Tests for grep fallback when ripgrep is not available."""

    def test_discover_falls_back_to_grep(self, tmp_path: Path) -> None:
        """Falls back to grep when ripgrep is not on PATH."""
        _write_md(tmp_path / "note.md", 'title: "Fallback"\nsync_target: notes')

        from src.lib import sync_discover

        original_which = __import__("shutil").which

        def mock_which(cmd: str) -> str | None:
            if cmd == "rg":
                return None
            return original_which(cmd)

        with patch.object(sync_discover.shutil, "which", side_effect=mock_which):
            items = sync_discover.discover_sync_items(vault_root=tmp_path)

        assert len(items) == 1
        assert items[0].title == "Fallback"


class TestSyncItemDataclass:
    """Tests for the SyncItem dataclass."""

    def test_sync_item_fields(self) -> None:
        """SyncItem has all required fields with correct defaults."""
        from src.lib.sync_discover import SyncItem

        item = SyncItem(
            path=Path("/vault/note.md"),
            sync_target="notes",
            title="Test",
            modified=datetime(2026, 3, 22),
        )
        assert item.path == Path("/vault/note.md")
        assert item.sync_target == "notes"
        assert item.title == "Test"
        assert item.modified == datetime(2026, 3, 22)
        assert item.sync_folder is None
        assert item.sync_list is None
        assert item.sync_id is None
