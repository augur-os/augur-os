"""Regression tests for Windows-safe command-export cleanup.

Generated command files are written read-only (0o444 in ``write_generated_file``).
On Windows, ``Path.unlink()`` / ``shutil.rmtree`` on a read-only target raises
``PermissionError`` (WinError 5), which aborted the orphan-prune step in
``_sync_command_stubs`` and left de-exported legacy slash commands behind. Because
the manifest was rewritten *before* the prune, the stragglers also fell out of the
manifest and became invisible to every later run. These tests pin the fix.
"""

import os
import stat
import sys
from pathlib import Path

scripts_dir = Path(__file__).resolve().parents[2]
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))


def _make_readonly(path: Path) -> None:
    os.chmod(path, stat.S_IREAD)


def test_force_remove_deletes_readonly_file(tmp_path):
    from sync_agents.skill_sync import _force_remove

    target = tmp_path / "orphan.md"
    target.write_text("generated", encoding="utf-8")
    _make_readonly(target)

    _force_remove(target)

    assert not target.exists()


def test_force_remove_deletes_readonly_directory_tree(tmp_path):
    """Codex/Gemini command wrappers are directories (name/SKILL.md) whose
    SKILL.md is written read-only; the whole tree must still be removable."""
    from sync_agents.skill_sync import _force_remove

    target = tmp_path / "orphan-skill"
    target.mkdir()
    inner = target / "SKILL.md"
    inner.write_text("generated", encoding="utf-8")
    _make_readonly(inner)

    _force_remove(target)

    assert not target.exists()


def test_reconcile_removes_readonly_orphans_and_persists_manifest(tmp_path):
    from sync_agents.skill_sync import (
        _COMMANDS_MANIFEST,
        _load_manifest_entries,
        _reconcile_generated_orphans,
        _save_manifest_entries,
    )

    cdir = tmp_path
    manifest = cdir / _COMMANDS_MANIFEST

    # Prior generation: manifest lists two legacy commands, both on disk read-only.
    _save_manifest_entries(manifest, "files", {"dev-merge.md", "note.md"})
    for name in ("dev-merge.md", "note.md"):
        legacy = cdir / name
        legacy.write_text("legacy", encoding="utf-8")
        _make_readonly(legacy)

    # New generation writes only the canonical command.
    (cdir / "dev.md").write_text("canonical", encoding="utf-8")
    written = {"dev.md"}

    _reconcile_generated_orphans(cdir, manifest, written)

    assert not (cdir / "dev-merge.md").exists()  # read-only orphan pruned
    assert not (cdir / "note.md").exists()
    assert (cdir / "dev.md").exists()            # freshly-written file untouched
    # manifest rewritten to exactly the kept set (saved AFTER successful prune)
    assert _load_manifest_entries(manifest, "files") == {"dev.md"}


def test_reconcile_clears_manifest_when_nothing_written(tmp_path):
    from sync_agents.skill_sync import (
        _COMMANDS_MANIFEST,
        _reconcile_generated_orphans,
        _save_manifest_entries,
    )

    cdir = tmp_path
    manifest = cdir / _COMMANDS_MANIFEST
    _save_manifest_entries(manifest, "files", {"old.md"})
    old = cdir / "old.md"
    old.write_text("legacy", encoding="utf-8")
    _make_readonly(old)

    _reconcile_generated_orphans(cdir, manifest, set())

    assert not old.exists()
    assert not manifest.exists()
