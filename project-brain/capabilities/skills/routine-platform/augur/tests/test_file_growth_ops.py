"""Auto-generated importability test for file_growth_ops."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_file_growth_ops_importable():
    """Verify that file_growth_ops can be imported without errors."""
    import importlib
    mod = importlib.import_module("file_growth_ops")
    assert mod is not None


def test_scan_stale_memory_entries_checks_all_client_prefixes(tmp_path: Path):
    import importlib

    mod = importlib.import_module("file_growth_ops")
    vault = tmp_path / "vault"
    entries_dir = vault / "memory" / "entries"
    entries_dir.mkdir(parents=True)
    codex_source = tmp_path / "codex"
    cursor_source = tmp_path / "cursor"
    codex_source.mkdir()
    cursor_source.mkdir()

    (codex_source / "keep.md").write_text("keep", encoding="utf-8")
    (cursor_source / "keep.md").write_text("keep", encoding="utf-8")
    (entries_dir / "codex_keep.md").write_text("assembled", encoding="utf-8")
    (entries_dir / "codex_missing.md").write_text("assembled", encoding="utf-8")
    (entries_dir / "cursor_keep.md").write_text("assembled", encoding="utf-8")

    issues = mod._scan_stale_memory_entries(
        vault,
        client_sources={"codex": codex_source, "cursor": cursor_source},
    )

    assert len(issues) == 1
    assert issues[0]["stale_count"] == 1
    assert issues[0]["stale_files"] == ["codex_missing.md"]
