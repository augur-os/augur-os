"""Auto-generated importability test for auto_index_notes."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_auto_index_notes_importable():
    """Verify that auto_index_notes can be imported without errors."""
    import src.mcp.augur_framework.tools.infrastructure.auto_index_notes
    assert src.mcp.augur_framework.tools.infrastructure.auto_index_notes is not None


def test_index_notes_resolves_staged_notes_lib(tmp_path: Path, monkeypatch):
    """_resolve_notes_lib_path finds the apple skill's notes_lib in the staged tree.

    Staged skills (r1/r2/r3/...) live under <vault>/drafts/staging/<release>/skills/
    rather than under project-brain/. The test stands up a fake staging dir under
    tmp_path and monkeypatches get_vault_staging_dir so find_skill_dir traverses
    it instead of the developer's real vault.
    """
    from skills.ai.scripts.ops import index_notes
    from src.config import paths

    staging_root = tmp_path / "staging"
    staged_skill = staging_root / "r1" / "skills" / "apple"
    notes_lib = staged_skill / "scripts" / "notes_lib.py"
    notes_lib.parent.mkdir(parents=True)
    (staged_skill / "SKILL.md").write_text("---\nname: apple\n---\n", encoding="utf-8")
    notes_lib.write_text("def write_index_cache(path):\n    return None\n", encoding="utf-8")

    monkeypatch.setattr(paths, "get_vault_staging_dir", lambda: staging_root)
    paths.invalidate_project_cache()

    assert index_notes._resolve_notes_lib_path(tmp_path) == notes_lib
